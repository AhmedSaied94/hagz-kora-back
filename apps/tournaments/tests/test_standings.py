"""
Unit and integration tests for standings computation.

Verifies:
  - Points/GD/GF aggregation
  - Tiebreaker chain: points → GD → GF → H2H → alphabetical
  - Cyclic 3-way tie resolves alphabetically
  - Group filter works correctly
"""

import pytest
from tests.factories import (
    FixtureFactory,
    TournamentFactory,
    TournamentTeamFactory,
)

from apps.tournaments.models import (
    FixtureStage,
    FixtureStatus,
    TournamentFormat,
)
from apps.tournaments.services.standings import compute_standings


def _completed(tournament, home_team, away_team, home_score, away_score, **kwargs):
    """Helper: create a completed fixture with scores."""
    return FixtureFactory(
        tournament=tournament,
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        status=FixtureStatus.COMPLETED,
        **kwargs,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestStandingsBasic:
    def test_winner_has_3_points(self):
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        home = TournamentTeamFactory(tournament=t, name="Alpha")
        away = TournamentTeamFactory(tournament=t, name="Beta")
        _completed(t, home, away, 3, 1)

        rows = compute_standings(t)
        by_name = {r.team.name: r for r in rows}

        assert by_name["Alpha"].points == 3
        assert by_name["Alpha"].won == 1
        assert by_name["Beta"].points == 0
        assert by_name["Beta"].lost == 1

    def test_draw_gives_one_point_each(self):
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        a = TournamentTeamFactory(tournament=t, name="A")
        b = TournamentTeamFactory(tournament=t, name="B")
        _completed(t, a, b, 2, 2)

        rows = compute_standings(t)
        for r in rows:
            assert r.points == 1
            assert r.drawn == 1

    def test_goals_accumulated_correctly(self):
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        a = TournamentTeamFactory(tournament=t, name="A")
        b = TournamentTeamFactory(tournament=t, name="B")
        c = TournamentTeamFactory(tournament=t, name="C")
        _completed(t, a, b, 3, 0)
        _completed(t, a, c, 2, 1)

        rows = compute_standings(t)
        by_name = {r.team.name: r for r in rows}
        assert by_name["A"].goals_for == 5
        assert by_name["A"].goals_against == 1
        assert by_name["A"].goal_difference == 4
        assert by_name["A"].played == 2


@pytest.mark.integration
@pytest.mark.django_db
class TestStandingsTiebreakers:
    def test_better_gd_wins_tiebreak(self):
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        a = TournamentTeamFactory(tournament=t, name="Alpha")
        b = TournamentTeamFactory(tournament=t, name="Beta")
        c = TournamentTeamFactory(tournament=t, name="Gamma")

        # a beats c 3-0 (GD +3), b beats c 1-0 (GD +1), a draws b
        _completed(t, a, b, 1, 1)
        _completed(t, a, c, 3, 0)
        _completed(t, b, c, 1, 0)

        rows = compute_standings(t)
        # a: 1W 1D = 4pts, gd=+3; b: 1W 1D = 4pts, gd=+1 → a > b
        assert rows[0].team.name == "Alpha"
        assert rows[1].team.name == "Beta"

    def test_h2h_resolves_equal_gd_gf(self):
        """Two teams equal on pts, GD, GF — H2H decides."""
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        a = TournamentTeamFactory(tournament=t, name="Aardvark")
        b = TournamentTeamFactory(tournament=t, name="Buffalo")
        c = TournamentTeamFactory(tournament=t, name="Camel")

        # A beats C 2-0, B beats C 2-0  → A and B tied on pts/GD/GF
        # A beat B 1-0 → A wins H2H
        _completed(t, a, c, 2, 0)
        _completed(t, b, c, 2, 0)
        _completed(t, a, b, 1, 0)

        rows = compute_standings(t)
        assert rows[0].team.name == "Aardvark"
        assert rows[1].team.name == "Buffalo"

    def test_cyclic_3way_tie_falls_back_to_alphabetical(self):
        """A beats B, B beats C, C beats A — all equal → alphabetical."""
        t = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        a = TournamentTeamFactory(tournament=t, name="Alpha")
        b = TournamentTeamFactory(tournament=t, name="Beta")
        c = TournamentTeamFactory(tournament=t, name="Gamma")

        _completed(t, a, b, 1, 0)
        _completed(t, b, c, 1, 0)
        _completed(t, c, a, 1, 0)

        rows = compute_standings(t)
        names = [r.team.name for r in rows]
        assert names == ["Alpha", "Beta", "Gamma"]


@pytest.mark.integration
@pytest.mark.django_db
class TestGroupFilter:
    def test_group_filter_excludes_other_groups(self):
        t = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        a1 = TournamentTeamFactory(tournament=t, name="A1")
        a2 = TournamentTeamFactory(tournament=t, name="A2")
        b1 = TournamentTeamFactory(tournament=t, name="B1")
        b2 = TournamentTeamFactory(tournament=t, name="B2")

        _completed(t, a1, a2, 2, 0, stage=FixtureStage.GROUP, group_name="A")
        _completed(t, b1, b2, 3, 1, stage=FixtureStage.GROUP, group_name="B")

        group_a = compute_standings(t, group_name="A")
        team_names_a = {r.team.name for r in group_a}
        assert team_names_a == {"A1", "A2"}

        group_b = compute_standings(t, group_name="B")
        team_names_b = {r.team.name for r in group_b}
        assert team_names_b == {"B1", "B2"}
