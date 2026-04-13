from __future__ import annotations

from typing import ClassVar

from apps.notifications.models import DeviceToken
from rest_framework import serializers


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields: ClassVar[list[str]] = ["token", "platform", "language"]
        # Strip the auto-added UniqueValidator so duplicate tokens reach create()
        # and are handled by the upsert logic there.
        extra_kwargs: ClassVar[dict] = {"token": {"validators": []}}

    def validate_token(self, value: str) -> str:
        return value.strip()

    def create(self, validated_data: dict) -> DeviceToken:
        user = self.context["request"].user
        # Upsert: if the token already exists, reactivate + re-associate it
        token, _ = DeviceToken.objects.update_or_create(
            token=validated_data["token"],
            defaults={
                "user": user,
                "platform": validated_data.get("platform", DeviceToken.Platform.ANDROID),
                "is_active": True,
            },
        )
        return token
