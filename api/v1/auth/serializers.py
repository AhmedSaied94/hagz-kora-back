from __future__ import annotations

from typing import ClassVar

import phonenumbers
from apps.auth_users.models import OwnerProfile, PlayerProfile, UserRole
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalize_phone(phone: str) -> str:
    """Parse and normalise to E.164. Raises ValidationError on invalid input."""
    try:
        parsed = phonenumbers.parse(phone, "EG")  # default region Egypt
    except phonenumbers.NumberParseException as exc:
        raise serializers.ValidationError("Invalid phone number.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise serializers.ValidationError("Phone number is not valid.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def _jwt_pair(user) -> dict:
    """Return a JWT access + refresh token dict for ``user``."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# ── OTP ───────────────────────────────────────────────────────────────────────


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        return _normalize_phone(value)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_phone(self, value: str) -> str:
        return _normalize_phone(value)


# ── Email backend (dev / staging only) ───────────────────────────────────────


class EmailRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=[UserRole.PLAYER, UserRole.OWNER],
        default=UserRole.PLAYER,
    )

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        normalized = _normalize_phone(value)
        if User.objects.filter(phone=normalized).exists():
            raise serializers.ValidationError("A user with this phone already exists.")
        return normalized

    def create(self, validated_data: dict) -> User:
        phone = validated_data.pop("phone", None) or None
        role = validated_data.pop("role", UserRole.PLAYER)
        password = validated_data.pop("password")
        user = User.objects.create_user(
            phone=phone,
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            password=password,
            role=role,
        )
        return user


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        email = attrs["email"].lower()
        password = attrs["password"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.") from None

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs["user"] = user
        return attrs


# ── JWT token management ──────────────────────────────────────────────────────


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# ── Player profile ────────────────────────────────────────────────────────────


class PlayerProfileSerializer(serializers.ModelSerializer):
    # Read-only user fields surfaced on the profile
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = PlayerProfile
        fields: ClassVar[list[str]] = [
            "phone",
            "email",
            "full_name",
            "city",
            "date_of_birth",
            "preferred_position",
            "avatar",
            "bio",
        ]
        read_only_fields: ClassVar[list[str]] = ["phone", "email", "full_name"]


# ── Owner profile ─────────────────────────────────────────────────────────────


class OwnerRegisterSerializer(serializers.Serializer):
    """
    Used by both the email-backend owner registration and the phone-OTP flow
    (after OTP verify, if the user has role=owner and no owner profile yet).
    """

    business_name_ar = serializers.CharField(max_length=200)
    business_name_en = serializers.CharField(max_length=200, required=False, allow_blank=True)
    national_id_number = serializers.CharField(max_length=50)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # Only used during initial email-backend registration; ignored in phone flow
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    full_name = serializers.CharField(max_length=200, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        normalized = _normalize_phone(value)
        if User.objects.filter(phone=normalized).exists():
            raise serializers.ValidationError("A user with this phone already exists.")
        return normalized

    def validate_email(self, value: str) -> str:
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower() if value else value

    @transaction.atomic
    def create(self, validated_data: dict) -> User:
        """Create a new owner User + OwnerProfile atomically."""
        phone = validated_data.pop("phone", None) or None
        email = validated_data.pop("email", "")
        password = validated_data.pop("password", None)
        full_name = validated_data.pop("full_name", "")

        user = User.objects.create_user(
            phone=phone,
            email=email,
            full_name=full_name,
            password=password,
            role=UserRole.OWNER,
        )
        OwnerProfile.objects.create(user=user, **validated_data)
        return user


class OwnerProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    kyc_status = serializers.CharField(source="user.kyc_status", read_only=True)

    class Meta:
        model = OwnerProfile
        fields: ClassVar[list[str]] = [
            "phone",
            "email",
            "full_name",
            "kyc_status",
            "business_name_ar",
            "business_name_en",
            "national_id_number",
            "city",
            "national_id_front",
            "national_id_back",
        ]
        read_only_fields: ClassVar[list[str]] = ["phone", "email", "full_name", "kyc_status"]


# ── Shared user info (returned in JWT responses) ──────────────────────────────


class UserTokenResponseSerializer(serializers.Serializer):
    """Serializer for the body returned after successful authentication."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user_id = serializers.IntegerField()
    role = serializers.CharField()
    full_name = serializers.CharField()
