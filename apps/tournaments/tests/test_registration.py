"""
Integration tests for team registration endpoints.

Covers:
  - Player can register a new team → becomes captain
  - Duplicate registration is rejected
  - Cannot register when tournament is not open
  - Tournament auto-closes when max_teams reached
  - Player can join a team via join_code
  - Invalid join_code is rejected
  - Cannot join a closed/in-progress tournament
  - Cannot join twice
  - GET /my-team/ returns team + players
  - /my-team/ returns 404 when not registered
"""

import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories import (
    TournamentFactory,
    TournamentTeamFactory,
)

from apps.tournaments.models import (
    TournamentPlayer,
    TournamentStatus,
    TournamentTeam,
)


@pytest.mark.integration
@pytest.mark.django_db
class TestTeamRegister:
    def test_player_can_register_team(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN, max_teams=8)
        url = reverse("tournament-team-register", kwargs={"pk": t.pk})

        response = player_client.post(url, {"team_name": "The Reds"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert TournamentTeam.objects.filter(tournament=t, name="The Reds").exists()
        team = TournamentTeam.objects.get(tournament=t, name="The Reds")
        assert team.captain == player
        assert TournamentPlayer.objects.filter(team=team, player=player).exists()

    def test_duplicate_registration_rejected(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        TournamentTeamFactory(tournament=t, captain=player)
        TournamentPlayer.objects.create(
            team=TournamentTeam.objects.get(tournament=t, captain=player),
            player=player,
        )

        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = player_client.post(url, {"team_name": "Another Team"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_register_closed_tournament(self, player_client):
        t = TournamentFactory(status=TournamentStatus.IN_PROGRESS)
        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = player_client.post(url, {"team_name": "Late Team"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_register_when_full(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN, max_teams=2)
        # Fill up tournament with 2 teams
        for _ in range(2):
            TournamentTeamFactory(tournament=t)

        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = player_client.post(url, {"team_name": "Overflow"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_auto_closes_when_max_reached(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN, max_teams=2)
        TournamentTeamFactory(tournament=t)  # 1 team already in

        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = player_client.post(url, {"team_name": "Fill Up"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        t.refresh_from_db()
        assert t.status == TournamentStatus.REGISTRATION_CLOSED

    def test_owner_cannot_register_team(self, owner_client):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = owner_client.post(url, {"team_name": "Owner Team"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_register(self, api_client):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        url = reverse("tournament-team-register", kwargs={"pk": t.pk})
        response = api_client.post(url, {"team_name": "Anon Team"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.django_db
class TestTeamJoin:
    def test_player_can_join_via_code(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        team = TournamentTeamFactory(tournament=t, join_code="TESTCODE1")

        url = reverse("tournament-team-join")
        response = player_client.post(url, {"join_code": "TESTCODE1"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert TournamentPlayer.objects.filter(team=team, player=player).exists()

    def test_invalid_code_rejected(self, player_client):
        url = reverse("tournament-team-join")
        response = player_client.post(url, {"join_code": "BADCODE99"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_join_closed_tournament(self, player_client):
        t = TournamentFactory(status=TournamentStatus.IN_PROGRESS)
        TournamentTeamFactory(tournament=t, join_code="CLOSEDCOD")

        url = reverse("tournament-team-join")
        response = player_client.post(url, {"join_code": "CLOSEDCOD"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_join_twice(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        team = TournamentTeamFactory(tournament=t, join_code="DUPCODE01")
        TournamentPlayer.objects.create(team=team, player=player)

        url = reverse("tournament-team-join")
        response = player_client.post(url, {"join_code": "DUPCODE01"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.django_db
class TestMyTeam:
    def test_returns_team_and_players(self, player_client, player):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        team = TournamentTeamFactory(tournament=t, name="My Team", captain=player)
        TournamentPlayer.objects.create(team=team, player=player)

        url = reverse("tournament-my-team", kwargs={"pk": t.pk})
        response = player_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["team"]["name"] == "My Team"
        assert len(response.data["players"]) == 1

    def test_returns_404_when_not_registered(self, player_client):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        url = reverse("tournament-my-team", kwargs={"pk": t.pk})
        response = player_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_in_other_tournament(self, player_client, player):
        """Player registered in tournament A should not see team in tournament B."""
        t1 = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        t2 = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        team = TournamentTeamFactory(tournament=t1, captain=player)
        TournamentPlayer.objects.create(team=team, player=player)

        url = reverse("tournament-my-team", kwargs={"pk": t2.pk})
        response = player_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
