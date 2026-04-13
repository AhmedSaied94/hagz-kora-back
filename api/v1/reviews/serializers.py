"""Serializers for the reviews API (v1)."""

from __future__ import annotations

from apps.reviews.models import Review
from rest_framework import serializers


class ReviewSerializer(serializers.ModelSerializer):
    """Read-only serializer for review list/detail responses."""

    booking_id = serializers.IntegerField(source="booking.pk", read_only=True)
    player_id = serializers.IntegerField(source="player.pk", read_only=True)
    stadium_id = serializers.IntegerField(source="stadium.pk", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "booking_id",
            "player_id",
            "stadium_id",
            "overall_rating",
            "pitch_quality",
            "facilities",
            "value_for_money",
            "text",
            "owner_response",
            "created_at",
        ]
        read_only_fields = fields


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Write serializer used when a player submits a review."""

    class Meta:
        model = Review
        fields = [
            "overall_rating",
            "pitch_quality",
            "facilities",
            "value_for_money",
            "text",
        ]
        extra_kwargs = {
            "overall_rating": {"required": True},
            "pitch_quality": {"required": False},
            "facilities": {"required": False},
            "value_for_money": {"required": False},
            "text": {"required": False},
        }


class OwnerResponseSerializer(serializers.ModelSerializer):
    """Write serializer used when an owner responds to a review."""

    class Meta:
        model = Review
        fields = ["owner_response"]

    def validate_owner_response(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Owner response cannot be blank.")
        return value
