"""
Integration tests for Stadium CRUD and submit endpoint (owner-facing).
"""

import pytest
from django.urls import reverse

from apps.stadiums.models import StadiumStatus
from tests.factories import OwnerUserFactory, StadiumFactory, StadiumPhotoFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumList:
    def test_owner_sees_only_own_stadiums(self, owner_client, owner):
        other_owner = OwnerUserFactory()
        own = StadiumFactory(owner=owner)
        StadiumFactory(owner=other_owner)

        resp = owner_client.get("/api/v1/stadiums/")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()["results"]]
        assert own.pk in ids
        assert len(ids) == 1

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get("/api/v1/stadiums/")
        assert resp.status_code == 401

    def test_player_rejected(self, player_client):
        resp = player_client.get("/api/v1/stadiums/")
        assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumCreate:
    def test_owner_creates_draft_stadium(self, owner_client, owner):
        payload = {
            "name_ar": "ملعب الفرسان",
            "name_en": "Al Forsan",
            "sport_type": "5v5",
            "address_ar": "شارع التحرير",
            "city": "Cairo",
            "price_per_slot": "150.00",
            "slot_duration_minutes": 60,
            "phone": "+201012345678",
        }
        resp = owner_client.post("/api/v1/stadiums/", data=payload, format="json")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == StadiumStatus.DRAFT
        assert data["name_ar"] == "ملعب الفرسان"

    def test_creates_with_owner_set_automatically(self, owner_client, owner):
        payload = {
            "name_ar": "ملعب",
            "sport_type": "7v7",
            "address_ar": "شارع",
            "city": "Alex",
            "price_per_slot": "100.00",
            "slot_duration_minutes": 60,
            "phone": "+201098765432",
        }
        resp = owner_client.post("/api/v1/stadiums/", data=payload, format="json")
        assert resp.status_code == 201
        from apps.stadiums.models import Stadium
        stadium = Stadium.objects.get(pk=resp.json()["id"])
        assert stadium.owner == owner


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumUpdate:
    def test_owner_can_patch_draft(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.DRAFT)
        resp = owner_client.patch(
            f"/api/v1/stadiums/{stadium.pk}/",
            data={"name_en": "Updated"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["name_en"] == "Updated"

    def test_cannot_edit_active_stadium(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.ACTIVE)
        resp = owner_client.patch(
            f"/api/v1/stadiums/{stadium.pk}/",
            data={"name_en": "x"},
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_access_other_owner_stadium(self, owner_client):
        other = OwnerUserFactory()
        stadium = StadiumFactory(owner=other)
        resp = owner_client.patch(
            f"/api/v1/stadiums/{stadium.pk}/",
            data={"name_en": "x"},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumDelete:
    def test_owner_can_delete_draft(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.DRAFT)
        resp = owner_client.delete(f"/api/v1/stadiums/{stadium.pk}/")
        assert resp.status_code == 204

    def test_cannot_delete_active(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.ACTIVE)
        resp = owner_client.delete(f"/api/v1/stadiums/{stadium.pk}/")
        assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.django_db
class TestStadiumSubmit:
    def test_submit_transitions_to_pending_review(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.DRAFT)
        # Add a cover photo
        StadiumPhotoFactory(stadium=stadium, is_cover=True)

        resp = owner_client.post(f"/api/v1/stadiums/{stadium.pk}/submit/")
        assert resp.status_code == 200
        assert resp.json()["status"] == StadiumStatus.PENDING_REVIEW

    def test_submit_without_photo_rejected(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.DRAFT)
        resp = owner_client.post(f"/api/v1/stadiums/{stadium.pk}/submit/")
        assert resp.status_code == 400
        assert "photo" in resp.json()["detail"].lower()

    def test_submit_without_cover_photo_rejected(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.DRAFT)
        StadiumPhotoFactory(stadium=stadium, is_cover=False)
        resp = owner_client.post(f"/api/v1/stadiums/{stadium.pk}/submit/")
        assert resp.status_code == 400
        assert "cover" in resp.json()["detail"].lower()

    def test_cannot_submit_non_draft(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status=StadiumStatus.ACTIVE)
        StadiumPhotoFactory(stadium=stadium, is_cover=True)
        resp = owner_client.post(f"/api/v1/stadiums/{stadium.pk}/submit/")
        assert resp.status_code == 400
