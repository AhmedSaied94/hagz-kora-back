"""Unit tests for the notifications service layer.

firebase_admin and twilio are optional production dependencies — not installed
in the local dev environment. All tests use sys.modules mocking so the service
layer can be exercised without the real SDKs present.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared mock error classes (reused across both FCM and SMS test classes)
# ---------------------------------------------------------------------------


class _FakeFirebaseError(Exception):
    """Stand-in for firebase_admin.exceptions.FirebaseError."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        super().__init__(message)


class _FakeUnregisteredError(_FakeFirebaseError):
    """Stand-in for firebase_admin.messaging.UnregisteredError."""

    def __init__(self, message: str = "token unregistered", cause=None) -> None:
        super().__init__(404, message)


class _FakeSenderIdMismatchError(_FakeFirebaseError):
    """Stand-in for firebase_admin.messaging.SenderIdMismatchError."""


class _FakeTwilioRestException(Exception):
    """Stand-in for twilio.base.exceptions.TwilioRestException."""

    def __init__(self, status: int = 400, uri: str = "/Messages", msg: str = "") -> None:
        self.status = status
        self.uri = uri
        super().__init__(msg or f"HTTP {status}")


# ---------------------------------------------------------------------------
# Module-level firebase_admin mock (lazy imports inside send_push reference these)
# ---------------------------------------------------------------------------

_mock_messaging = MagicMock()
_mock_messaging.UnregisteredError = _FakeUnregisteredError
_mock_messaging.SenderIdMismatchError = _FakeSenderIdMismatchError
_mock_messaging.Notification = MagicMock(return_value=MagicMock())
_mock_messaging.Message = MagicMock(return_value=MagicMock())
_mock_messaging.MulticastMessage = MagicMock(return_value=MagicMock())

_mock_exceptions = MagicMock()
_mock_exceptions.FirebaseError = _FakeFirebaseError

_mock_credentials = MagicMock()

_mock_firebase_admin = MagicMock()
_mock_firebase_admin.messaging = _mock_messaging
_mock_firebase_admin.exceptions = _mock_exceptions
_mock_firebase_admin.credentials = _mock_credentials

_FIREBASE_MODULES = {
    "firebase_admin": _mock_firebase_admin,
    "firebase_admin.messaging": _mock_messaging,
    "firebase_admin.exceptions": _mock_exceptions,
    "firebase_admin.credentials": _mock_credentials,
}

# ---------------------------------------------------------------------------
# Module-level twilio mock
# ---------------------------------------------------------------------------

_mock_twilio_base_exc = MagicMock()
_mock_twilio_base_exc.TwilioRestException = _FakeTwilioRestException

_mock_twilio_rest = MagicMock()
_MockClient = MagicMock()
_mock_twilio_rest.Client = _MockClient

_TWILIO_MODULES = {
    "twilio": MagicMock(),
    "twilio.rest": _mock_twilio_rest,
    "twilio.base": MagicMock(),
    "twilio.base.exceptions": _mock_twilio_base_exc,
}


# ---------------------------------------------------------------------------
# FCM tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendPush:
    """Tests for apps.notifications.services.fcm.send_push."""

    def test_returns_true_on_success(self):
        _mock_messaging.send.return_value = "projects/test/messages/abc123"

        with patch.dict(sys.modules, _FIREBASE_MODULES):
            with patch("apps.notifications.services.fcm.settings") as mock_settings:
                mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/path/to/creds.json"
                with patch("apps.notifications.services.fcm._get_firebase_app"):
                    from apps.notifications.services.fcm import send_push

                    result = send_push("token_abc", "Hello", "World")

        assert result is True

    def test_returns_false_on_unregistered_error(self):
        _mock_messaging.send.side_effect = _FakeUnregisteredError("token expired")

        with patch.dict(sys.modules, _FIREBASE_MODULES):
            with patch("apps.notifications.services.fcm.settings") as mock_settings:
                mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/path/to/creds.json"
                with patch("apps.notifications.services.fcm._get_firebase_app"):
                    from apps.notifications.services.fcm import send_push

                    result = send_push("dead_token", "Hello", "World")

        assert result is False
        _mock_messaging.send.side_effect = None  # reset

    def test_raises_fcm_error_on_other_firebase_error(self):
        _mock_messaging.send.side_effect = _FakeFirebaseError(500, "internal server error")

        with patch.dict(sys.modules, _FIREBASE_MODULES):
            with patch("apps.notifications.services.fcm.settings") as mock_settings:
                mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/path/to/creds.json"
                with patch("apps.notifications.services.fcm._get_firebase_app"):
                    from apps.notifications.services.fcm import FCMError, send_push

                    with pytest.raises(FCMError):
                        send_push("token_abc", "Hello", "World")

        _mock_messaging.send.side_effect = None  # reset

    def test_returns_false_when_credentials_empty(self):
        with patch("apps.notifications.services.fcm.settings") as mock_settings:
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = ""
            from apps.notifications.services.fcm import send_push

            result = send_push("token_abc", "Hello", "World")

        assert result is False


