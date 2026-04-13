"""Firebase Cloud Messaging wrapper using the Firebase Admin SDK."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class FCMError(Exception):
    """Raised for transient Firebase errors that should trigger a Celery retry."""


def _get_firebase_app():
    """Return the initialized Firebase app, initializing it lazily if needed."""
    import firebase_admin
    from firebase_admin import credentials

    try:
        return firebase_admin.get_app()
    except ValueError:
        # App not yet initialized.
        pass

    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if not cred_path:
        return None

    cred = credentials.Certificate(cred_path)
    return firebase_admin.initialize_app(cred)


def send_push(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> bool:
    """Send a single push notification to one FCM token.

    Returns True on success, False if the token is invalid/expired/unregistered.
    Raises FCMError for network/server errors that should trigger task retry.
    """
    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if not cred_path:
        logger.warning(
            "GOOGLE_APPLICATION_CREDENTIALS is not set — skipping FCM push to token %s.",
            token[:20],
        )
        return False

    try:
        _get_firebase_app()
    except Exception as exc:
        raise FCMError(f"Firebase app initialization failed: {exc}") from exc

    from firebase_admin import messaging
    from firebase_admin.exceptions import FirebaseError

    # FCM requires all data dict values to be strings — enforce at the boundary.
    safe_data: dict[str, str] = {}
    if data:
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise FCMError(
                    f"FCM data dict must contain only str keys and str values; got {k!r}={v!r}"
                )
            safe_data[k] = v

    notification = messaging.Notification(title=title, body=body)
    message = messaging.Message(
        notification=notification,
        token=token,
        data=safe_data,
    )

    try:
        response = messaging.send(message)
        logger.debug("FCM push sent successfully. Message ID: %s", response)
        return True
    except messaging.UnregisteredError:
        logger.debug("FCM token is unregistered/expired: %s…", token[:20])
        return False
    except messaging.SenderIdMismatchError:
        logger.debug("FCM sender ID mismatch for token: %s…", token[:20])
        return False
    except FirebaseError as exc:
        logger.warning("Transient Firebase error for token %s…: %s", token[:20], exc)
        raise FCMError(str(exc)) from exc


def send_push_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> tuple[int, int]:
    """Send to multiple tokens.

    Returns (success_count, failure_count).
    """
    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if not cred_path:
        logger.warning(
            "GOOGLE_APPLICATION_CREDENTIALS is not set — skipping FCM multicast to %d tokens.",
            len(tokens),
        )
        return (0, len(tokens))

    try:
        _get_firebase_app()
    except Exception as exc:
        raise FCMError(f"Firebase app initialization failed: {exc}") from exc

    from firebase_admin import messaging
    from firebase_admin.exceptions import FirebaseError

    # FCM requires all data dict values to be strings — enforce at the boundary.
    safe_data: dict[str, str] = {}
    if data:
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise FCMError(
                    f"FCM data dict must contain only str keys and str values; got {k!r}={v!r}"
                )
            safe_data[k] = v

    notification = messaging.Notification(title=title, body=body)
    multicast_message = messaging.MulticastMessage(
        notification=notification,
        tokens=tokens,
        data=safe_data,
    )

    try:
        batch_response = messaging.send_each_for_multicast(multicast_message)
        success_count: int = batch_response.success_count
        failure_count: int = batch_response.failure_count
        logger.debug(
            "FCM multicast complete. success=%d failure=%d",
            success_count,
            failure_count,
        )
        return (success_count, failure_count)
    except FirebaseError as exc:
        logger.warning("Transient Firebase error during multicast: %s", exc)
        raise FCMError(str(exc)) from exc
