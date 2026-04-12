"""Serializers for the bookings API (v1)."""

from __future__ import annotations

from apps.bookings.models import Booking
from rest_framework import serializers


class CreateBookingSerializer(serializers.Serializer):
    """Request body for POST /api/v1/bookings/."""

    slot_id = serializers.IntegerField(required=True, min_value=1)


class OwnerCancelBookingSerializer(serializers.Serializer):
    """Request body for POST /api/v1/owner/bookings/<pk>/cancel/."""

    cancellation_reason = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=5,
        max_length=500,
        help_text="Reason the owner is cancelling this booking (5-500 characters).",
    )


class BookingSerializer(serializers.ModelSerializer):
    """Response body for booking endpoints.

    Includes denormalised stadium + slot fields so the mobile client can
    render a booking card without a second round trip.
    """

    stadium_name_ar = serializers.CharField(source="stadium.name_ar", read_only=True)
    stadium_name_en = serializers.CharField(source="stadium.name_en", read_only=True)
    date = serializers.DateField(source="slot.date", read_only=True)
    start_time = serializers.TimeField(source="slot.start_time", read_only=True)
    end_time = serializers.TimeField(source="slot.end_time", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "player",
            "slot",
            "stadium",
            "status",
            "cancellation_reason",
            "cancelled_by",
            "is_late_cancellation",
            "price_at_booking",
            "deposit_amount",
            "stadium_name_ar",
            "stadium_name_en",
            "date",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
