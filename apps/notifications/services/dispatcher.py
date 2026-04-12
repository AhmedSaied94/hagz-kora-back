"""Notification channel routing by notification type."""

from __future__ import annotations

import enum


class NotificationType(str, enum.Enum):
    BOOKING_CONFIRMED_PLAYER = "booking_confirmed_player"
    BOOKING_CONFIRMED_OWNER = "booking_confirmed_owner"
    BOOKING_CANCELLED_BY_PLAYER = "booking_cancelled_player"
    BOOKING_CANCELLED_BY_OWNER = "booking_cancelled_owner"
    STADIUM_APPROVED = "stadium_approved"
    STADIUM_REJECTED = "stadium_rejected"


# Maps each notification type to (send_push, send_sms).
CHANNELS: dict[NotificationType, tuple[bool, bool]] = {
    NotificationType.BOOKING_CONFIRMED_PLAYER: (True, True),
    NotificationType.BOOKING_CONFIRMED_OWNER: (True, True),
    NotificationType.BOOKING_CANCELLED_BY_PLAYER: (True, False),
    NotificationType.BOOKING_CANCELLED_BY_OWNER: (True, True),
    NotificationType.STADIUM_APPROVED: (True, True),
    NotificationType.STADIUM_REJECTED: (True, True),
}


def get_channels(notification_type: NotificationType) -> tuple[bool, bool]:
    """Return (should_push, should_sms) for a given notification type."""
    return CHANNELS[notification_type]
