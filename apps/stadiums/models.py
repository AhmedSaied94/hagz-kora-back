from __future__ import annotations

from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.core.models import TimeStampedModel


class SportType(models.TextChoices):
    FIVE_VS_FIVE = "5v5", "5 vs 5"
    SEVEN_VS_SEVEN = "7v7", "7 vs 7"


class StadiumStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_REVIEW = "pending_review", "Pending Review"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class SlotStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    BOOKED = "booked", "Booked"
    BLOCKED = "blocked", "Blocked"


class Stadium(TimeStampedModel):
    """
    A football pitch listed by an owner.

    Status flow: draft → pending_review → active (or back to draft with rejection_note).
    """

    owner = models.ForeignKey(
        "auth_users.User",
        on_delete=models.CASCADE,
        related_name="stadiums",
        limit_choices_to={"role": "owner"},
    )
    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    sport_type = models.CharField(max_length=10, choices=SportType.choices)
    location = gis_models.PointField(geography=True, null=True, blank=True)
    address_ar = models.CharField(max_length=500)
    address_en = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100)
    price_per_slot = models.DecimalField(max_digits=8, decimal_places=2)
    slot_duration_minutes = models.PositiveIntegerField(default=60)
    phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StadiumStatus.choices,
        default=StadiumStatus.DRAFT,
        db_index=True,
    )
    rejection_note = models.TextField(blank=True)

    class Meta:
        verbose_name = "stadium"
        verbose_name_plural = "stadiums"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name_ar or self.name_en or f"Stadium({self.pk})"

    def submit_for_review(self) -> None:
        """Transition draft → pending_review. Raises ValueError if not in draft."""
        if self.status != StadiumStatus.DRAFT:
            raise ValueError(f"Cannot submit a stadium with status '{self.status}'.")
        self.status = StadiumStatus.PENDING_REVIEW
        self.rejection_note = ""
        self.save(update_fields=["status", "rejection_note", "updated_at"])

    def approve(self) -> None:
        """Transition pending_review → active."""
        if self.status != StadiumStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot approve a stadium with status '{self.status}'.")
        self.status = StadiumStatus.ACTIVE
        self.save(update_fields=["status", "updated_at"])

    def reject(self, note: str) -> None:
        """Transition pending_review → draft with a rejection note."""
        if self.status != StadiumStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot reject a stadium with status '{self.status}'.")
        self.status = StadiumStatus.DRAFT
        self.rejection_note = note
        self.save(update_fields=["status", "rejection_note", "updated_at"])


class StadiumPhoto(TimeStampedModel):
    """
    Photo attached to a stadium.

    The original file is stored via Django's file storage (S3 in prod, local in dev).
    Celery generates thumbnail (400x300) and medium (800x600) variants and stores
    their URLs in thumbnail_url / medium_url.
    """

    stadium = models.ForeignKey(Stadium, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="stadiums/photos/original/")
    thumbnail_url = models.URLField(max_length=2000, blank=True)
    medium_url = models.URLField(max_length=2000, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_cover = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "stadium photo"
        verbose_name_plural = "stadium photos"
        ordering = ["order"]

    def __str__(self) -> str:
        return f"Photo({self.pk}) for {self.stadium}"


class OperatingHour(TimeStampedModel):
    """
    Operating hours for one day of the week per stadium.
    day_of_week follows Python's weekday(): 0=Monday … 6=Sunday.
    """

    stadium = models.ForeignKey(Stadium, on_delete=models.CASCADE, related_name="operating_hours")
    day_of_week = models.SmallIntegerField(
        choices=list(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]))
    )
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "operating hour"
        verbose_name_plural = "operating hours"
        unique_together = ("stadium", "day_of_week")
        ordering = ["day_of_week"]

    def __str__(self) -> str:
        day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][self.day_of_week]
        return f"{self.stadium} — {day_name}"


class Slot(TimeStampedModel):
    """
    A bookable time slot for a stadium on a specific date.
    Generated daily by Celery Beat for the next 60 days.
    """

    stadium = models.ForeignKey(Stadium, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=SlotStatus.choices,
        default=SlotStatus.AVAILABLE,
        db_index=True,
    )

    class Meta:
        verbose_name = "slot"
        verbose_name_plural = "slots"
        unique_together = ("stadium", "date", "start_time")
        ordering = ["date", "start_time"]

    def __str__(self) -> str:
        return f"{self.stadium} | {self.date} {self.start_time}-{self.end_time}"
