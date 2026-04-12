from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class BookingStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED_BY_PLAYER = "cancelled_by_player", "Cancelled by Player"
    CANCELLED_BY_OWNER = "cancelled_by_owner", "Cancelled by Owner"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"


class Booking(TimeStampedModel):
    """
    A confirmed reservation of a stadium slot by a player.

    The (slot, status=confirmed) pair is globally unique — enforced by a
    partial UniqueConstraint so that cancelled/no-show records for the same
    slot do not conflict with a new confirmed booking.
    """

    player = models.ForeignKey(
        "auth_users.User",
        on_delete=models.CASCADE,
        related_name="bookings",
        limit_choices_to={"role": "player"},
    )
    slot = models.ForeignKey(
        "stadiums.Slot",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    stadium = models.ForeignKey(
        "stadiums.Stadium",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=30,
        choices=BookingStatus.choices,
        default=BookingStatus.CONFIRMED,
        db_index=True,
    )
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        "auth_users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_bookings",
    )
    is_late_cancellation = models.BooleanField(default=False)
    price_at_booking = models.DecimalField(max_digits=8, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "booking"
        verbose_name_plural = "bookings"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(status="confirmed"),
                name="unique_confirmed_booking_per_slot",
            ),
        ]

    def __str__(self) -> str:
        return f"Booking({self.pk}) {self.player_id} → slot {self.slot_id} [{self.status}]"
