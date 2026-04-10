from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.core.models import TimeStampedModel


class SurfaceType(models.TextChoices):
    GRASS: ClassVar[str] = "grass", "Grass"
    ARTIFICIAL: ClassVar[str] = "artificial", "Artificial"
    FUTSAL: ClassVar[str] = "futsal", "Futsal"


class PitchSize(models.TextChoices):
    FIVE_VS_FIVE: ClassVar[str] = "5v5", "5v5"
    SEVEN_VS_SEVEN: ClassVar[str] = "7v7", "7v7"
    ELEVEN_VS_ELEVEN: ClassVar[str] = "11v11", "11v11"


class Pitch(TimeStampedModel):
    """
    A football pitch available for booking.

    Supports geo-spatial search via PostGIS location field.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = gis_models.PointField(geography=True, null=True, blank=True)
    address = models.CharField(max_length=500, blank=True)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    surface_type = models.CharField(
        max_length=20,
        choices=SurfaceType.choices,
        default=SurfaceType.GRASS,
    )
    amenities = models.JSONField(default=list, blank=True)
    size = models.CharField(
        max_length=10,
        choices=PitchSize.choices,
        default=PitchSize.FIVE_VS_FIVE,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pitches",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name: ClassVar[str] = "pitch"
        verbose_name_plural: ClassVar[str] = "pitches"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["surface_type", "is_active"]),
            models.Index(fields=["size", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name
