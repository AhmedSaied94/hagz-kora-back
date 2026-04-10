"""
Integration tests for Phase 1 auth endpoints.

Covers:
  - Email register / login (DJANGO_AUTH_BACKEND=email)
  - OTP request / verify flow
  - JWT token refresh
  - Logout (blacklist)
  - Player profile GET / PATCH
  - Owner register / profile GET / PATCH
  - FCM device token register / deregister
"""

import pytest
from apps.auth_users.models import KycStatus, OwnerProfile, PlayerProfile
from apps.auth_users.otp import generate_otp
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from tests.factories import (
    DeviceTokenFactory,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ── Email register ────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_email_register_creates_player_and_returns_jwt(api_client):
    url = reverse("auth-register")
    payload = {
        "email": "newplayer@example.com",
        "password": "StrongPass123!",
        "full_name": "Ahmed Ali",
        "phone": "+201011112222",
        "role": "player",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    assert data["role"] == "player"
    assert data["full_name"] == "Ahmed Ali"


@pytest.mark.integration
@pytest.mark.django_db
def test_email_register_duplicate_email_returns_400(api_client, player):
    url = reverse("auth-register")
    payload = {
        "email": player.email,
        "password": "StrongPass123!",
        "full_name": "Another User",
    }
    response = api_client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.django_db
def test_email_register_duplicate_phone_returns_400(api_client, player):
    url = reverse("auth-register")
    payload = {
        "email": "unique@example.com",
        "password": "StrongPass123!",
        "full_name": "Another User",
        "phone": player.phone,
    }
    response = api_client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Email login ───────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_email_login_returns_jwt(api_client, player):
    url = reverse("auth-login")
    response = api_client.post(
        url,
        {"email": player.email, "password": "TestPass123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.json()


@pytest.mark.integration
@pytest.mark.django_db
def test_email_login_wrong_password_returns_400(api_client, player):
    url = reverse("auth-login")
    response = api_client.post(
        url,
        {"email": player.email, "password": "WrongPassword!"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.django_db
def test_email_login_unknown_email_returns_400(api_client):
    url = reverse("auth-login")
    response = api_client.post(
        url,
        {"email": "nobody@example.com", "password": "TestPass123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── OTP flow ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_otp_request_returns_200(api_client):
    url = reverse("otp-request")
    response = api_client.post(url, {"phone": "+201011112233"}, format="json")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
@pytest.mark.django_db
def test_otp_verify_creates_user_and_returns_jwt(api_client):
    phone = "+201011119999"
    otp = generate_otp(phone)

    url = reverse("otp-verify")
    response = api_client.post(url, {"phone": phone, "otp": otp}, format="json")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access" in data
    assert data["role"] == "player"


@pytest.mark.integration
@pytest.mark.django_db
def test_otp_verify_wrong_otp_returns_400(api_client):
    phone = "+201011118888"
    generate_otp(phone)

    url = reverse("otp-verify")
    response = api_client.post(url, {"phone": phone, "otp": "000000"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.django_db
def test_otp_verify_expired_returns_400(api_client):
    url = reverse("otp-verify")
    response = api_client.post(url, {"phone": "+201011117777", "otp": "123456"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── JWT refresh + logout ──────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_token_refresh_returns_new_access(api_client, player):
    login_url = reverse("auth-login")
    tokens = api_client.post(
        login_url,
        {"email": player.email, "password": "TestPass123!"},
        format="json",
    ).json()

    refresh_url = reverse("token-refresh")
    response = api_client.post(refresh_url, {"refresh": tokens["refresh"]}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.json()


@pytest.mark.integration
@pytest.mark.django_db
def test_logout_blacklists_refresh_token(api_client, player_client, player):
    login_url = reverse("auth-login")
    tokens = api_client.post(
        login_url,
        {"email": player.email, "password": "TestPass123!"},
        format="json",
    ).json()

    logout_url = reverse("logout")
    response = player_client.post(logout_url, {"refresh": tokens["refresh"]}, format="json")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Refresh token is now blacklisted
    refresh_url = reverse("token-refresh")
    response2 = api_client.post(refresh_url, {"refresh": tokens["refresh"]}, format="json")
    assert response2.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.django_db
def test_logout_requires_authentication(api_client):
    url = reverse("logout")
    response = api_client.post(url, {"refresh": "any-token"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Player profile ────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_player_me_get_returns_profile(player_client, player):
    url = reverse("player-me")
    response = player_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["phone"] == player.phone
    assert data["full_name"] == player.full_name


@pytest.mark.integration
@pytest.mark.django_db
def test_player_me_patch_updates_city(player_client, player):
    url = reverse("player-me")
    response = player_client.patch(url, {"city": "Cairo"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["city"] == "Cairo"

    profile = PlayerProfile.objects.get(user=player)
    assert profile.city == "Cairo"


@pytest.mark.integration
@pytest.mark.django_db
def test_player_me_requires_player_role(owner_client):
    url = reverse("player-me")
    response = owner_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.integration
@pytest.mark.django_db
def test_player_me_requires_authentication(api_client):
    url = reverse("player-me")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Owner register ────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_owner_register_creates_owner_and_returns_jwt(api_client):
    url = reverse("owner-register")
    payload = {
        "email": "newowner@example.com",
        "password": "StrongPass123!",
        "full_name": "Mohamed Salah",
        "phone": "+201022223333",
        "business_name_ar": "ملعب النيل",
        "business_name_en": "Nile Pitch",
        "national_id_number": "29901010112345",
        "city": "Cairo",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["role"] == "owner"
    assert OwnerProfile.objects.filter(user__email="newowner@example.com").exists()


# ── Owner profile ─────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_owner_me_get_returns_profile(owner_client, owner, owner_profile):
    url = reverse("owner-me")
    response = owner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["phone"] == owner.phone
    assert data["kyc_status"] == KycStatus.PENDING


@pytest.mark.integration
@pytest.mark.django_db
def test_owner_me_patch_updates_city(owner_client, owner, owner_profile):
    url = reverse("owner-me")
    response = owner_client.patch(url, {"city": "Alexandria"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["city"] == "Alexandria"


@pytest.mark.integration
@pytest.mark.django_db
def test_owner_me_requires_owner_role(player_client):
    url = reverse("owner-me")
    response = player_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Device token ──────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.django_db
def test_register_device_token_returns_201(player_client):
    url = reverse("device-register")
    response = player_client.post(
        url, {"token": "fcm-abc123", "platform": "android"}, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.integration
@pytest.mark.django_db
def test_register_device_token_upserts_on_duplicate(player_client, player):
    url = reverse("device-register")
    player_client.post(url, {"token": "fcm-dupe", "platform": "android"}, format="json")
    response = player_client.post(url, {"token": "fcm-dupe", "platform": "android"}, format="json")
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.integration
@pytest.mark.django_db
def test_deregister_device_token_marks_inactive(player_client, player):
    token = DeviceTokenFactory(user=player, token="fcm-to-delete")
    url = reverse("device-deregister", kwargs={"token": "fcm-to-delete"})
    response = player_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    token.refresh_from_db()
    assert token.is_active is False


@pytest.mark.integration
@pytest.mark.django_db
def test_device_token_requires_authentication(api_client):
    url = reverse("device-register")
    response = api_client.post(url, {"token": "fcm-anon", "platform": "android"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
