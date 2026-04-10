"""
Integration tests for slot block/unblock endpoints.
"""

import pytest

from apps.stadiums.models import SlotStatus
from tests.factories import SlotFactory, StadiumFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestBlockSlot:
    def test_owner_can_block_available_slot(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status="active")
        slot = SlotFactory(stadium=stadium, status=SlotStatus.AVAILABLE)

        resp = owner_client.post(
            f"/api/v1/owner/stadiums/{stadium.pk}/slots/{slot.pk}/block/"
        )
        assert resp.status_code == 200
        slot.refresh_from_db()
        assert slot.status == SlotStatus.BLOCKED

    def test_cannot_block_booked_slot(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status="active")
        slot = SlotFactory(stadium=stadium, status=SlotStatus.BOOKED)

        resp = owner_client.post(
            f"/api/v1/owner/stadiums/{stadium.pk}/slots/{slot.pk}/block/"
        )
        assert resp.status_code == 400

    def test_cannot_block_slot_of_other_owner(self, owner_client):
        from tests.factories import OwnerUserFactory
        other = OwnerUserFactory()
        stadium = StadiumFactory(owner=other, status="active")
        slot = SlotFactory(stadium=stadium, status=SlotStatus.AVAILABLE)

        resp = owner_client.post(
            f"/api/v1/owner/stadiums/{stadium.pk}/slots/{slot.pk}/block/"
        )
        assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.django_db
class TestUnblockSlot:
    def test_owner_can_unblock_blocked_slot(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status="active")
        slot = SlotFactory(stadium=stadium, status=SlotStatus.BLOCKED)

        resp = owner_client.post(
            f"/api/v1/owner/stadiums/{stadium.pk}/slots/{slot.pk}/unblock/"
        )
        assert resp.status_code == 200
        slot.refresh_from_db()
        assert slot.status == SlotStatus.AVAILABLE

    def test_cannot_unblock_available_slot(self, owner_client, owner):
        stadium = StadiumFactory(owner=owner, status="active")
        slot = SlotFactory(stadium=stadium, status=SlotStatus.AVAILABLE)

        resp = owner_client.post(
            f"/api/v1/owner/stadiums/{stadium.pk}/slots/{slot.pk}/unblock/"
        )
        assert resp.status_code == 400
