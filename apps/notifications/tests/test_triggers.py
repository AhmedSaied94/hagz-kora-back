"""Integration tests — verify that every business-level action enqueues
the expected Celery notification task via `.delay()`.

All task calls are intercepted by patching the `.delay` method — no real
workers or external services are involved.

Rules:
- `@pytest.mark.django_db(transaction=True)` is used wherever the code
  under test relies on `transaction.on_commit` to fire the callback
  (create_booking, cancel_booking, cancel_booking_by_owner).
- Stadium approval/rejection are straight synchronous calls — plain
  `@pytest.mark.django_db` is enough there.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from tests.factories import (
    BookingFactory,
    OwnerUserFactory,
    PlayerUserFactory,
    SlotFactory,
    StadiumFactory,
)

from apps.bookings.services import cancel_booking, cancel_booking_by_owner, create_booking

# ---------------------------------------------------------------------------
# Booking confirmed — player + owner both notified
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestBookingConfirmedTriggers:
    """create_booking → player + owner notification tasks enqueued."""

    def test_confirmed_booking_enqueues_player_and_owner_notifications(self):
        player = PlayerUserFactory()
        slot = SlotFactory()  # active stadium, available slot

        with (
            patch("apps.notifications.tasks.notify_booking_confirmed_player.delay") as mock_player,
            patch("apps.notifications.tasks.notify_booking_confirmed_owner.delay") as mock_owner,
        ):
            booking = create_booking(player, slot.pk)

        mock_player.assert_called_once_with(booking.id)
        mock_owner.assert_called_once_with(booking.id)

    def test_only_booking_confirmed_tasks_are_called_on_create(self):
        """No cancellation tasks should fire when a booking is created."""
        player = PlayerUserFactory()
        slot = SlotFactory()

        with (
            patch("apps.notifications.tasks.notify_booking_confirmed_player.delay"),
            patch("apps.notifications.tasks.notify_booking_confirmed_owner.delay"),
            patch(
                "apps.notifications.tasks.notify_booking_cancelled_by_player.delay"
            ) as mock_cancel,
        ):
            create_booking(player, slot.pk)

        mock_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# Player cancellation — owner notified
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestPlayerCancellationTrigger:
    """cancel_booking → owner notified about player cancellation."""

    def test_cancel_booking_enqueues_owner_notification(self):
        player = PlayerUserFactory()
        # Use a slot well in the future so it is not a late cancellation.
        future_date = datetime.date.today() + datetime.timedelta(days=7)
        slot = SlotFactory(date=future_date, status="available")
        # Build a confirmed booking without going through create_booking so we
        # don't need to worry about the slot status flip or the on_commit
        # notifications from create_booking interfering with our assertion.
        from apps.bookings.models import BookingStatus
        from apps.stadiums.models import SlotStatus

        booking = BookingFactory(player=player, slot=slot, status=BookingStatus.CONFIRMED)
        # Ensure the slot is marked BOOKED so cancel_booking can flip it back.
        slot.status = SlotStatus.BOOKED
        slot.save(update_fields=["status", "updated_at"])

        with patch(
            "apps.notifications.tasks.notify_booking_cancelled_by_player.delay"
        ) as mock_cancel:
            cancel_booking(player, booking.pk)

        mock_cancel.assert_called_once_with(booking.pk)

    def test_player_cancel_does_not_enqueue_owner_cancellation_task(self):
        """notify_player_of_owner_cancellation must NOT fire for a player-initiated cancel."""
        player = PlayerUserFactory()
        future_date = datetime.date.today() + datetime.timedelta(days=7)
        slot = SlotFactory(date=future_date, status="available")
        from apps.bookings.models import BookingStatus
        from apps.stadiums.models import SlotStatus

        booking = BookingFactory(player=player, slot=slot, status=BookingStatus.CONFIRMED)
        slot.status = SlotStatus.BOOKED
        slot.save(update_fields=["status", "updated_at"])

        with (
            patch("apps.notifications.tasks.notify_booking_cancelled_by_player.delay"),
            patch(
                "apps.notifications.tasks.notify_player_of_owner_cancellation.delay"
            ) as mock_owner_cancel,
        ):
            cancel_booking(player, booking.pk)

        mock_owner_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# Owner cancellation — player notified
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestOwnerCancellationTrigger:
    """cancel_booking_by_owner → player notified about owner cancellation."""

    def test_owner_cancel_enqueues_player_notification(self):
        owner = OwnerUserFactory()
        stadium = StadiumFactory(owner=owner, active=True)
        slot = SlotFactory(stadium=stadium, status="available")
        from apps.bookings.models import BookingStatus
        from apps.stadiums.models import SlotStatus

        booking = BookingFactory(
            stadium=stadium, slot=slot, status=BookingStatus.CONFIRMED
        )
        slot.status = SlotStatus.BOOKED
        slot.save(update_fields=["status", "updated_at"])

        with patch(
            "apps.notifications.tasks.notify_player_of_owner_cancellation.delay"
        ) as mock_player_cancel:
            cancel_booking_by_owner(owner, booking.pk, reason="Stadium maintenance required.")

        mock_player_cancel.assert_called_once_with(booking.pk)

    def test_owner_cancel_does_not_enqueue_player_cancellation_task(self):
        """notify_booking_cancelled_by_player must NOT fire for an owner-initiated cancel."""
        owner = OwnerUserFactory()
        stadium = StadiumFactory(owner=owner, active=True)
        slot = SlotFactory(stadium=stadium, status="available")
        from apps.bookings.models import BookingStatus
        from apps.stadiums.models import SlotStatus

        booking = BookingFactory(
            stadium=stadium, slot=slot, status=BookingStatus.CONFIRMED
        )
        slot.status = SlotStatus.BOOKED
        slot.save(update_fields=["status", "updated_at"])

        with (
            patch("apps.notifications.tasks.notify_player_of_owner_cancellation.delay"),
            patch(
                "apps.notifications.tasks.notify_booking_cancelled_by_player.delay"
            ) as mock_player_cancel,
        ):
            cancel_booking_by_owner(owner, booking.pk, reason="Unexpected closure.")

        mock_player_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# Stadium approval / rejection — owner notified
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumApprovalTriggers:
    """Admin approve/reject endpoints → owner notification tasks enqueued."""

    def test_approve_stadium_enqueues_owner_notification(self, admin_client):
        stadium = StadiumFactory(pending=True)

        with patch(
            "apps.notifications.tasks.notify_stadium_approved.delay"
        ) as mock_approved:
            response = admin_client.post(f"/api/v1/admin/stadiums/{stadium.pk}/approve/")

        assert response.status_code == 200
        mock_approved.assert_called_once_with(stadium.pk)

    def test_reject_stadium_enqueues_owner_notification(self, admin_client):
        stadium = StadiumFactory(pending=True)

        with patch(
            "apps.notifications.tasks.notify_stadium_rejected.delay"
        ) as mock_rejected:
            response = admin_client.post(
                f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
                data={"rejection_note": "Does not meet safety requirements."},
                format="json",
            )

        assert response.status_code == 200
        mock_rejected.assert_called_once_with(stadium.pk)

    def test_approve_non_pending_stadium_does_not_enqueue_notification(self, admin_client):
        """Attempting to approve an already-active stadium returns 400 and does not notify."""
        stadium = StadiumFactory(active=True)

        with patch(
            "apps.notifications.tasks.notify_stadium_approved.delay"
        ) as mock_approved:
            response = admin_client.post(f"/api/v1/admin/stadiums/{stadium.pk}/approve/")

        assert response.status_code == 400
        mock_approved.assert_not_called()

    def test_reject_non_pending_stadium_does_not_enqueue_notification(self, admin_client):
        """Attempting to reject an already-active stadium returns 400 and does not notify."""
        stadium = StadiumFactory(active=True)

        with patch(
            "apps.notifications.tasks.notify_stadium_rejected.delay"
        ) as mock_rejected:
            response = admin_client.post(
                f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
                data={"rejection_note": "Already approved, cannot reject."},
                format="json",
            )

        assert response.status_code == 400
        mock_rejected.assert_not_called()
