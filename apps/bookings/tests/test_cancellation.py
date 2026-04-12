"""Integration tests for player booking cancellation.

All tests hit the real DB and exercise the full Django/DRF stack via
APIClient. They are marked @pytest.mark.integration and rely on the
factories in tests/factories.py plus the conftest fixtures.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookings.models import Booking, BookingStatus
from apps.stadiums.models import Slot, SlotStatus
from tests.factories import BookingFactory, PlayerUserFactory, SlotFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cancel_url(booking_id: int) -> str:
    return reverse("booking-cancel", kwargs={"pk": booking_id})


def _slot_start_dt(slot: Slot) -> datetime.datetime:
    """Return the slot's start as an aware datetime in the current timezone."""
    return timezone.make_aware(
        datetime.datetime.combine(slot.date, slot.start_time),
        timezone.get_current_timezone(),
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBookingCancellation:
    """POST /api/v1/bookings/<pk>/cancel/"""

    # ------------------------------------------------------------------
    # 1. Happy path
    # ------------------------------------------------------------------

    def test_player_cancels_confirmed_booking(self, db):
        """Cancelling a confirmed booking sets status to cancelled_by_player
        and returns 200 with the updated booking data."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        client = APIClient()
        client.force_authenticate(user=booking.player)

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == BookingStatus.CANCELLED_BY_PLAYER

        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED_BY_PLAYER
        assert booking.cancelled_by == booking.player

    # ------------------------------------------------------------------
    # 2. Slot status rolls back to available on successful cancel
    # ------------------------------------------------------------------

    def test_slot_becomes_available_after_cancel(self, db):
        """After a successful cancellation, Slot.status must be 'available'."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        client = APIClient()
        client.force_authenticate(user=booking.player)

        client.post(_cancel_url(booking.pk))

        slot.refresh_from_db()
        assert slot.status == SlotStatus.AVAILABLE

    # ------------------------------------------------------------------
    # 3. Late cancellation flag — within 2 hours
    # ------------------------------------------------------------------

    def test_late_cancellation_sets_flag(self, db):
        """When the slot starts within 2 hours, is_late_cancellation=True."""
        # Build an aware datetime in the local (Cairo) timezone 1 hour ahead,
        # then extract the local date/time so make_aware inside the service
        # reconstructs exactly the same moment.
        local_tz = timezone.get_current_timezone()
        soon_local = timezone.localtime(timezone.now() + datetime.timedelta(hours=1), local_tz)
        slot = SlotFactory(
            date=soon_local.date(),
            start_time=soon_local.time().replace(second=0, microsecond=0),
            status=SlotStatus.BOOKED,
        )
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        client = APIClient()
        client.force_authenticate(user=booking.player)

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_late_cancellation"] is True

        booking.refresh_from_db()
        assert booking.is_late_cancellation is True

    # ------------------------------------------------------------------
    # 4. Non-late cancellation — more than 2 hours away
    # ------------------------------------------------------------------

    def test_non_late_cancellation_does_not_set_flag(self, db):
        """When the slot starts more than 2 hours away, is_late_cancellation=False."""
        # Build an aware datetime in the local (Cairo) timezone 3 hours ahead,
        # then extract the local date/time to match how the service interprets them.
        local_tz = timezone.get_current_timezone()
        future_local = timezone.localtime(timezone.now() + datetime.timedelta(hours=3), local_tz)
        slot = SlotFactory(
            date=future_local.date(),
            start_time=future_local.time().replace(second=0, microsecond=0),
            status=SlotStatus.BOOKED,
        )
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        client = APIClient()
        client.force_authenticate(user=booking.player)

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_late_cancellation"] is False

        booking.refresh_from_db()
        assert booking.is_late_cancellation is False

    # ------------------------------------------------------------------
    # 5. Cannot cancel a non-confirmed booking
    # ------------------------------------------------------------------

    def test_cannot_cancel_completed_booking(self, db):
        """Attempting to cancel a completed booking returns 400 NOT_CANCELLABLE."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.COMPLETED)

        client = APIClient()
        client.force_authenticate(user=booking.player)

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "NOT_CANCELLABLE"

        # Booking must be unchanged.
        booking.refresh_from_db()
        assert booking.status == BookingStatus.COMPLETED

    # ------------------------------------------------------------------
    # 6. Cannot cancel another player's booking — 404
    # ------------------------------------------------------------------

    def test_cannot_cancel_another_players_booking(self, db):
        """Trying to cancel a booking that belongs to a different player returns 404."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        other_player = PlayerUserFactory()
        client = APIClient()
        client.force_authenticate(user=other_player)

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Original booking must be unchanged.
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    # ------------------------------------------------------------------
    # 7. Unauthenticated request returns 401
    # ------------------------------------------------------------------

    def test_unauthenticated_returns_401(self, db):
        """An unauthenticated request to cancel must be rejected with 401."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        client = APIClient()  # no force_authenticate

        response = client.post(_cancel_url(booking.pk))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ------------------------------------------------------------------
    # 8. Atomicity: if Slot.save() raises, Booking.status is unchanged
    # ------------------------------------------------------------------

    def test_atomic_rollback_if_slot_save_fails(self, db):
        """If Slot.save() raises after Booking.save(), the entire transaction
        is rolled back and the booking remains 'confirmed'."""
        slot = SlotFactory(status=SlotStatus.BOOKED)
        booking = BookingFactory(slot=slot, status=BookingStatus.CONFIRMED)

        original_slot_save = Slot.save

        call_count = {"n": 0}

        def failing_slot_save(self, *args, **kwargs):
            call_count["n"] += 1
            raise RuntimeError("Simulated DB failure on slot update")

        client = APIClient()
        client.force_authenticate(user=booking.player)

        with patch.object(Slot, "save", failing_slot_save):
            with pytest.raises(RuntimeError):
                from apps.bookings.services import cancel_booking

                cancel_booking(booking.player, booking.pk)

        # Both objects must be in their original state.
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

        slot.refresh_from_db()
        assert slot.status == SlotStatus.BOOKED
