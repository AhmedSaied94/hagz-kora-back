from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UserRole(models.TextChoices):
    PLAYER = "player", "Player"
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"


class KycStatus(models.TextChoices):
    PENDING = "pending_kyc", "Pending KYC"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "kyc_approved", "KYC Approved"
    REJECTED = "kyc_rejected", "KYC Rejected"


class UserManager(BaseUserManager):
    def _create_user(self, phone, email, password, **extra_fields):
        if not email:
            if not phone:
                raise ValueError("Either phone or email must be provided.")
            # Phone-only users get a stable, unique placeholder email so the
            # DB unique constraint on email is always satisfied.
            email = f"{phone.lstrip('+')}@placeholder.hagzkora.internal"
        email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, email, password, **extra_fields)

    def create_superuser(self, phone=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"]:
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(phone, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for Hagz Kora.

    Primary identifier: ``phone`` (production OTP flow) / ``email`` (dev email+password flow).
    Roles determine what each user can do: player, owner, admin.
    KYC status tracks stadium-owner verification (only relevant for role=owner).
    """

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PLAYER)
    kyc_status = models.CharField(
        max_length=20,
        choices=KycStatus.choices,
        default=KycStatus.PENDING,
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["full_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email or self.phone or f"User({self.pk})"

    @property
    def is_player(self) -> bool:
        return self.role == UserRole.PLAYER

    @property
    def is_owner(self) -> bool:
        return self.role == UserRole.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_kyc_approved(self) -> bool:
        return self.role == UserRole.OWNER and self.kyc_status == KycStatus.APPROVED


class PlayerProfile(TimeStampedModel):
    """Extended profile for users with role=player."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="player_profile")
    city = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    preferred_position = models.CharField(max_length=50, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    bio = models.TextField(blank=True)

    class Meta:
        verbose_name = "player profile"
        verbose_name_plural = "player profiles"

    def __str__(self) -> str:
        return f"PlayerProfile({self.user})"


class OwnerProfile(TimeStampedModel):
    """Extended profile for users with role=owner. Holds KYC documents."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="owner_profile")
    business_name_ar = models.CharField(max_length=200)
    business_name_en = models.CharField(max_length=200, blank=True)
    national_id_number = models.CharField(max_length=50)
    city = models.CharField(max_length=100, blank=True)
    national_id_front = models.ImageField(upload_to="kyc/", null=True, blank=True)
    national_id_back = models.ImageField(upload_to="kyc/", null=True, blank=True)

    class Meta:
        verbose_name = "owner profile"
        verbose_name_plural = "owner profiles"

    def __str__(self) -> str:
        return f"OwnerProfile({self.user})"
