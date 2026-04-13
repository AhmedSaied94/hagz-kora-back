"""
Integration tests for the owner score-entry endpoint.

Verifies:
  - Owner can PATCH a fixture score → status becomes COMPLETED
  - Non-owner gets 404
  - Cannot score a bye fixture
  - Cannot score a cancelled fixture
  - Cannot score fixtures in a non-in-progress tournament
  - tournament.on_commit auto-generation wires correctly (round 2 created)
"""

import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories import (
    FixtureFactory,
    OwnerUserFactory,
    TournamentFactory,
    TournamentTeamFactory,
)

from apps.tournaments.models import (
    Fixture,
    FixtureStage,
    FixtureStatus,
    TournamentFormat,
    TournamentStatus,
)


def _score_url(tournament_pk, fixture_pk):
    return reverse(
        "owner-fixture-score",
        kwargs={"pk": tournament_pk, "fixture_pk": fixture_pk},
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestScoreEntry:
    def test_owner_can_enter_score(self, owner_client, owner):
        t = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.IN_PROGRESS,
            format=TournamentFormat.KNOCKOUT,
        )
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(
            tournament=t,
            home_team=home,
            away_team=away,
            stage=FixtureStage.KNOCKOUT,
            status=FixtureStatus.SCHEDULED,
        )

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 2, "away_score": 1}, format="json")

        assert response.status_code == status.HTTP_200_OK
        fixture.refresh_from_db()
        assert fixture.home_score == 2
        assert fixture.away_score == 1
        assert fixture.status == FixtureStatus.COMPLETED

    def test_non_owner_gets_404(self, owner_client):
        other_owner = OwnerUserFactory()
        t = TournamentFactory(
            organizer=other_owner,
            status=TournamentStatus.IN_PROGRESS,
        )
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(tournament=t, home_team=home, away_team=away)

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 1, "away_score": 0}, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_score_bye_fixture(self, owner_client, owner):
        t = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.IN_PROGRESS,
            format=TournamentFormat.KNOCKOUT,
        )
        home = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(
            tournament=t,
            home_team=home,
            away_team=None,
            is_bye=True,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.KNOCKOUT,
        )

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 1, "away_score": 0}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_score_cancelled_fixture(self, owner_client, owner):
        t = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.IN_PROGRESS,
        )
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(
            tournament=t,
            home_team=home,
            away_team=away,
            status=FixtureStatus.CANCELLED,
        )

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 1, "away_score": 0}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_score_draft_tournament(self, owner_client, owner):
        t = TournamentFactory(organizer=owner, status=TournamentStatus.DRAFT)
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(tournament=t, home_team=home, away_team=away)

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 1, "away_score": 0}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_scores_returns_400(self, owner_client, owner):
        t = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.IN_PROGRESS,
        )
        home = TournamentTeamFactory(tournament=t)
        away = TournamentTeamFactory(tournament=t)
        fixture = FixtureFactory(
            tournament=t,
            home_team=home,
            away_team=away,
            status=FixtureStatus.SCHEDULED,
        )

        url = _score_url(t.pk, fixture.pk)
        response = owner_client.patch(url, {"home_score": 2}, format="json")  # missing away_score

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db(transaction=True)
    def test_score_triggers_next_round_generation(self, owner, owner_client):
        """After scoring the last R1 fixture, R2 is auto-created on commit."""
        t = TournamentFactory(
            organizer=owner,
            status=TournamentStatus.IN_PROGRESS,
            format=TournamentFormat.KNOCKOUT,
        )
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)
        d = TournamentTeamFactory(tournament=t)

        # pre-create first fixture as completed
        FixtureFactory(
            tournament=t,
            home_team=a,
            away_team=b,
            home_score=2,
            away_score=0,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.KNOCKOUT,
            round_number=1,
        )
        # second fixture still scheduled
        f2 = FixtureFactory(
            tournament=t,
            home_team=c,
            away_team=d,
            status=FixtureStatus.SCHEDULED,
            stage=FixtureStage.KNOCKOUT,
            round_number=1,
        )

        url = _score_url(t.pk, f2.pk)
        response = owner_client.patch(url, {"home_score": 1, "away_score": 3}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert (
            Fixture.objects.filter(
                tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2
            ).count()
            == 1
        )
