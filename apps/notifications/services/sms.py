"""SMS gateway abstraction — provider is swappable with zero code changes."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class SMSError(Exception):
    """Raised for transient SMS errors that should trigger a Celery retry."""


def _send_via_twilio(phone: str, message: str) -> bool:
    """Send an SMS using Twilio."""
    account_sid: str = settings.TWILIO_ACCOUNT_SID
    if not account_sid:
        logger.warning(
            "TWILIO_ACCOUNT_SID is not set — skipping SMS to %s.",
            phone,
        )
        return False

    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client

    try:
        client = Client(account_sid, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=phone,
        )
        logger.debug("SMS sent via Twilio. SID: %s", msg.sid)
        return True
    except TwilioRestException as exc:
        logger.warning("Twilio error sending SMS to %s: %s", phone, exc)
        raise SMSError(str(exc)) from exc


def send_sms(phone: str, message: str) -> bool:
    """Send an SMS. Provider determined by settings.SMS_PROVIDER.

    Returns True on success, False on failure.
    Raises SMSError for errors that should trigger task retry.
    """
    provider: str = settings.SMS_PROVIDER

    if provider == "twilio":
        return _send_via_twilio(phone, message)

    logger.warning(
        "Unknown SMS_PROVIDER '%s' — no SMS sent to %s. "
        "Add a handler branch in sms.py when this provider is ready.",
        provider,
        phone,
    )
    return False
