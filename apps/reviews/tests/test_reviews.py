"""Integration tests for Phase 7 — Ratings & Reviews."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from tests.factories import (
    BookingFactory,
    OwnerUserFactory,
    ReviewFactory,
    SlotFactory,
    StadiumFactory,
)


@pytest.mark.integration
def test_player_can_submit_review_for_completed_booking(player, player_client, db):
    slot = SlotFactory(stadium=StadiumFactory(active=True))
    booking = BookingFactory(player=player, slot=slot, status="completed")

    url = f"/api/v1/bookings/{booking.pk}/review/"
    response = player_client.post(url, {"overall_rating": 4, "text": "Great pitch"}, format="json")

    assert response.status_code == 201
    assert response.data["overall_rating"] == 4


@pytest.mark.integration
def test_submit_review_requires_completed_booking(player, player_client, db):
    slot = SlotFactory(stadium=StadiumFactory(active=True))
    booking = BookingFactory(player=player, slot=slot, status="confirmed")

    url = f"/api/v1/bookings/{booking.pk}/review/"
    response = player_client.post(url, {"overall_rating": 4, "text": "Nice"}, format="json")

    assert response.status_code == 400


@pytest.mark.integration
def test_submit_review_prevents_duplicate(player, player_client, db):
    slot = SlotFactory(stadium=StadiumFactory(active=True))
    booking = BookingFactory(player=player, slot=slot, status="completed")
    ReviewFactory(booking=booking)

    url = f"/api/v1/bookings/{booking.pk}/review/"
    response = player_client.post(url, {"overall_rating": 5, "text": "Again"}, format="json")

    assert response.status_code == 400


@pytest.mark.integration
def test_unauthenticated_can_list_stadium_reviews(db):
    stadium = StadiumFactory(active=True)
    for _ in range(3):
        slot = SlotFactory(stadium=stadium)
        booking = BookingFactory(slot=slot, status="completed")
        ReviewFactory(booking=booking)

    client = APIClient()
    url = f"/api/v1/stadiums/{stadium.pk}/reviews/"
    response = client.get(url)

    assert response.status_code == 200
    assert response.data["count"] == 3


@pytest.mark.integration
def test_owner_can_respond_to_review(owner, owner_client, db):
    stadium = StadiumFactory(active=True, owner=owner)
    slot = SlotFactory(stadium=stadium)
    booking = BookingFactory(slot=slot, status="completed")
    review = ReviewFactory(booking=booking)

    url = f"/api/v1/owner/stadiums/{stadium.pk}/reviews/{review.pk}/respond/"
    response = owner_client.post(url, {"owner_response": "Thank you!"}, format="json")

    assert response.status_code == 200
    assert response.data["owner_response"] == "Thank you!"


@pytest.mark.integration
def test_owner_cannot_respond_to_other_owners_review(owner, owner_client, db):
    second_owner = OwnerUserFactory()
    stadium = StadiumFactory(active=True, owner=second_owner)
    slot = SlotFactory(stadium=stadium)
    booking = BookingFactory(slot=slot, status="completed")
    review = ReviewFactory(booking=booking)

    url = f"/api/v1/owner/stadiums/{stadium.pk}/reviews/{review.pk}/respond/"
    response = owner_client.post(url, {"owner_response": "Sneaky response"}, format="json")

    assert response.status_code == 403


@pytest.mark.integration
def test_avg_rating_updates_after_review_submission(player, player_client, db):
    from apps.stadiums.models import Stadium

    stadium = StadiumFactory(active=True)
    slot = SlotFactory(stadium=stadium)
    booking = BookingFactory(player=player, slot=slot, status="completed")

    url = f"/api/v1/bookings/{booking.pk}/review/"
    response = player_client.post(url, {"overall_rating": 5, "text": "Excellent"}, format="json")

    assert response.status_code == 201

    stadium = Stadium.objects.get(pk=stadium.pk)
    assert stadium.avg_rating == 5
    assert stadium.review_count == 1


@pytest.mark.integration
def test_avg_rating_updates_after_review_deletion(db):
    from apps.stadiums.models import Stadium

    stadium = StadiumFactory(active=True)

    slot1 = SlotFactory(stadium=stadium)
    booking1 = BookingFactory(slot=slot1, status="completed")
    review1 = ReviewFactory(booking=booking1, overall_rating=4)

    slot2 = SlotFactory(stadium=stadium)
    booking2 = BookingFactory(slot=slot2, status="completed")
    ReviewFactory(booking=booking2, overall_rating=2)

    review1.delete()

    stadium = Stadium.objects.get(pk=stadium.pk)
    assert stadium.avg_rating == 2
    assert stadium.review_count == 1
