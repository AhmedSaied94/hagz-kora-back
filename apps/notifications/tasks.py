"""Celery tasks for the notifications app."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


# ============================================================================
# Low-level primitive tasks
# ============================================================================


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def send_push_to_user(
    self,
    user_id: int,
    title_ar: str,
    title_en: str,
    body_ar: str,
    body_en: str,
    data: dict | None = None,
) -> dict:
    """Send push to ALL active device tokens for a user.

    Selects title/body based on device language:
    - ar → title_ar / body_ar
    - en → title_en / body_en

    Returns {"sent": N, "failed": M}.
    Retries on FCMError (transient failures).
    """
    from apps.notifications.models import DeviceToken
    from apps.notifications.services.fcm import FCMError, send_push

    tokens = list(
        DeviceToken.objects.filter(user_id=user_id, is_active=True).values_list("token", "language")
    )

    sent = 0
    failed = 0
    last_transient_exc: FCMError | None = None

    for token, language in tokens:
        title = title_ar if language == DeviceToken.Language.AR else title_en
        body = body_ar if language == DeviceToken.Language.AR else body_en

        try:
            success = send_push(token=token, title=title, body=body, data=data)
            if success:
                sent += 1
            else:
                # Token is dead (UnregisteredError / SenderIdMismatchError) — deactivate it.
                DeviceToken.objects.filter(token=token).update(is_active=False)
                failed += 1
        except FCMError as exc:
            logger.warning("FCM error sending to token %s…: %s", token[:20], exc)
            failed += 1
            last_transient_exc = exc  # record but finish the loop

    logger.info("send_push_to_user(user_id=%s): sent=%s, failed=%s", user_id, sent, failed)

    # Only retry if every token failed due to transient errors (nothing got through).
    if sent == 0 and last_transient_exc is not None:
        raise self.retry(exc=last_transient_exc) from last_transient_exc

    return {"sent": sent, "failed": failed}


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def send_sms_to_user(self, user_id: int, message_ar: str) -> bool:
    """Send SMS to user's phone number. Always Arabic.

    Returns True on success.
    Retries on SMSError (transient failures).
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.services.sms import SMSError, send_sms

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(f"send_sms_to_user: user {user_id} not found")
        return False

    try:
        success = send_sms(phone=user.phone, message=message_ar)
        logger.info("send_sms_to_user(user_id=%s): success=%s", user_id, success)
        return success
    except SMSError as exc:
        masked = f"{user.phone[:3]}****{user.phone[-2:]}" if user.phone else "unknown"
        logger.warning("SMS error sending to %s: %s", masked, exc)
        raise self.retry(exc=exc) from exc


