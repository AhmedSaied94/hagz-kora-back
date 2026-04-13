"""
Integration tests for knockout auto-generation service.

Verifies:
  - After all round-1 KO fixtures complete, round-2 fixtures are created
  - Winners (home > away, away > home, bye) are seeded correctly
  - With 1 winner left the tournament is marked COMPLETED
  - Idempotency: calling twice does not duplicate fixtures
  - Group-stage completion triggers KO cross-seeding (A1-B2, B1-A2)
  - Pending fixtures block advancement
"""

import pytest
from tests.factories import (
    FixtureFactory,
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
from apps.tournaments.services.knockout import (
    _maybe_advance_knockout_round,
    _maybe_transition_group_to_knockout,
    maybe_generate_next_round,
)


def _ko_fixture(tournament, home, away, home_score, away_score, round_number=1):
    """Create a completed knockout fixture."""
    return FixtureFactory(
        tournament=tournament,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        status=FixtureStatus.COMPLETED,
        stage=FixtureStage.KNOCKOUT,
        round_number=round_number,
    )


def _group_fixture(tournament, home, away, home_score, away_score, group_name):
    return FixtureFactory(
        tournament=tournament,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        status=FixtureStatus.COMPLETED,
        stage=FixtureStage.GROUP,
        group_name=group_name,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestKnockoutAdvancement:
    def test_round2_created_after_round1_completes(self):
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)
        d = TournamentTeamFactory(tournament=t)

        _ko_fixture(t, a, b, 2, 0)  # a wins
        _ko_fixture(t, c, d, 0, 1)  # d wins

        _maybe_advance_knockout_round(t, 1)

        round2 = Fixture.objects.filter(tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2)
        assert round2.count() == 1
        participants = {round2.first().home_team, round2.first().away_team}
        assert participants == {a, d}

    def test_pending_fixture_blocks_advancement(self):
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)
        d = TournamentTeamFactory(tournament=t)

        _ko_fixture(t, a, b, 2, 0)  # completed
        # f2 is still scheduled (not completed)
        FixtureFactory(
            tournament=t,
            home_team=c,
            away_team=d,
            stage=FixtureStage.KNOCKOUT,
            round_number=1,
            status=FixtureStatus.SCHEDULED,
        )

        _maybe_advance_knockout_round(t, 1)

        assert not Fixture.objects.filter(
            tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2
        ).exists()

    def test_idempotent_no_duplicate_round(self):
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)
        d = TournamentTeamFactory(tournament=t)

        _ko_fixture(t, a, b, 2, 0)
        _ko_fixture(t, c, d, 1, 3)

        _maybe_advance_knockout_round(t, 1)
        _maybe_advance_knockout_round(t, 1)  # second call

        assert (
            Fixture.objects.filter(
                tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2
            ).count()
            == 1
        )

    def test_bye_winner_advances(self):
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)

        # a has a bye (already completed, no away team)
        FixtureFactory(
            tournament=t,
            home_team=a,
            away_team=None,
            is_bye=True,
            status=FixtureStatus.COMPLETED,
            stage=FixtureStage.KNOCKOUT,
            round_number=1,
        )
        _ko_fixture(t, b, c, 1, 0)  # b wins

        _maybe_advance_knockout_round(t, 1)

        round2 = Fixture.objects.filter(tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2)
        assert round2.count() == 1
        participants = {round2.first().home_team, round2.first().away_team}
        assert participants == {a, b}

    def test_single_winner_marks_tournament_completed(self):
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)

        _ko_fixture(t, a, b, 2, 0)  # a is the final winner

        _maybe_advance_knockout_round(t, 1)

        t.refresh_from_db()
        assert t.status == TournamentStatus.COMPLETED

    def test_maybe_generate_next_round_dispatches_correctly(self):
        """maybe_generate_next_round reads stage and routes to the right handler."""
        t = TournamentFactory(format=TournamentFormat.KNOCKOUT, status=TournamentStatus.IN_PROGRESS)
        a = TournamentTeamFactory(tournament=t)
        b = TournamentTeamFactory(tournament=t)
        c = TournamentTeamFactory(tournament=t)
        d = TournamentTeamFactory(tournament=t)

        f1 = _ko_fixture(t, a, b, 2, 0)
        _ko_fixture(t, c, d, 0, 3)

        maybe_generate_next_round(f1.pk)

        assert (
            Fixture.objects.filter(
                tournament=t, stage=FixtureStage.KNOCKOUT, round_number=2
            ).count()
            == 1
        )

    def test_nonexistent_fixture_silently_exits(self):
        """maybe_generate_next_round must not raise if fixture is gone."""
        maybe_generate_next_round(999_999_999)  # should not raise


