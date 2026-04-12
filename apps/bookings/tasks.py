"""Celery tasks for the bookings app."""

from __future__ import annotations

import logging

from django.db import OperationalError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="bookings")
def mark_completed_bookings(self) -> dict:
    """
    Mark all confirmed bookings whose slot has ended as completed.

    Schedule: every hour via django-celery-beat.
    Logic: Booking.status=confirmed + slot end datetime < now (Africa/Cairo).
    Uses queryset.update() for efficiency — no signals triggered (none needed).
    Returns: {"completed": <count>}
    """
    now_local = timezone.localtime(timezone.now())  # Africa/Cairo
    today = now_local.date()
    time_now = now_local.time()

    try:
        with transaction.atomic():
            updated_count = (
                Booking.objects.filter(
                    status=BookingStatus.CONFIRMED,
                )
                .filter(Q(slot__date__lt=today) | Q(slot__date=today, slot__end_time__lt=time_now))
                .select_related("slot")
                .update(status=BookingStatus.COMPLETED)
            )
    except OperationalError as exc:
        logger.warning("mark_completed_bookings: transient DB error, retrying. exc=%s", exc)
        raise self.retry(exc=exc) from exc

    logger.info("mark_completed_bookings: marked %d booking(s) as completed.", updated_count)
    return {"completed": updated_count}
