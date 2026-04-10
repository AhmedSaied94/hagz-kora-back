from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class DeviceToken(TimeStampedModel):
    """
    FCM device token associated with a user session.

    One user may have multiple tokens (multiple devices / reinstalls).
    Tokens are registered on login and deregistered on logout.
    """

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(
        max_length=10,
        choices=Platform.choices,
        default=Platform.ANDROID,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "device token"
        verbose_name_plural = "device tokens"
        indexes: ClassVar[list] = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.platform} / {self.token[:20]}…"
