"""Celery tasks for the notifications app."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_player_of_owner_cancellation(self, booking_id: int) -> None:
    """Notify the player that the owner has cancelled their booking.

    TODO(Phase 4 — notifications): implement FCM push + SMS via the
    notifications service once device tokens and SMS provider are wired up.
    Currently a no-op stub so the service layer can already enqueue it.
    """
    logger.debug(
        "notify_player_of_owner_cancellation: booking_id=%s — "
        "notification delivery not yet implemented (Phase 4).",
        booking_id,
    )