# ============================================================================
# Event tasks
# ============================================================================


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_booking_confirmed_player(self, booking_id: int) -> None:
    """Notify the player that their booking has been confirmed.

    Channels: FCM + SMS.
    """
    from apps.bookings.models import Booking

    try:
        booking = Booking.objects.select_related("slot", "stadium", "player").get(pk=booking_id)
    except Booking.DoesNotExist:
        logger.warning(f"notify_booking_confirmed_player: booking {booking_id} not found")
        return

    slot = booking.slot
    stadium = booking.stadium
    player = booking.player

    title_ar = "تم تأكيد حجزك"
    title_en = "Booking Confirmed"
    body_ar = f"ملعب {stadium.name_ar} - {slot.date} {slot.start_time}"
    body_en = f"{stadium.name_en} - {slot.date} {slot.start_time}"

    send_push_to_user.delay(
        user_id=player.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )
    send_sms_to_user.delay(user_id=player.id, message_ar=body_ar)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_booking_confirmed_owner(self, booking_id: int) -> None:
    """Notify the stadium owner that a new booking has been confirmed.

    Channels: FCM + SMS.
    """
    from apps.bookings.models import Booking

    try:
        booking = Booking.objects.select_related("slot", "stadium__owner", "player").get(
            pk=booking_id
        )
    except Booking.DoesNotExist:
        logger.warning(f"notify_booking_confirmed_owner: booking {booking_id} not found")
        return

    slot = booking.slot
    stadium = booking.stadium
    owner = stadium.owner

    title_ar = "حجز جديد"
    title_en = "New Booking"
    body_ar = f"حجز جديد لـ {stadium.name_ar} - {slot.date} {slot.start_time}"
    body_en = f"New booking for {stadium.name_en} - {slot.date} {slot.start_time}"

    send_push_to_user.delay(
        user_id=owner.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )
    send_sms_to_user.delay(user_id=owner.id, message_ar=body_ar)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_booking_cancelled_by_player(self, booking_id: int) -> None:
    """Notify the stadium owner that a player has cancelled their booking.

    Channel: FCM only.
    """
    from apps.bookings.models import Booking

    try:
        booking = Booking.objects.select_related("slot", "stadium__owner", "player").get(
            pk=booking_id
        )
    except Booking.DoesNotExist:
        logger.warning(f"notify_booking_cancelled_by_player: booking {booking_id} not found")
        return

    slot = booking.slot
    stadium = booking.stadium
    owner = stadium.owner

    title_ar = "إلغاء حجز"
    title_en = "Booking Cancelled"
    body_ar = f"تم إلغاء حجز {stadium.name_ar} - {slot.date} {slot.start_time}"
    body_en = f"Booking cancelled for {stadium.name_en} - {slot.date}"

    send_push_to_user.delay(
        user_id=owner.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_player_of_owner_cancellation(self, booking_id: int) -> None:
    """Notify the player that the owner has cancelled their booking.

    Channels: FCM + SMS.
    """
    from apps.bookings.models import Booking

    try:
        booking = Booking.objects.select_related("slot", "stadium", "player").get(pk=booking_id)
    except Booking.DoesNotExist:
        logger.warning(f"notify_player_of_owner_cancellation: booking {booking_id} not found")
        return

    slot = booking.slot
    stadium = booking.stadium
    player = booking.player

    title_ar = "تم إلغاء حجزك"
    title_en = "Booking Cancelled"
    body_ar = f"ألغى المالك حجز {stadium.name_ar} - {slot.date}"
    body_en = f"Owner cancelled booking for {stadium.name_en} - {slot.date}"

    send_push_to_user.delay(
        user_id=player.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )
    send_sms_to_user.delay(user_id=player.id, message_ar=body_ar)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_stadium_approved(self, stadium_id: int) -> None:
    """Notify the stadium owner that their stadium has been approved.

    Channels: FCM + SMS.
    """
    from apps.stadiums.models import Stadium

    try:
        stadium = Stadium.objects.select_related("owner").get(pk=stadium_id)
    except Stadium.DoesNotExist:
        logger.warning(f"notify_stadium_approved: stadium {stadium_id} not found")
        return

    owner = stadium.owner

    title_ar = "تمت الموافقة على ملعبك"
    title_en = "Stadium Approved"
    body_ar = f"تمت الموافقة على {stadium.name_ar} وهو الآن نشط"
    body_en = f"{stadium.name_en} has been approved and is now active"

    send_push_to_user.delay(
        user_id=owner.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )
    send_sms_to_user.delay(user_id=owner.id, message_ar=body_ar)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="notifications")
def notify_stadium_rejected(self, stadium_id: int) -> None:
    """Notify the stadium owner that their stadium has been rejected.

    Channels: FCM + SMS.
    """
    from apps.stadiums.models import Stadium

    try:
        stadium = Stadium.objects.select_related("owner").get(pk=stadium_id)
    except Stadium.DoesNotExist:
        logger.warning(f"notify_stadium_rejected: stadium {stadium_id} not found")
        return

    owner = stadium.owner

    title_ar = "تم رفض ملعبك"
    title_en = "Stadium Rejected"
    note = (stadium.rejection_note or "")[:160]
    body_ar = f"تم رفض {stadium.name_ar}. السبب: {note}"
    body_en = f"{stadium.name_en} was rejected. Reason: {note}"

    send_push_to_user.delay(
        user_id=owner.id,
        title_ar=title_ar,
        title_en=title_en,
        body_ar=body_ar,
        body_en=body_en,
    )
    send_sms_to_user.delay(user_id=owner.id, message_ar=body_ar)
