"""Integration tests for booking list and detail endpoints."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories import BookingFactory, OwnerUserFactory, PlayerUserFactory, StadiumFactory


@pytest.mark.integration
class TestMyBookingListView:
    """Tests for GET /api/v1/bookings/"""

    def test_player_sees_only_own_bookings(self, player, player_client, db):
        """Player can only see their own bookings, not other players' bookings."""
        # Arrange
        player2 = PlayerUserFactory()
        stadium = StadiumFactory(active=True)

        booking1 = BookingFactory(player=player, stadium=stadium)
        booking2 = BookingFactory(player=player2, stadium=stadium)

        # Act
        url = reverse("booking-list")
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == booking1.id
        assert booking2.id not in [b["id"] for b in response.data["results"]]

    def test_bookings_ordered_by_created_at_descending(self, player, player_client, db):
        """Bookings should be ordered by created_at in descending order."""
        # Arrange
        stadium = StadiumFactory(active=True)

        booking1 = BookingFactory(player=player, stadium=stadium)
        booking2 = BookingFactory(player=player, stadium=stadium)
        booking3 = BookingFactory(player=player, stadium=stadium)

        # Act
        url = reverse("booking-list")
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        result_ids = [b["id"] for b in response.data["results"]]
        # Most recent first
        assert result_ids == [booking3.id, booking2.id, booking1.id]

    def test_booking_list_includes_denormalized_fields(self, player, player_client, db):
        """Booking list response should include denormalized stadium and slot fields."""
        # Arrange
        booking = BookingFactory(player=player)

        # Act
        url = reverse("booking-list")
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert "stadium_name_ar" in result
        assert "stadium_name_en" in result
        assert "date" in result
        assert "start_time" in result
        assert "end_time" in result
        assert result["stadium_name_ar"] == booking.stadium.name_ar
        assert result["stadium_name_en"] == booking.stadium.name_en
        assert str(result["date"]) == str(booking.slot.date)

    def test_unauthenticated_request_returns_401(self, api_client, db):
        """Unauthenticated requests should return 401."""
        # Act
        url = reverse("booking-list")
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_player_role_returns_403(self, api_client, db):
        """Non-player users should receive 403 Forbidden."""
        # Arrange
        owner = OwnerUserFactory()
        client = api_client
        client.force_authenticate(user=owner)

        # Act
        url = reverse("booking-list")
        response = client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_pagination_applied_to_booking_list(self, player, player_client, db):
        """Booking list should be paginated (20 items per page by default)."""
        # Arrange
        stadium = StadiumFactory(active=True)
        # Create 25 bookings
        for _ in range(25):
            BookingFactory(player=player, stadium=stadium)

        # Act
        url = reverse("booking-list")
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 25
        assert len(response.data["results"]) == 20
        assert response.data["next"] is not None


@pytest.mark.integration
class TestBookingDetailView:
    """Tests for GET /api/v1/bookings/<pk>/"""

    def test_player_can_retrieve_own_booking(self, player, player_client, db):
        """Player can retrieve their own booking."""
        # Arrange
        booking = BookingFactory(player=player)

        # Act
        url = reverse("booking-detail", kwargs={"pk": booking.id})
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == booking.id
        assert response.data["player"] == player.id
        assert response.data["status"] == booking.status

    def test_player_cannot_access_other_players_booking(self, api_client, db):
        """Player cannot access another player's booking."""
        # Arrange
        player1 = PlayerUserFactory()
        player2 = PlayerUserFactory()
        booking = BookingFactory(player=player1)

        client = api_client
        client.force_authenticate(user=player2)

        # Act
        url = reverse("booking-detail", kwargs={"pk": booking.id})
        response = client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_booking_detail_includes_all_fields(self, player, player_client, db):
        """Booking detail response includes all required fields."""
        # Arrange
        booking = BookingFactory(player=player)

        # Act
        url = reverse("booking-detail", kwargs={"pk": booking.id})
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        required_fields = [
            "id",
            "player",
            "slot",
            "stadium",
            "status",
            "cancellation_reason",
            "cancelled_by",
            "is_late_cancellation",
            "price_at_booking",
            "deposit_amount",
            "stadium_name_ar",
            "stadium_name_en",
            "date",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in response.data

    def test_unauthenticated_request_to_detail_returns_401(self, api_client, db):
        """Unauthenticated requests to detail endpoint should return 401."""
        # Arrange
        booking = BookingFactory()

        # Act
        url = reverse("booking-detail", kwargs={"pk": booking.id})
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_booking_detail_not_found_for_invalid_id(self, player_client, db):
        """Requesting a non-existent booking should return 404."""
        # Act
        url = reverse("booking-detail", kwargs={"pk": 99999})
        response = player_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestOwnerBookingListView:
    """Tests for GET /api/v1/owner/bookings/"""

    def test_owner_sees_bookings_for_all_stadiums(self, owner, owner_client, db):
        """Owner can see all bookings for their stadiums."""
        # Arrange
        stadium1 = StadiumFactory(owner=owner, active=True)
        stadium2 = StadiumFactory(owner=owner, active=True)
        other_owner_stadium = StadiumFactory(active=True)

        booking1 = BookingFactory(stadium=stadium1)
        booking2 = BookingFactory(stadium=stadium2)
        booking3 = BookingFactory(stadium=other_owner_stadium)

        # Act
        url = reverse("owner-booking-list")
        response = owner_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        result_ids = [b["id"] for b in response.data["results"]]
        assert booking1.id in result_ids
        assert booking2.id in result_ids
        assert booking3.id not in result_ids

    def test_non_owner_cannot_access_booking_list(self, api_client, db):
        """Non-owner users should not access owner booking list."""
        # Arrange
        player = PlayerUserFactory()
        client = api_client
        client.force_authenticate(user=player)

        # Act
        url = reverse("owner-booking-list")
        response = client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_bookings_include_player_info(self, owner, owner_client, db):
        """Owner booking list should include player information."""
        # Arrange
        stadium = StadiumFactory(owner=owner, active=True)
        booking = BookingFactory(stadium=stadium)

        # Act
        url = reverse("owner-booking-list")
        response = owner_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["player"] == booking.player.id
        assert "stadium_name_ar" in result
        assert "stadium_name_en" in result

    def test_unauthenticated_request_to_owner_bookings_returns_401(self, api_client, db):
        """Unauthenticated requests to owner bookings should return 401."""
        # Act
        url = reverse("owner-booking-list")
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_owner_bookings_ordered_by_created_at_descending(self, owner, owner_client, db):
        """Owner bookings should be ordered by created_at descending."""
        # Arrange
        stadium = StadiumFactory(owner=owner, active=True)

        booking1 = BookingFactory(stadium=stadium)
        booking2 = BookingFactory(stadium=stadium)
        booking3 = BookingFactory(stadium=stadium)

        # Act
        url = reverse("owner-booking-list")
        response = owner_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        result_ids = [b["id"] for b in response.data["results"]]
        # Most recent first
        assert result_ids == [booking3.id, booking2.id, booking1.id]


@pytest.mark.integration
class TestBookingCreateValidation:
    """Tests for POST /api/v1/bookings/ validation."""

    def test_create_booking_invalid_slot_id(self, player_client, db):
        """Creating a booking with invalid slot_id returns validation error."""
        # Act
        url = reverse("booking-list")
        response = player_client.post(url, {"slot_id": 99999})

        # Assert — slot_id passes serializer validation (valid int), so the
        # service runs and returns 409 because slot 99999 does not exist.
        assert response.status_code == status.HTTP_409_CONFLICT
