"""Integration tests for owner booking cancellation.

All tests hit the real DB and exercise the full Django/DRF stack via
APIClient. They are marked @pytest.mark.integration and rely on the
factories in tests/factories.py plus the conftest fixtures.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookings.models import Booking, BookingStatus
from apps.stadiums.models import Slot, SlotStatus
from tests.factories import BookingFactory, OwnerUserFactory, PlayerUserFactory, SlotFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cancel_url(booking_id: int) -> str:
    return reverse("owner-booking-cancel", kwargs={"pk": booking_id})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db):
    return OwnerUserFactory()


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def slot(db, owner):
    """An available slot belonging to `owner`'s stadium."""
    from tests.factories import StadiumFactory

    stadium = StadiumFactory(owner=owner, active=True)
    return SlotFactory(stadium=stadium, status=SlotStatus.BOOKED)


@pytest.fixture
def confirmed_booking(db, slot):
    """A confirmed booking for the owner's slot."""
    return BookingFactory(
        slot=slot,
        stadium=slot.stadium,
        status=BookingStatus.CONFIRMED,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_owner_cancel_happy_path(owner, owner_client, confirmed_booking, slot):
    """Happy path: owner cancels a confirmed booking.

    - Booking status becomes cancelled_by_owner.
    - cancelled_by is set to the owner.
    - cancellation_reason is saved.
    - Slot.status is returned to available.
    """
    url = _cancel_url(confirmed_booking.pk)

    with patch("apps.notifications.tasks.notify_player_of_owner_cancellation.delay") as mock_task:
        response = owner_client.post(url, {"cancellation_reason": "Maintenance required"})

    assert response.status_code == status.HTTP_200_OK, response.data

    # Reload from DB for source-of-truth assertions.
    confirmed_booking.refresh_from_db()
    slot.refresh_from_db()

    assert confirmed_booking.status == BookingStatus.CANCELLED_BY_OWNER
    assert confirmed_booking.cancelled_by_id == owner.pk
    assert confirmed_booking.cancellation_reason == "Maintenance required"
    assert slot.status == SlotStatus.AVAILABLE

    # Notification should have been enqueued (via on_commit — in tests this fires
    # synchronously inside the TestCase's ATOMIC_REQUESTS wrapping).
    mock_task.assert_called_once_with(confirmed_booking.pk)

    # Response body contains serialized booking.
    assert response.data["status"] == BookingStatus.CANCELLED_BY_OWNER
    assert response.data["cancellation_reason"] == "Maintenance required"


@pytest.mark.integration
def test_owner_cannot_cancel_other_owners_booking(db, confirmed_booking, slot):
    """Owner cannot cancel a booking that belongs to a different owner's stadium.

    Expected: 404 — the booking is invisible to this owner.
    """
    other_owner = OwnerUserFactory()
    client = APIClient()
    client.force_authenticate(user=other_owner)

    url = _cancel_url(confirmed_booking.pk)
    response = client.post(url, {"cancellation_reason": "Should not work"})

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
def test_cannot_cancel_completed_booking(owner_client, confirmed_booking):
    """Owner cannot cancel a booking that is already completed.

    Expected: 400 with code NOT_CANCELLABLE.
    """
    confirmed_booking.status = BookingStatus.COMPLETED
    confirmed_booking.save(update_fields=["status"])

    url = _cancel_url(confirmed_booking.pk)
    response = owner_client.post(url, {"cancellation_reason": "Too late"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "NOT_CANCELLABLE"


@pytest.mark.integration
def test_cannot_cancel_already_cancelled_booking(owner_client, confirmed_booking):
    """Owner cannot re-cancel a booking that is already cancelled.

    Expected: 400 with code NOT_CANCELLABLE.
    """
    confirmed_booking.status = BookingStatus.CANCELLED_BY_PLAYER
    confirmed_booking.save(update_fields=["status"])

    url = _cancel_url(confirmed_booking.pk)
    response = owner_client.post(url, {"cancellation_reason": "Already gone"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "NOT_CANCELLABLE"


@pytest.mark.integration
def test_empty_cancellation_reason_returns_400(owner_client, confirmed_booking):
    """Sending an empty cancellation_reason string returns 400 REASON_REQUIRED."""
    url = _cancel_url(confirmed_booking.pk)
    response = owner_client.post(url, {"cancellation_reason": ""})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "REASON_REQUIRED"


@pytest.mark.integration
def test_missing_cancellation_reason_returns_400(owner_client, confirmed_booking):
    """Omitting cancellation_reason entirely returns 400 REASON_REQUIRED."""
    url = _cancel_url(confirmed_booking.pk)
    response = owner_client.post(url, {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "REASON_REQUIRED"


@pytest.mark.integration
def test_unauthenticated_request_returns_401(api_client, confirmed_booking):
    """Unauthenticated requests are rejected with 401."""
    url = _cancel_url(confirmed_booking.pk)
    response = api_client.post(url, {"cancellation_reason": "Anonymous attempt"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
def test_player_cannot_use_owner_cancel_endpoint(player_client, confirmed_booking):
    """Player role must not access the owner cancellation endpoint.

    Expected: 403 Forbidden.
    """
    url = _cancel_url(confirmed_booking.pk)
    response = player_client.post(url, {"cancellation_reason": "Player tries owner route"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.integration
def test_slot_rolls_back_to_available_atomically(owner_client, confirmed_booking, slot):
    """Cancelling returns Slot.status to available in the same atomic transaction.

    We verify by reading from the DB *after* the response — if the transaction
    rolled back for any reason the slot would still be BOOKED.
    """
    assert slot.status == SlotStatus.BOOKED  # pre-condition

    with patch("apps.notifications.tasks.notify_player_of_owner_cancellation.delay"):
        response = owner_client.post(
            _cancel_url(confirmed_booking.pk),
            {"cancellation_reason": "Stadium closed today"},
        )

    assert response.status_code == status.HTTP_200_OK

    slot.refresh_from_db()
    assert slot.status == SlotStatus.AVAILABLE
