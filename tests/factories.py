"""
Project-wide factory_boy factories.

Factories are not tied to any single app — they live here so conftest.py
and any test module can import them from one place.

Each phase adds factories for its own models at the bottom of this file.
"""

import datetime

import factory
from apps.auth_users.models import OwnerProfile, PlayerProfile
from apps.notifications.models import DeviceToken
from apps.stadiums.models import (
    OperatingHour,
    Slot,
    SlotStatus,
    Stadium,
    StadiumPhoto,
    StadiumStatus,
)
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
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
    language = DeviceToken.Language.AR


# ---------------------------------------------------------------------------
# Phase 2 — Stadium factories
# ---------------------------------------------------------------------------


class StadiumFactory(DjangoModelFactory):
    class Meta:
        model = Stadium

    owner = factory.SubFactory(OwnerUserFactory)
    name_ar = factory.Sequence(lambda n: f"ملعب {n}")
    name_en = factory.Sequence(lambda n: f"Stadium {n}")
    description_ar = factory.Faker("sentence")
    sport_type = "5v5"
    location = factory.LazyFunction(lambda: Point(31.2357, 30.0444, srid=4326))
    address_ar = factory.Faker("address")
    city = "Cairo"
    price_per_slot = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    slot_duration_minutes = 60
    phone = factory.Sequence(lambda n: f"+2010{n:08d}")
    amenities = factory.LazyFunction(list)
    status = StadiumStatus.DRAFT

    class Params:
        active = factory.Trait(status=StadiumStatus.ACTIVE)
        pending = factory.Trait(status=StadiumStatus.PENDING_REVIEW)


class StadiumPhotoFactory(DjangoModelFactory):
    class Meta:
        model = StadiumPhoto

    stadium = factory.SubFactory(StadiumFactory)
    image = factory.django.ImageField(filename="test_photo.jpg", width=800, height=600)
    thumbnail_url = ""
    medium_url = ""
    order = factory.Sequence(lambda n: n)
    is_cover = False


class OperatingHourFactory(DjangoModelFactory):
    class Meta:
        model = OperatingHour
        django_get_or_create = ("stadium", "day_of_week")

    stadium = factory.SubFactory(StadiumFactory)
    day_of_week = 0  # Monday
    open_time = datetime.time(8, 0)
    close_time = datetime.time(22, 0)
    is_closed = False


class SlotFactory(DjangoModelFactory):
    class Meta:
        model = Slot
        django_get_or_create = ("stadium", "date", "start_time")

    stadium = factory.SubFactory(StadiumFactory, active=True)
    date = factory.LazyFunction(datetime.date.today)
    start_time = datetime.time(10, 0)
    end_time = datetime.time(11, 0)
    status = SlotStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Phase 3 — Booking factories
# ---------------------------------------------------------------------------


class BookingFactory(DjangoModelFactory):
    class Meta:
        model = "bookings.Booking"

    player = factory.SubFactory(PlayerUserFactory)
    slot = factory.SubFactory(SlotFactory)
    stadium = factory.SelfAttribute("slot.stadium")
    status = "confirmed"
    price_at_booking = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    deposit_amount = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


# ---------------------------------------------------------------------------
# Phase 6 — Tournament factories
# ---------------------------------------------------------------------------

from apps.tournaments.models import (
    Fixture,
    FixtureStage,
    FixtureStatus,
    Tournament,
    TournamentFormat,
    TournamentPlayer,
    TournamentStatus,
    TournamentTeam,
)


class TournamentFactory(DjangoModelFactory):
    class Meta:
        model = Tournament

    organizer = factory.SubFactory(OwnerUserFactory)
    name = factory.Sequence(lambda n: f"Tournament {n}")
    format = TournamentFormat.ROUND_ROBIN
    max_teams = 8
    registration_deadline = factory.LazyFunction(
        lambda: datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(days=7)
    )
    start_date = factory.LazyFunction(
        lambda: (datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(days=14)).date()
    )
    status = TournamentStatus.DRAFT
    public_slug = factory.Sequence(lambda n: f"tournament-{n}")

    class Params:
        open = factory.Trait(status=TournamentStatus.REGISTRATION_OPEN)
        in_progress = factory.Trait(status=TournamentStatus.IN_PROGRESS)


class TournamentTeamFactory(DjangoModelFactory):
    class Meta:
        model = TournamentTeam

    tournament = factory.SubFactory(TournamentFactory)
    name = factory.Sequence(lambda n: f"Team {n}")
    captain = factory.SubFactory(PlayerUserFactory)
    join_code = factory.Sequence(lambda n: f"CODE{n:04d}")


class TournamentPlayerFactory(DjangoModelFactory):
    class Meta:
        model = TournamentPlayer

    team = factory.SubFactory(TournamentTeamFactory)
    player = factory.SubFactory(PlayerUserFactory)


class FixtureFactory(DjangoModelFactory):
    class Meta:
        model = Fixture

    tournament = factory.SubFactory(TournamentFactory)
    home_team = factory.SubFactory(TournamentTeamFactory)
    away_team = factory.SubFactory(TournamentTeamFactory)
    round_number = 1
    status = FixtureStatus.SCHEDULED
    stage = FixtureStage.KNOCKOUT
    is_bye = False


# ---------------------------------------------------------------------------
# Phase 7 — Review factories
# ---------------------------------------------------------------------------

from apps.reviews.models import Review


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    booking = factory.SubFactory(BookingFactory)
    player = factory.SelfAttribute("booking.player")
    stadium = factory.SelfAttribute("booking.stadium")
    overall_rating = 4
    text = factory.Faker("sentence")
