"""
Project-wide factory_boy factories.

Factories are not tied to any single app — they live here so conftest.py
and any test module can import them from one place.

Each phase adds factories for its own models at the bottom of this file.
"""

import factory
from apps.auth_users.models import OwnerProfile, PlayerProfile
from apps.notifications.models import DeviceToken
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


# ---------------------------------------------------------------------------
# Phase 1 — User + Profile factories
# ---------------------------------------------------------------------------


class BaseUserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("phone",)

    phone = factory.Sequence(lambda n: f"+2010{n:08d}")
    email = factory.LazyAttribute(lambda o: f"user_{o.phone[-8:]}@example.com")
    full_name = factory.Faker("name", locale="ar_EG")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "TestPass123!")


class PlayerUserFactory(BaseUserFactory):
    role = "player"


class OwnerUserFactory(BaseUserFactory):
    role = "owner"
    # kyc_status defaults to "pending_kyc" on the model

    class Params:
        kyc_approved = factory.Trait(kyc_status="kyc_approved")


class AdminUserFactory(BaseUserFactory):
    role = "admin"
    is_staff = True
    is_superuser = True


class PlayerProfileFactory(DjangoModelFactory):
    class Meta:
        model = PlayerProfile
        django_get_or_create = ("user",)

    user = factory.SubFactory(PlayerUserFactory)
    city = factory.Faker("city")
    bio = factory.Faker("sentence")


class OwnerProfileFactory(DjangoModelFactory):
    class Meta:
        model = OwnerProfile
        django_get_or_create = ("user",)

    user = factory.SubFactory(OwnerUserFactory)
    business_name_ar = factory.Faker("company")
    business_name_en = factory.Faker("company")
    national_id_number = factory.Sequence(lambda n: f"2900{n:09d}")
    city = factory.Faker("city")


class DeviceTokenFactory(DjangoModelFactory):
    class Meta:
        model = DeviceToken
        django_get_or_create = ("token",)

    user = factory.SubFactory(PlayerUserFactory)
    token = factory.Sequence(lambda n: f"fcm-token-{n:06d}")
    platform = DeviceToken.Platform.ANDROID
    is_active = True
