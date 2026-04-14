"""
Unit tests for the fixture generation service.

Tests each format with known inputs (N=3,4,5,6,7,8) and verifies:
  - Correct fixture count
  - Every team appears the right number of times
  - No team plays itself
  - Bye fixtures have is_bye=True and away_team=None
"""


import pytest
from tests.factories import TournamentFactory, TournamentTeamFactory

from apps.tournaments.models import (
    Fixture,
    FixtureStage,
    FixtureStatus,
    Tournament,
    TournamentFormat,
    TournamentTeam,
)
from apps.tournaments.services.fixture_generator import (
    _generate_knockout_round1,
    _generate_round_robin,
    _next_power_of_2,
    generate_fixtures,
    validate_team_count,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_teams(tournament: Tournament, n: int) -> list[TournamentTeam]:
    return [TournamentTeamFactory(tournament=tournament) for _ in range(n)]


# ---------------------------------------------------------------------------
# _next_power_of_2
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNextPowerOf2:
    def test_exact_powers(self):
        assert _next_power_of_2(1) == 1
        assert _next_power_of_2(2) == 2
        assert _next_power_of_2(4) == 4
        assert _next_power_of_2(8) == 8
        assert _next_power_of_2(16) == 16

    def test_non_powers(self):
        assert _next_power_of_2(3) == 4
        assert _next_power_of_2(5) == 8
        assert _next_power_of_2(6) == 8
        assert _next_power_of_2(7) == 8
        assert _next_power_of_2(9) == 16


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
class TestRoundRobin:
    @pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
    def test_fixture_count(self, n):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        teams = _make_teams(tournament, n)
        fixtures = _generate_round_robin(tournament, teams)
        expected = n * (n - 1) // 2
        assert len(fixtures) == expected, f"N={n}: expected {expected} fixtures, got {len(fixtures)}"

    @pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
    def test_every_team_plays_correct_times(self, n):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        teams = _make_teams(tournament, n)
        fixtures = _generate_round_robin(tournament, teams)

        appearances: dict[int, int] = {}
        for f in fixtures:
            appearances[f.home_team_id] = appearances.get(f.home_team_id, 0) + 1
            appearances[f.away_team_id] = appearances.get(f.away_team_id, 0) + 1

        for team in teams:
            assert appearances.get(team.pk, 0) == n - 1, (
                f"N={n}: {team.name} should play {n - 1} times"
            )

    @pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
    def test_no_team_plays_itself(self, n):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        teams = _make_teams(tournament, n)
        fixtures = _generate_round_robin(tournament, teams)
        for f in fixtures:
            assert f.home_team_id != f.away_team_id

    @pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
    def test_no_duplicate_pairs(self, n):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        teams = _make_teams(tournament, n)
        fixtures = _generate_round_robin(tournament, teams)
        pairs = set()
        for f in fixtures:
            pair = frozenset([f.home_team_id, f.away_team_id])
            assert pair not in pairs, f"Duplicate pair found: {pair}"
            pairs.add(pair)

    def test_no_bye_fixtures_in_round_robin(self):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        teams = _make_teams(tournament, 4)
        fixtures = _generate_round_robin(tournament, teams)
        assert all(not f.is_bye for f in fixtures)


# ---------------------------------------------------------------------------
# Knockout
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
class TestKnockout:
    @pytest.mark.parametrize("n,expected_byes", [
        (2, 0),
        (3, 1),
        (4, 0),
        (5, 3),
        (6, 2),
        (7, 1),
        (8, 0),
    ])
    def test_bye_count(self, n, expected_byes):
        tournament = TournamentFactory(format=TournamentFormat.KNOCKOUT)
        teams = _make_teams(tournament, n)
        fixtures = _generate_knockout_round1(tournament, teams)
        bye_count = sum(1 for f in fixtures if f.is_bye)
        assert bye_count == expected_byes, f"N={n}: expected {expected_byes} byes"

    @pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8])
    def test_bye_fixtures_have_null_away(self, n):
        tournament = TournamentFactory(format=TournamentFormat.KNOCKOUT)
        teams = _make_teams(tournament, n)
        fixtures = _generate_knockout_round1(tournament, teams)
        for f in fixtures:
            if f.is_bye:
                assert f.away_team_id is None
                assert f.status == FixtureStatus.COMPLETED

    @pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8])
    def test_total_first_round_fixtures(self, n):
        """Round 1 fixtures = bracket_size / 2 (byes + real matches)."""
        from apps.tournaments.services.fixture_generator import _next_power_of_2
        tournament = TournamentFactory(format=TournamentFormat.KNOCKOUT)
        teams = _make_teams(tournament, n)
        fixtures = _generate_knockout_round1(tournament, teams)
        bracket_size = _next_power_of_2(n)
        expected = bracket_size // 2
        assert len(fixtures) == expected


# ---------------------------------------------------------------------------
# Group knockout — structure
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
class TestGroupKnockout:
    def test_8_teams_produces_group_fixtures(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        teams = _make_teams(tournament, 8)
        fixtures = generate_fixtures(tournament)
        # 2 groups of 4 → 2 * C(4,2) = 12 fixtures
        assert len(fixtures) == 12
        assert all(f.stage == FixtureStage.GROUP for f in fixtures)

    def test_8_teams_has_two_groups(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        teams = _make_teams(tournament, 8)
        generate_fixtures(tournament)
        group_names = set(
            Fixture.objects.filter(tournament=tournament).values_list("group_name", flat=True)
        )
        assert group_names == {"A", "B"}

    def test_16_teams_has_four_groups(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        teams = _make_teams(tournament, 16)
        generate_fixtures(tournament)
        group_names = set(
            Fixture.objects.filter(tournament=tournament).values_list("group_name", flat=True)
        )
        assert group_names == {"A", "B", "C", "D"}

    def test_invalid_team_count_raises(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        _make_teams(tournament, 7)
        with pytest.raises(ValueError, match="7"):
            generate_fixtures(tournament)


# ---------------------------------------------------------------------------
# validate_team_count
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db
class TestValidateTeamCount:
    def test_raises_with_one_team(self):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        TournamentTeamFactory(tournament=tournament)
        with pytest.raises(ValueError):
            validate_team_count(tournament)

    def test_passes_with_two_teams(self):
        tournament = TournamentFactory(format=TournamentFormat.ROUND_ROBIN)
        TournamentTeamFactory.create_batch(2, tournament=tournament)
        validate_team_count(tournament)  # should not raise

    def test_group_ko_invalid_count_raises(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        TournamentTeamFactory.create_batch(7, tournament=tournament)
        with pytest.raises(ValueError):
            validate_team_count(tournament)

    def test_group_ko_valid_count_passes(self):
        tournament = TournamentFactory(format=TournamentFormat.GROUP_KNOCKOUT)
        TournamentTeamFactory.create_batch(8, tournament=tournament)
        validate_team_count(tournament)  # should not raise