# ---------------------------------------------------------------------------
# SMS tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendSms:
    """Tests for apps.notifications.services.sms.send_sms."""

    def test_returns_true_on_twilio_success(self):
        mock_message = MagicMock()
        mock_message.sid = "SM123"
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.return_value = mock_message
        _MockClient.return_value = mock_client_instance

        with patch.dict(sys.modules, _TWILIO_MODULES):
            with patch("apps.notifications.services.sms.settings") as mock_settings:
                mock_settings.SMS_PROVIDER = "twilio"
                mock_settings.TWILIO_ACCOUNT_SID = "ACtest"
                mock_settings.TWILIO_AUTH_TOKEN = "auth_token"
                mock_settings.TWILIO_FROM_NUMBER = "+10000000000"

                from apps.notifications.services.sms import send_sms

                result = send_sms("+201001234567", "Test message")

        assert result is True
        mock_client_instance.messages.create.assert_called_once_with(
            body="Test message",
            from_="+10000000000",
            to="+201001234567",
        )

    def test_raises_sms_error_on_twilio_exception(self):
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = _FakeTwilioRestException(
            status=400, uri="/Messages"
        )
        _MockClient.return_value = mock_client_instance

        with patch.dict(sys.modules, _TWILIO_MODULES):
            with patch("apps.notifications.services.sms.settings") as mock_settings:
                mock_settings.SMS_PROVIDER = "twilio"
                mock_settings.TWILIO_ACCOUNT_SID = "ACtest"
                mock_settings.TWILIO_AUTH_TOKEN = "auth_token"
                mock_settings.TWILIO_FROM_NUMBER = "+10000000000"

                from apps.notifications.services.sms import SMSError, send_sms

                with pytest.raises(SMSError):
                    send_sms("+201001234567", "Test message")

    def test_returns_false_when_account_sid_empty(self):
        with patch("apps.notifications.services.sms.settings") as mock_settings:
            mock_settings.SMS_PROVIDER = "twilio"
            mock_settings.TWILIO_ACCOUNT_SID = ""

            from apps.notifications.services.sms import send_sms

            result = send_sms("+201001234567", "Test message")

        assert result is False

    def test_returns_false_for_unknown_provider(self):
        with patch("apps.notifications.services.sms.settings") as mock_settings:
            mock_settings.SMS_PROVIDER = "unknown_provider"
            mock_settings.TWILIO_ACCOUNT_SID = "ACtest"

            from apps.notifications.services.sms import send_sms

            result = send_sms("+201001234567", "Test message")

        assert result is False


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetChannels:
    """Tests for apps.notifications.services.dispatcher.get_channels."""

    def test_booking_confirmed_player_push_and_sms(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.BOOKING_CONFIRMED_PLAYER)
        assert should_push is True
        assert should_sms is True

    def test_booking_confirmed_owner_push_and_sms(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.BOOKING_CONFIRMED_OWNER)
        assert should_push is True
        assert should_sms is True

    def test_booking_cancelled_by_player_push_only(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.BOOKING_CANCELLED_BY_PLAYER)
        assert should_push is True
        assert should_sms is False

    def test_booking_cancelled_by_owner_push_and_sms(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.BOOKING_CANCELLED_BY_OWNER)
        assert should_push is True
        assert should_sms is True

    def test_stadium_approved_push_and_sms(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.STADIUM_APPROVED)
        assert should_push is True
        assert should_sms is True

    def test_stadium_rejected_push_and_sms(self):
        from apps.notifications.services.dispatcher import NotificationType, get_channels

        should_push, should_sms = get_channels(NotificationType.STADIUM_REJECTED)
        assert should_push is True
        assert should_sms is True

    def test_all_notification_types_have_channel_mapping(self):
        from apps.notifications.services.dispatcher import CHANNELS, NotificationType

        for notification_type in NotificationType:
            assert notification_type in CHANNELS, f"{notification_type} is missing from CHANNELS"
