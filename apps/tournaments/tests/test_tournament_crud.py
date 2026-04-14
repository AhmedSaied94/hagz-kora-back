"""
Integration tests for tournament CRUD and lifecycle (owner endpoints).
"""

import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories import (
    OwnerUserFactory,
    TournamentFactory,
    TournamentTeamFactory,
)

from apps.tournaments.models import TournamentStatus


@pytest.mark.integration
@pytest.mark.django_db
class TestTournamentCreate:
    def test_owner_can_create_tournament(self, owner_client):
        url = reverse("owner-tournament-list")
        data = {
            "name": "Summer Cup",
            "format": "round_robin",
            "max_teams": 8,
            "registration_deadline": "2030-06-01T00:00:00Z",
            "start_date": "2030-06-15",
            "prize_info": "Trophy",
            "rules": "Standard rules",
        }
        response = owner_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Summer Cup"
        assert response.data["status"] == TournamentStatus.DRAFT

    def test_creates_public_slug_from_name(self, owner_client):
        url = reverse("owner-tournament-list")
        data = {
            "name": "My Great Tournament",
            "format": "knockout",
            "max_teams": 4,
            "registration_deadline": "2030-06-01T00:00:00Z",
            "start_date": "2030-06-15",
        }
        response = owner_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        slug = response.data["public_slug"]
        assert slug  # not empty
        assert " " not in slug

    def test_player_cannot_create_tournament(self, player_client):
        url = reverse("owner-tournament-list")
        data = {
            "name": "Player Cup",
            "format": "round_robin",
            "max_teams": 4,
            "registration_deadline": "2030-06-01T00:00:00Z",
            "start_date": "2030-06-15",
        }
        response = player_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.integration
@pytest.mark.django_db
class TestTournamentPublish:
    def test_owner_can_publish_draft(self, owner_client, owner):
        tournament = TournamentFactory(organizer=owner, status=TournamentStatus.DRAFT)
        url = reverse("owner-tournament-publish", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        tournament.refresh_from_db()
        assert tournament.status == TournamentStatus.REGISTRATION_OPEN

    def test_cannot_publish_already_open(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner, status=TournamentStatus.REGISTRATION_OPEN
        )
        url = reverse("owner-tournament-publish", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_owner_cannot_publish(self, owner_client):
        other_owner = OwnerUserFactory()
        tournament = TournamentFactory(organizer=other_owner, status=TournamentStatus.DRAFT)
        url = reverse("owner-tournament-publish", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.django_db
class TestTournamentEditDelete:
    def test_owner_can_edit_draft(self, owner_client, owner):
        tournament = TournamentFactory(organizer=owner, status=TournamentStatus.DRAFT)
        url = reverse("owner-tournament-detail", kwargs={"pk": tournament.pk})
        response = owner_client.patch(url, {"name": "Updated Name"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_edit_open_tournament(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner, status=TournamentStatus.REGISTRATION_OPEN
        )
        url = reverse("owner-tournament-detail", kwargs={"pk": tournament.pk})
        response = owner_client.patch(url, {"name": "New Name"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_owner_can_delete_draft(self, owner_client, owner):
        tournament = TournamentFactory(organizer=owner, status=TournamentStatus.DRAFT)
        url = reverse("owner-tournament-detail", kwargs={"pk": tournament.pk})
        response = owner_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_cannot_delete_open_tournament(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner, status=TournamentStatus.REGISTRATION_OPEN
        )
        url = reverse("owner-tournament-detail", kwargs={"pk": tournament.pk})
        response = owner_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.django_db
class TestTournamentCloseRegistration:
    def test_close_registration_requires_min_teams(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner, status=TournamentStatus.REGISTRATION_OPEN
        )
        # No teams registered
        url = reverse("owner-tournament-close-reg", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "2" in response.data["detail"] or "team" in response.data["detail"].lower()

    def test_close_registration_with_enough_teams(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.REGISTRATION_OPEN,
            format="round_robin",
        )
        TournamentTeamFactory.create_batch(4, tournament=tournament)
        url = reverse("owner-tournament-close-reg", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        tournament.refresh_from_db()
        assert tournament.status == TournamentStatus.IN_PROGRESS


@pytest.mark.integration
@pytest.mark.django_db
class TestTournamentComplete:
    def test_owner_can_complete_in_progress(self, owner_client, owner):
        tournament = TournamentFactory(
            organizer=owner, status=TournamentStatus.IN_PROGRESS
        )
        url = reverse("owner-tournament-complete", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        tournament.refresh_from_db()
        assert tournament.status == TournamentStatus.COMPLETED

    def test_cannot_complete_draft(self, owner_client, owner):
        tournament = TournamentFactory(organizer=owner, status=TournamentStatus.DRAFT)
        url = reverse("owner-tournament-complete", kwargs={"pk": tournament.pk})
        response = owner_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