@pytest.mark.integration
@pytest.mark.django_db
class TestGroupToKnockoutTransition:
    def test_2_group_ko_seeding(self):
        """After all group fixtures complete, A1-B2 and B1-A2 are created."""
        t = TournamentFactory(
            format=TournamentFormat.GROUP_KNOCKOUT, status=TournamentStatus.IN_PROGRESS
        )
        a1 = TournamentTeamFactory(tournament=t, name="A1")
        a2 = TournamentTeamFactory(tournament=t, name="A2")
        b1 = TournamentTeamFactory(tournament=t, name="B1")
        b2 = TournamentTeamFactory(tournament=t, name="B2")

        # Group A: a1 wins (3pts), a2 loses (0pts)
        _group_fixture(t, a1, a2, 2, 0, "A")
        # Group B: b1 wins (3pts), b2 loses (0pts)
        _group_fixture(t, b1, b2, 2, 0, "B")

        _maybe_transition_group_to_knockout(t)

        ko_fixtures = Fixture.objects.filter(
            tournament=t, stage=FixtureStage.KNOCKOUT, round_number=1
        ).select_related("home_team", "away_team")

        assert ko_fixtures.count() == 2
        matchups = {frozenset([f.home_team.name, f.away_team.name]) for f in ko_fixtures}
        assert frozenset(["A1", "B2"]) in matchups
        assert frozenset(["B1", "A2"]) in matchups

    def test_pending_group_fixture_blocks_transition(self):
        t = TournamentFactory(
            format=TournamentFormat.GROUP_KNOCKOUT, status=TournamentStatus.IN_PROGRESS
        )
        a1 = TournamentTeamFactory(tournament=t)
        a2 = TournamentTeamFactory(tournament=t)
        b1 = TournamentTeamFactory(tournament=t)
        b2 = TournamentTeamFactory(tournament=t)

        _group_fixture(t, a1, a2, 2, 0, "A")
        # b1 vs b2 still pending
        FixtureFactory(
            tournament=t,
            home_team=b1,
            away_team=b2,
            stage=FixtureStage.GROUP,
            group_name="B",
            status=FixtureStatus.SCHEDULED,
        )

        _maybe_transition_group_to_knockout(t)

        assert not Fixture.objects.filter(tournament=t, stage=FixtureStage.KNOCKOUT).exists()

    def test_transition_idempotent(self):
        t = TournamentFactory(
            format=TournamentFormat.GROUP_KNOCKOUT, status=TournamentStatus.IN_PROGRESS
        )
        a1 = TournamentTeamFactory(tournament=t)
        a2 = TournamentTeamFactory(tournament=t)
        b1 = TournamentTeamFactory(tournament=t)
        b2 = TournamentTeamFactory(tournament=t)

        _group_fixture(t, a1, a2, 2, 0, "A")
        _group_fixture(t, b1, b2, 2, 0, "B")

        _maybe_transition_group_to_knockout(t)
        _maybe_transition_group_to_knockout(t)  # second call

        assert (
            Fixture.objects.filter(
                tournament=t, stage=FixtureStage.KNOCKOUT, round_number=1
            ).count()
            == 2
        )
