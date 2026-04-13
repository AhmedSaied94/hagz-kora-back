"""
Dynamic standings computation for tournament round-robin and group stages.

Algorithm design by Opus 4.6:
  Phase A — aggregate all completed fixtures into StandingRow dataclasses.
  Phase B — sort by (-pts, -gd, -gf, name), then walk tie runs and resolve
            each run with a H2H mini-table.  No recursive H2H; alphabetical fallback.

Standing is never persisted — always recomputed from Fixture records.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.tournaments.models import Fixture, FixtureStatus, Tournament, TournamentTeam


@dataclass
class StandingRow:
    team: TournamentTeam
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn


def compute_standings(
    tournament: Tournament,
    group_name: str | None = None,
) -> list[StandingRow]:
    """Return ranked standings for a tournament (or a single group).

    Parameters
    ----------
    tournament:
        The tournament to compute standings for.
    group_name:
        If provided, restrict to fixtures in that group (e.g. "A").
        If None, include all non-knockout fixtures (round-robin tournament).
    """
    qs = Fixture.objects.filter(
        tournament=tournament,
        status=FixtureStatus.COMPLETED,
        is_bye=False,
    ).select_related("home_team", "away_team")

    if group_name is not None:
        qs = qs.filter(group_name=group_name)

    # Phase A: aggregate
    rows: dict[int, StandingRow] = {}

    def _get_or_create(team: TournamentTeam) -> StandingRow:
        if team.pk not in rows:
            rows[team.pk] = StandingRow(team=team)
        return rows[team.pk]

    completed_fixtures: list[Fixture] = list(qs)
    for f in completed_fixtures:
        if f.home_team is None or f.away_team is None:
            continue
        if f.home_score is None or f.away_score is None:
            continue

        home_row = _get_or_create(f.home_team)
        away_row = _get_or_create(f.away_team)

        home_row.played += 1
        away_row.played += 1
        home_row.goals_for += f.home_score
        home_row.goals_against += f.away_score
        away_row.goals_for += f.away_score
        away_row.goals_against += f.home_score

        if f.home_score > f.away_score:
            home_row.won += 1
            away_row.lost += 1
        elif f.home_score < f.away_score:
            away_row.won += 1
            home_row.lost += 1
        else:
            home_row.drawn += 1
            away_row.drawn += 1

    # Phase B: sort then resolve ties with H2H
    ranked = sorted(
        rows.values(),
        key=lambda r: (-r.points, -r.goal_difference, -r.goals_for, r.team.name),
    )
    ranked = _resolve_ties(ranked, completed_fixtures)
    return ranked


def _resolve_ties(
    ranked: list[StandingRow],
    all_fixtures: list[Fixture],
) -> list[StandingRow]:
    """Walk tie runs and resolve each with a H2H mini-table."""
    if len(ranked) <= 1:
        return ranked

    result: list[StandingRow] = []
    i = 0
    while i < len(ranked):
        # Find extent of tie run
        j = i + 1
        while j < len(ranked) and _same_primary_keys(ranked[i], ranked[j]):
            j += 1

        tie_group = ranked[i:j]
        if len(tie_group) == 1:
            result.extend(tie_group)
        else:
            result.extend(_sort_by_h2h(tie_group, all_fixtures))
        i = j

    return result


def _same_primary_keys(a: StandingRow, b: StandingRow) -> bool:
    return (
        a.points == b.points
        and a.goal_difference == b.goal_difference
        and a.goals_for == b.goals_for
    )


def _sort_by_h2h(
    tied: list[StandingRow],
    all_fixtures: list[Fixture],
) -> list[StandingRow]:
    """Sort a tied group using a head-to-head mini-table.

    Only fixtures where BOTH teams are in the tied set count.
    If the mini-table still leaves teams equal → alphabetical by team name.
    No recursive H2H (prevents infinite loops on cyclic 3-way ties).
    """
    team_pks = {r.team.pk for r in tied}
    h2h_fixtures = [
        f
        for f in all_fixtures
        if f.home_team is not None
        and f.away_team is not None
        and f.home_team.pk in team_pks
        and f.away_team.pk in team_pks
    ]

    if not h2h_fixtures:
        # No mutual fixtures — alphabetical fallback
        return sorted(tied, key=lambda r: r.team.name)

    # Build mini-table
    mini: dict[int, StandingRow] = {r.team.pk: StandingRow(team=r.team) for r in tied}
    for f in h2h_fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        h = mini[f.home_team.pk]
        a = mini[f.away_team.pk]
        h.played += 1
        a.played += 1
        h.goals_for += f.home_score
        h.goals_against += f.away_score
        a.goals_for += f.away_score
        a.goals_against += f.home_score
        if f.home_score > f.away_score:
            h.won += 1
            a.lost += 1
        elif f.home_score < f.away_score:
            a.won += 1
            h.lost += 1
        else:
            h.drawn += 1
            a.drawn += 1

    # Sort mini-table — no recursive H2H, alphabetical fallback only
    return sorted(
        tied,
        key=lambda r: (
            -mini[r.team.pk].points,
            -mini[r.team.pk].goal_difference,
            -mini[r.team.pk].goals_for,
            r.team.name,
        ),
    )
