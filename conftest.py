"""
Root conftest.py — fixtures available to all tests across all apps.

Scope hierarchy:
  session  → set up once for the entire test run (e.g., reusable DB state)
  module   → set up once per test module
  function → set up/torn down around each test (default)

Factories live in tests/factories.py; import them here as fixtures so
individual test files never import factories directly.
"""

import pytest
from django.test import RequestFactory as DjangoRequestFactory
from rest_framework.test import APIClient
from tests.factories import (
    AdminUserFactory,
    DeviceTokenFactory,
    OwnerProfileFactory,
    OwnerUserFactory,
    PlayerProfileFactory,
    PlayerUserFactory,
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTTP clients
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    """Unauthenticated DRF APIClient."""
    return APIClient()


@pytest.fixture
def request_factory():
    """Django RequestFactory for unit-testing views directly."""
    return DjangoRequestFactory()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@pytest.fixture
def player(db):
    """A saved Player user."""
    return PlayerUserFactory()


@pytest.fixture
def owner(db):
    """A saved Owner user (pending KYC by default)."""
    return OwnerUserFactory()


@pytest.fixture
def admin_user(db):
    """A saved Admin user."""
    return AdminUserFactory()


# ---------------------------------------------------------------------------
# Authenticated clients
# ---------------------------------------------------------------------------


@pytest.fixture
def player_client(player):
    """APIClient authenticated as a player."""
    client = APIClient()
    client.force_authenticate(user=player)
    return client


@pytest.fixture
def owner_client(owner):
    """APIClient authenticated as an owner."""
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def admin_client(admin_user):
    """APIClient authenticated as an admin."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@pytest.fixture
def player_profile(player):
    """PlayerProfile for the player fixture."""
    return PlayerProfileFactory(user=player)


@pytest.fixture
def owner_profile(owner):
    """OwnerProfile for the owner fixture."""
    return OwnerProfileFactory(user=owner)


@pytest.fixture
def kyc_approved_owner(db):
    """An owner whose KYC has been approved."""
    return OwnerUserFactory(kyc_approved=True)


@pytest.fixture
def device_token(player):
    """A DeviceToken associated with the player fixture."""
    return DeviceTokenFactory(user=player)
