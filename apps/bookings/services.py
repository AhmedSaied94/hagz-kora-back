"""Booking service layer — atomic reservation of a stadium slot.

The critical section is protected by:
  1. A Redis lock (advisory, short-circuits concurrent requests early).
  2. A DB row lock via SELECT ... FOR UPDATE on the Slot row.
  3. A partial UniqueConstraint on Booking(slot, status='confirmed') that
     is the final source of truth — any IntegrityError there is surfaced
     as SlotNotAvailable.
"""

from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.auth_users.models import User
from apps.bookings.exceptions import BookingNotCancellable, SlotNotAvailable, StadiumInactive
from apps.bookings.locking import booking_slot_lock
from apps.bookings.models import Booking, BookingStatus
from apps.stadiums.models import Slot, SlotStatus, StadiumStatus

logger = logging.getLogger(__name__)

TWO = Decimal("2")


def _enqueue_notifications(booking_id: int) -> None:
    """Enqueue post-booking notification tasks.

    TODO(Phase 4 — notifications): wire to Celery tasks once they land.
    For now this is a no-op placeholder; callers schedule it via
    transaction.on_commit so enqueueing only happens after the DB commit.
    """
    logger.debug("Booking %s committed — notifications to be enqueued (Phase 4).", booking_id)


def create_booking(user: User, slot_id: int) -> Booking:
    """Atomically create a confirmed booking for `user` on `slot_id`.

    Raises:
        SlotNotAvailable — slot does not exist, is booked, or is blocked.
        LockAcquisitionFailed — another request is currently booking this slot.
        BookingLockUnavailable — Redis is unreachable.
        StadiumInactive — stadium is not in the 'active' state.
    """
    # 1. Cheap pre-check before paying for a Redis lock / DB row lock.
    preview = (
        Slot.objects.select_related("stadium")
        .filter(pk=slot_id)
        .only("id", "status", "stadium__status")
        .first()
    )
    if preview is None or preview.status != SlotStatus.AVAILABLE:
        raise SlotNotAvailable(f"Slot {slot_id} is not available.")
    if preview.stadium.status != StadiumStatus.ACTIVE:
        raise StadiumInactive(f"Stadium {preview.stadium_id} is not active.")

    # 2. Redis-locked critical section.
    with booking_slot_lock(slot_id, user.id):
        try:
            with transaction.atomic():
                slot = Slot.objects.select_for_update().select_related("stadium").get(pk=slot_id)

                if slot.status != SlotStatus.AVAILABLE:
                    raise SlotNotAvailable(f"Slot {slot_id} is not available.")
                if slot.stadium.status != StadiumStatus.ACTIVE:
                    raise StadiumInactive(f"Stadium {slot.stadium_id} is not active.")

                price = slot.stadium.price_per_slot
                deposit = (price / TWO).quantize(Decimal("0.01"))

                booking = Booking.objects.create(
                    player=user,
                    slot=slot,
                    stadium=slot.stadium,
                    status=BookingStatus.CONFIRMED,
                    price_at_booking=price,
                    deposit_amount=deposit,
                )

                slot.status = SlotStatus.BOOKED
                slot.save(update_fields=["status", "updated_at"])

                transaction.on_commit(lambda bid=booking.id: _enqueue_notifications(bid))
        except IntegrityError as exc:
            # Partial UniqueConstraint tripped — another worker beat us
            # past the DB row lock (should be impossible under the Redis
            # lock, but the constraint is the final source of truth).
            raise SlotNotAvailable(f"Slot {slot_id} is not available.") from exc

    return booking


def cancel_booking(user: User, booking_id: int) -> Booking:
    """Cancel a confirmed booking by the player who made it.

    Sets is_late_cancellation=True if the slot starts within 2 hours of now.
    Rolls Slot.status back to 'available'.
    Both changes are committed atomically.

    Raises:
        Booking.DoesNotExist — booking not found or does not belong to user.
        BookingNotCancellable — booking is not in 'confirmed' status.
    """
    with transaction.atomic():
        # Scope to this player so another player gets a 404, not a 403.
        booking = (
            Booking.objects.select_for_update()
            .select_related("slot")
            .get(pk=booking_id, player=user)
        )

        if booking.status != BookingStatus.CONFIRMED:
            raise BookingNotCancellable(
                f"Booking {booking_id} cannot be cancelled — current status: {booking.status}."
            )

        slot = booking.slot

        # Determine late-cancellation: <= 2 hours until slot start.
        slot_start = timezone.make_aware(
            datetime.datetime.combine(slot.date, slot.start_time),
            timezone.get_current_timezone(),
        )
        hours_until = (slot_start - timezone.now()).total_seconds() / 3600
        is_late = hours_until <= 2

        booking.status = BookingStatus.CANCELLED_BY_PLAYER
        booking.is_late_cancellation = is_late
        booking.cancelled_by = user
        booking.save(update_fields=["status", "is_late_cancellation", "cancelled_by", "updated_at"])

        slot.status = SlotStatus.AVAILABLE
        slot.save(update_fields=["status", "updated_at"])

    return booking


def cancel_booking_by_owner(owner: User, booking_id: int, reason: str) -> Booking:
    """Owner cancels a confirmed booking for one of their stadiums.

    No time restriction. reason is required (min 5 chars enforced at serializer
    level; service raises ValueError if empty as a second line of defence).
    Rolls Slot.status back to available.
    Enqueues player notification via Celery (transaction.on_commit).

    Raises:
        Booking.DoesNotExist — booking not found or not in owner's stadiums.
        BookingNotCancellable — booking is not in 'confirmed' status.
        ValueError — reason is empty.
    """
    if not reason or not reason.strip():
        raise ValueError("cancellation_reason is required.")

    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("slot", "stadium")
            .get(pk=booking_id, stadium__owner=owner, status=BookingStatus.CONFIRMED)
        )

        booking.status = BookingStatus.CANCELLED_BY_OWNER
        booking.cancelled_by = owner
        booking.cancellation_reason = reason
        booking.save(update_fields=["status", "cancelled_by", "cancellation_reason", "updated_at"])

        slot = booking.slot
        slot.status = SlotStatus.AVAILABLE
        slot.save(update_fields=["status", "updated_at"])

        transaction.on_commit(lambda bid=booking.id: _enqueue_owner_cancellation_notification(bid))

    return booking


def _enqueue_owner_cancellation_notification(booking_id: int) -> None:
    """Enqueue player notification after an owner cancellation.

    Deferred import avoids circular imports between services and tasks.
    """
    from apps.notifications.tasks import notify_player_of_owner_cancellation

    notify_player_of_owner_cancellation.delay(booking_id)
