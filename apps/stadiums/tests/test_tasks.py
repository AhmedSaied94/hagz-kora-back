"""
Unit tests for Celery tasks.
"""

import datetime

import pytest
from tests.factories import OperatingHourFactory, StadiumFactory

from apps.stadiums.models import Slot, StadiumStatus
from apps.stadiums.tasks import _create_slots_for_day, _generate_slots_for_stadium


@pytest.mark.integration
@pytest.mark.django_db
class TestSlotGenerationHelpers:
    def test_create_slots_fills_entire_day(self):
        """_create_slots_for_day creates all slots between open and close."""
        from unittest.mock import MagicMock

        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=60)
        oh = MagicMock()
        oh.open_time = datetime.time(8, 0)
        oh.close_time = datetime.time(10, 0)

        slot_date = datetime.date(2025, 6, 1)
        count = _create_slots_for_day(stadium, slot_date, oh)
        assert count == 2  # 08:00 and 09:00

    def test_create_slots_for_30_min_duration(self):
        """30-minute slots double the count."""
        from unittest.mock import MagicMock

        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=30)
        oh = MagicMock()
        oh.open_time = datetime.time(8, 0)
        oh.close_time = datetime.time(10, 0)

        slot_date = datetime.date(2025, 6, 1)
        count = _create_slots_for_day(stadium, slot_date, oh)
        assert count == 4  # 08:00, 08:30, 09:00, 09:30


@pytest.mark.integration
@pytest.mark.django_db
class TestGenerateSlotsForAllStadiums:
    def test_task_creates_slots_for_active_stadiums(self):
        from apps.stadiums.tasks import generate_slots_for_all_stadiums

        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=60)
        OperatingHourFactory(
            stadium=stadium,
            day_of_week=0,
            open_time=datetime.time(8, 0),
            close_time=datetime.time(9, 0),
            is_closed=False,
        )
        result = generate_slots_for_all_stadiums.apply().get()
        assert result["created"] >= 1

    def test_task_ignores_inactive_stadiums(self):
        from apps.stadiums.tasks import generate_slots_for_all_stadiums

        StadiumFactory(status=StadiumStatus.DRAFT, slot_duration_minutes=60)
        result = generate_slots_for_all_stadiums.apply().get()
        assert result["created"] == 0


@pytest.mark.integration
@pytest.mark.django_db
class TestGenerateSlotsForStadium:
    def test_generates_slots_for_open_days(self):
        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=60)
        # Monday open 08-10 (generates 2 slots per Monday in range)
        OperatingHourFactory(
            stadium=stadium,
            day_of_week=0,
            open_time=datetime.time(8, 0),
            close_time=datetime.time(10, 0),
            is_closed=False,
        )
        start = datetime.date(2025, 6, 2)   # Monday
        end = datetime.date(2025, 6, 9)     # next Monday (exclusive)

        created = _generate_slots_for_stadium(stadium, start, end)
        assert created == 2
        assert Slot.objects.filter(stadium=stadium).count() == 2

    def test_skips_closed_days(self):
        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=60)
        OperatingHourFactory(
            stadium=stadium,
            day_of_week=0,
            is_closed=True,
        )
        start = datetime.date(2025, 6, 2)
        end = datetime.date(2025, 6, 9)

        created = _generate_slots_for_stadium(stadium, start, end)
        assert created == 0

    def test_idempotent_does_not_duplicate(self):
        stadium = StadiumFactory(status=StadiumStatus.ACTIVE, slot_duration_minutes=60)
        oh = OperatingHourFactory(
            stadium=stadium,
            day_of_week=0,
            open_time=datetime.time(8, 0),
            close_time=datetime.time(10, 0),
            is_closed=False,
        )
        start = datetime.date(2025, 6, 2)
        end = datetime.date(2025, 6, 9)

        _generate_slots_for_stadium(stadium, start, end)
        # Run again — should not create duplicates
        created_second_run = _generate_slots_for_stadium(stadium, start, end)

        assert created_second_run == 0
        assert Slot.objects.filter(stadium=stadium).count() == 2
