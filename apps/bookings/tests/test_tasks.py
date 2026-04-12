"""Tests for apps.bookings.tasks."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus
from apps.bookings.tasks import mark_completed_bookings
from tests.factories import BookingFactory, SlotFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slot_ended(days_ago: int = 1) -> object:
    """Return a Slot whose end_time is in the past."""
    past_date = timezone.localdate() - datetime.timedelta(days=days_ago)
    return SlotFactory(
        date=past_date, start_time=datetime.time(10, 0), end_time=datetime.time(11, 0)
    )


def _make_slot_future(hours_ahead: int = 2) -> object:
    """Return a Slot whose end_time is in the future (today, end_time > now)."""
    future_time = (datetime.datetime.now() + datetime.timedelta(hours=hours_ahead)).time()
    # Ensure start_time is before end_time
    start_time = (datetime.datetime.now() + datetime.timedelta(hours=hours_ahead - 1)).time()
    return SlotFactory(
        date=timezone.localdate(),
        start_time=start_time,
        end_time=future_time,
    )


# ---------------------------------------------------------------------------
# Integration tests (require DB)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
def test_past_confirmed_bookings_are_marked_completed() -> None:
    """Confirmed bookings with a slot that ended yesterday → status=completed."""
    slot = _make_slot_ended(days_ago=1)
    booking = BookingFactory(slot=slot, status="confirmed")

    result = mark_completed_bookings.apply().get()

    booking.refresh_from_db()
    assert booking.status == BookingStatus.COMPLETED
    assert result == {"completed": 1}


@pytest.mark.integration
@pytest.mark.django_db
def test_future_confirmed_bookings_are_not_touched() -> None:
    """Confirmed bookings whose slot ends in the future must not be updated."""
    slot = _make_slot_future(hours_ahead=3)
    booking = BookingFactory(slot=slot, status="confirmed")

    result = mark_completed_bookings.apply().get()

    booking.refresh_from_db()
    assert booking.status == BookingStatus.CONFIRMED
    assert result == {"completed": 0}


@pytest.mark.integration
@pytest.mark.django_db
def test_already_completed_bookings_are_not_touched() -> None:
    """Idempotency: already-completed bookings must not be double-updated."""
    slot = _make_slot_ended()
    booking = BookingFactory(slot=slot, status="completed")

    result = mark_completed_bookings.apply().get()

    booking.refresh_from_db()
    assert booking.status == BookingStatus.COMPLETED
    assert result == {"completed": 0}


@pytest.mark.integration
@pytest.mark.django_db
def test_cancelled_bookings_are_not_touched() -> None:
    """Cancelled bookings with a past slot must not be changed to completed."""
    slot = _make_slot_ended()
    booking = BookingFactory(slot=slot, status="cancelled_by_player")

    result = mark_completed_bookings.apply().get()

    booking.refresh_from_db()
    assert booking.status == BookingStatus.CANCELLED_BY_PLAYER
    assert result == {"completed": 0}


@pytest.mark.integration
@pytest.mark.django_db
def test_empty_set_returns_zero_without_error() -> None:
    """No confirmed bookings at all → returns {"completed": 0} cleanly."""
    result = mark_completed_bookings.apply().get()

    assert result == {"completed": 0}


@pytest.mark.integration
@pytest.mark.django_db
def test_returns_correct_count_for_multiple_bookings() -> None:
    """Task returns the exact count when several bookings are updated."""
    past_slot_1 = _make_slot_ended(days_ago=2)
    past_slot_2 = _make_slot_ended(days_ago=3)
    future_slot = _make_slot_future()

    b1 = BookingFactory(slot=past_slot_1, status="confirmed")
    b2 = BookingFactory(slot=past_slot_2, status="confirmed")
    b_future = BookingFactory(slot=future_slot, status="confirmed")

    result = mark_completed_bookings.apply().get()

    b1.refresh_from_db()
    b2.refresh_from_db()
    b_future.refresh_from_db()

    assert b1.status == BookingStatus.COMPLETED
    assert b2.status == BookingStatus.COMPLETED
    assert b_future.status == BookingStatus.CONFIRMED
    assert result == {"completed": 2}


@pytest.mark.integration
@pytest.mark.django_db
def test_today_slot_ended_earlier_is_completed() -> None:
    """A slot on today's date whose end_time has already passed must be completed."""
    # Use a time well in the past (midnight) so it's always "past" during the test
    slot = SlotFactory(
        date=timezone.localdate(),
        start_time=datetime.time(0, 0),
        end_time=datetime.time(0, 1),
    )
    booking = BookingFactory(slot=slot, status="confirmed")

    result = mark_completed_bookings.apply().get()

    booking.refresh_from_db()
    assert booking.status == BookingStatus.COMPLETED
    assert result["completed"] >= 1


# ---------------------------------------------------------------------------
# Unit tests (no DB — test retry path via mocking)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_task_retries_on_operational_error() -> None:
    """OperationalError should trigger self.retry (mocked)."""
    from django.db import OperationalError

    with (
        patch("apps.bookings.tasks.Booking") as mock_booking_cls,
        patch("apps.bookings.tasks.transaction") as mock_tx,
    ):
        mock_tx.atomic.return_value.__enter__ = lambda s: s
        mock_tx.atomic.return_value.__exit__ = lambda s, *a: False
        mock_booking_cls.objects.filter.side_effect = OperationalError("DB gone")

        task_instance = mark_completed_bookings

        with pytest.raises(Exception):
            # Apply eagerly — Celery raises Retry which wraps the exc
            task_instance.apply(throw=True).get()
