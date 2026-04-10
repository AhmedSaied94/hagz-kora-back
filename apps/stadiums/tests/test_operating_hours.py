"""
Integration tests for operating hours GET/PUT endpoint.
"""

import pytest
from tests.factories import OperatingHourFactory, StadiumFactory

from apps.stadiums.models import OperatingHour


@pytest.mark.integration
@pytest.mark.django_db
class TestOperatingHoursGet:
    def test_owner_gets_operating_hours(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        OperatingHourFactory(stadium=stadium, day_of_week=0)
        OperatingHourFactory(stadium=stadium, day_of_week=1, is_closed=True)

        resp = owner_client.get(f"/api/v1/stadiums/{stadium.pk}/operating-hours/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_empty_list_when_no_hours_set(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        resp = owner_client.get(f"/api/v1/stadiums/{stadium.pk}/operating-hours/")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.integration
@pytest.mark.django_db
class TestOperatingHoursPut:
    def test_bulk_replace_operating_hours(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        payload = [
            {"day_of_week": 0, "open_time": "08:00:00", "close_time": "22:00:00", "is_closed": False},
            {"day_of_week": 5, "open_time": None, "close_time": None, "is_closed": True},
        ]
        resp = owner_client.put(
            f"/api/v1/stadiums/{stadium.pk}/operating-hours/",
            data=payload,
            format="json",
        )
        assert resp.status_code == 200
        assert OperatingHour.objects.filter(stadium=stadium).count() == 2

    def test_replaces_existing_hours(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        OperatingHourFactory(stadium=stadium, day_of_week=0)
        OperatingHourFactory(stadium=stadium, day_of_week=1)

        payload = [
            {"day_of_week": 3, "open_time": "10:00:00", "close_time": "20:00:00", "is_closed": False},
        ]
        resp = owner_client.put(
            f"/api/v1/stadiums/{stadium.pk}/operating-hours/",
            data=payload,
            format="json",
        )
        assert resp.status_code == 200
        remaining = OperatingHour.objects.filter(stadium=stadium)
        assert remaining.count() == 1
        assert remaining.first().day_of_week == 3

    def test_rejects_invalid_hours_open_without_close(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        payload = [
            {"day_of_week": 0, "open_time": "08:00:00", "close_time": None, "is_closed": False},
        ]
        resp = owner_client.put(
            f"/api/v1/stadiums/{stadium.pk}/operating-hours/",
            data=payload,
            format="json",
        )
        assert resp.status_code == 400

    def test_rejects_non_list_payload(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner)
        resp = owner_client.put(
            f"/api/v1/stadiums/{stadium.pk}/operating-hours/",
            data={"day_of_week": 0},
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_access_other_owner_stadium(self, owner_client):
        from tests.factories import OwnerUserFactory
        other = OwnerUserFactory()
        stadium = StadiumFactory(owner=other)
        resp = owner_client.get(f"/api/v1/stadiums/{stadium.pk}/operating-hours/")
        assert resp.status_code == 404
