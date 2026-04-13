"""
Integration tests for public (no-auth) tournament endpoints.

Covers:
  - GET /tournaments/<id>/ returns tournament + teams
  - GET /tournaments/<id>/ returns 404 for unknown id
  - GET /tournaments/<id>/fixtures/ returns ordered fixture list
  - GET /tournaments/<id>/standings/ returns round_robin standings
  - GET /tournaments/<id>/standings/ returns group_knockout standings
  - Unauthenticated clients can access all public endpoints
"""

import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories import (
    FixtureFactory,
    TournamentFactory,
    TournamentTeamFactory,
)

from apps.tournaments.models import (
    FixtureStage,
    FixtureStatus,
    TournamentFormat,
    TournamentStatus,
)


@pytest.mark.integration
@pytest.mark.django_db
class TestPublicDetail:
    def test_returns_tournament_and_teams(self, api_client):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN, name="Open Cup")
        TournamentTeamFactory(tournament=t, name="Team Alpha")
        TournamentTeamFactory(tournament=t, name="Team Beta")

        url = reverse("tournament-public-detail", kwargs={"pk": t.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tournament"]["name"] == "Open Cup"
        team_names = {t["name"] for t in response.data["teams"]}
        assert team_names == {"Team Alpha", "Team Beta"}

    def test_unknown_id_returns_404(self, api_client):
        url = reverse("tournament-public-detail", kwargs={"pk": 999_999})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_access_allowed(self, api_client):
        t = TournamentFactory(status=TournamentStatus.REGISTRATION_OPEN)
        url = reverse("tournament-public-detail", kwargs={"pk": t.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
@pytest.mark.django_db
class TestPublicFixtureList:
    def test_returns_fixtures_for_tournament(self, api_client):
        t = TournamentFactory(status=TournamentStatus.IN_PROGRESS)
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        FixtureFactory(
            tournament=t,
            home_team=home,
            away_team=away,
            round_number=1,
            stage=FixtureStage.KNOCKOUT,
        )

        url = reverse("tournament-fixture-list", kwargs={"pk": t.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_does_not_include_other_tournament_fixtures(self, api_client):
        t1 = TournamentFactory(status=TournamentStatus.IN_PROGRESS)
        t2 = TournamentFactory(status=TournamentStatus.IN_PROGRESS)
        home = TournamentTeamFactory(tournament=t1)
        away = TournamentTeamFactory(tournament=t1)
        FixtureFactory(tournament=t1, home_team=home, away_team=away)
        FixtureFactory(
            tournament=t2,
            home_team=TournamentTeamFactory(tournament=t2),
            away_team=TournamentTeamFactory(tournament=t2),
        )

        url = reverse("tournament-fixture-list", kwargs={"pk": t1.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_fixture_list_404_for_missing_tournament(self, api_client):
        url = reverse("tournament-fixture-list", kwargs={"pk": 999_999})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.django_db
class TestPublicStandings:
    def test_round_robin_standings_type(self, api_client):
        t = TournamentFactory(
            format=TournamentFormat.ROUND_ROBIN, status=TournamentStatus.IN_PROGRESS
        )
        a = TournamentTeamFactory(tournament=t, name="Alpha")
        b = TournamentTeamFactory(tournament=t, name="Beta")
        FixtureFactory(
            tournament=t,
            home_team=a,
            away_team=b,
            home_score=1,
            away_score=0,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.KNOCKOUT,
        )

        url = reverse("tournament-standings", kwargs={"pk": t.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "round_robin"
        assert "standings" in response.data

    def test_group_knockout_standings_type(self, api_client):
        t = TournamentFactory(
            format=TournamentFormat.GROUP_KNOCKOUT, status=TournamentStatus.IN_PROGRESS
        )
        a1 = TournamentTeamFactory(tournament=t, name="A1")
        a2 = TournamentTeamFactory(tournament=t, name="A2")
        b1 = TournamentTeamFactory(tournament=t, name="B1")
        b2 = TournamentTeamFactory(tournament=t, name="B2")

        FixtureFactory(
            tournament=t,
            home_team=a1,
            away_team=a2,
            home_score=2,
            away_score=0,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.GROUP,
            group_name="A",
        )
        FixtureFactory(
            tournament=t,
            home_team=b1,
            away_team=b2,
            home_score=1,
            away_score=0,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.GROUP,
            group_name="B",
        )

        url = reverse("tournament-standings", kwargs={"pk": t.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "group_knockout"
        assert "groups" in response.data
        assert "A" in response.data["groups"]
        assert "B" in response.data["groups"]

    def test_standings_leader_is_winner(self, api_client):
        t = TournamentFactory(
            format=TournamentFormat.ROUND_ROBIN, status=TournamentStatus.IN_PROGRESS
        )
        a = TournamentTeamFactory(tournament=t, name="Winner")
        b = TournamentTeamFactory(tournament=t, name="Loser")
        FixtureFactory(
            tournament=t,
            home_team=a,
            away_team=b,
            home_score=3,
            away_score=0,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.KNOCKOUT,
        )

        url = reverse("tournament-standings", kwargs={"pk": t.pk})
        response = api_client.get(url)

        assert response.data["standings"][0]["team_name"] == "Winner"

    def test_standings_404_for_missing_tournament(self, api_client):
        url = reverse("tournament-standings", kwargs={"pk": 999_999})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
