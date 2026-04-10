"""
Integration tests for admin stadium approval workflow.
"""

import pytest

from apps.stadiums.models import StadiumStatus
from tests.factories import StadiumFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestAdminPendingQueue:
    def test_admin_sees_pending_stadiums(self, admin_client):
        StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        StadiumFactory(status=StadiumStatus.DRAFT)

        resp = admin_client.get("/api/v1/admin/stadiums/pending/")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_owner_cannot_access_pending_queue(self, owner_client):
        resp = owner_client.get("/api/v1/admin/stadiums/pending/")
        assert resp.status_code == 403

    def test_player_cannot_access_pending_queue(self, player_client):
        resp = player_client.get("/api/v1/admin/stadiums/pending/")
        assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.django_db
class TestAdminApprove:
    def test_approve_pending_stadium(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        resp = admin_client.post(f"/api/v1/admin/stadiums/{stadium.pk}/approve/")
        assert resp.status_code == 200
        stadium.refresh_from_db()
        assert stadium.status == StadiumStatus.ACTIVE

    def test_cannot_approve_draft_stadium(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.DRAFT)
        resp = admin_client.post(f"/api/v1/admin/stadiums/{stadium.pk}/approve/")
        assert resp.status_code == 400

    def test_returns_404_for_missing_stadium(self, admin_client):
        resp = admin_client.post("/api/v1/admin/stadiums/99999/approve/")
        assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.django_db
class TestAdminReject:
    def test_reject_pending_stadium_with_note(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        resp = admin_client.post(
            f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
            data={"rejection_note": "Photos are too blurry."},
            format="json",
        )
        assert resp.status_code == 200
        stadium.refresh_from_db()
        assert stadium.status == StadiumStatus.DRAFT
        assert stadium.rejection_note == "Photos are too blurry."

    def test_reject_requires_note(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        resp = admin_client.post(
            f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
            data={},
            format="json",
        )
        assert resp.status_code == 400

    def test_reject_note_must_be_at_least_5_chars(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.PENDING_REVIEW)
        resp = admin_client.post(
            f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
            data={"rejection_note": "Bad"},
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_reject_draft_stadium(self, admin_client):
        stadium = StadiumFactory(status=StadiumStatus.DRAFT)
        resp = admin_client.post(
            f"/api/v1/admin/stadiums/{stadium.pk}/reject/",
            data={"rejection_note": "Wrong status."},
            format="json",
        )
        assert resp.status_code == 400
