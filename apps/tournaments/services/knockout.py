"""
Knockout round auto-generation service.

Algorithm design by Opus 4.6:
  - Called via transaction.on_commit after each score entry.
  - For group-knockout tournaments: after all group fixtures complete,
    derive standings and seed into the first knockout round.
  - For knockout tournaments: when all non-cancelled fixtures in round N
    complete, generate round N+1 fixtures with the winners.
  - Idempotency: check if next round already exists before creating.
  - Cancelled fixtures are skipped in "round complete" checks; they block
    progression only if a non-cancelled, non-completed fixture remains.
"""

from __future__ import annotations

import datetime

from django.db import transaction

from apps.tournaments.models import (
    Fixture,
    FixtureStage,
    FixtureStatus,
    Tournament,
    TournamentStatus,
    TournamentTeam,
)

_GROUP_NAMES = ["A", "B", "C", "D"]


def maybe_generate_next_round(fixture_pk: int) -> None:
    """Entry point called from transaction.on_commit after score entry.

    Re-fetches the fixture inside a fresh transaction to ensure latest DB state.
    Silently exits if next round already exists (idempotent).
    """
    try:
        fixture = Fixture.objects.select_related("tournament").get(pk=fixture_pk)
    except Fixture.DoesNotExist:
        return

    tournament = fixture.tournament

    if fixture.stage == FixtureStage.GROUP:
        _maybe_transition_group_to_knockout(tournament)
    elif fixture.stage == FixtureStage.KNOCKOUT:
        _maybe_advance_knockout_round(tournament, fixture.round_number)


# ---------------------------------------------------------------------------
# Group stage → knockout transition
# ---------------------------------------------------------------------------


def _maybe_transition_group_to_knockout(tournament: Tournament) -> None:
    """If all group fixtures are complete, seed the first knockout round."""
    group_fixtures = Fixture.objects.filter(
        tournament=tournament,
        stage=FixtureStage.GROUP,
    )

    # Round complete = every non-cancelled fixture is completed
    pending = group_fixtures.exclude(status__in=[FixtureStatus.COMPLETED, FixtureStatus.CANCELLED])
    if pending.exists():
        return

    # Idempotency: if KO round 1 already exists, bail
    if Fixture.objects.filter(
        tournament=tournament,
        stage=FixtureStage.KNOCKOUT,
        round_number=1,
    ).exists():
        return

    _create_knockout_from_groups(tournament)


def _create_knockout_from_groups(tournament: Tournament) -> None:
    """Determine group winners/runners-up and create first KO round."""
    from apps.tournaments.services.standings import compute_standings

    # Determine number of groups
    group_names_used = list(
        Fixture.objects.filter(tournament=tournament, stage=FixtureStage.GROUP)
        .values_list("group_name", flat=True)
        .distinct()
        .order_by("group_name")
    )

    group_results: dict[str, tuple[TournamentTeam, TournamentTeam]] = {}
    for gname in group_names_used:
        standings = compute_standings(tournament, group_name=gname)
        if len(standings) < 2:
            return  # not enough data
        group_results[gname] = (standings[0].team, standings[1].team)

    num_groups = len(group_names_used)
    # Cross-seeding: 2 groups → A1-B2, B1-A2
    #                4 groups → A1-D2, B1-C2, C1-B2, D1-A2
    if num_groups == 2:
        matchups = [
            (group_results["A"][0], group_results["B"][1]),
            (group_results["B"][0], group_results["A"][1]),
        ]
    elif num_groups == 4:
        matchups = [
            (group_results["A"][0], group_results["D"][1]),
            (group_results["B"][0], group_results["C"][1]),
            (group_results["C"][0], group_results["B"][1]),
            (group_results["D"][0], group_results["A"][1]),
        ]
    else:
        # Fallback: just pair sequentially
        matchups = []
        for i in range(num_groups // 2):
            g1 = group_names_used[i]
            g2 = group_names_used[num_groups - 1 - i]
            matchups.append((group_results[g1][0], group_results[g2][1]))
            matchups.append((group_results[g2][0], group_results[g1][1]))

    start_dt = datetime.datetime.now(tz=datetime.UTC)
    fixtures_to_create = [
        Fixture(
            tournament=tournament,
            home_team=home,
            away_team=away,
            round_number=1,
            scheduled_at=start_dt,
            status=FixtureStatus.SCHEDULED,
            stage=FixtureStage.KNOCKOUT,
            is_bye=False,
        )
        for home, away in matchups
    ]

    with transaction.atomic():
        Fixture.objects.bulk_create(fixtures_to_create)


# ---------------------------------------------------------------------------
# Knockout round advancement
# ---------------------------------------------------------------------------


def _maybe_advance_knockout_round(tournament: Tournament, current_round: int) -> None:
    """If all KO fixtures in current_round are done, generate next round."""
    round_fixtures = Fixture.objects.filter(
        tournament=tournament,
        stage=FixtureStage.KNOCKOUT,
        round_number=current_round,
    )

    pending = round_fixtures.exclude(status__in=[FixtureStatus.COMPLETED, FixtureStatus.CANCELLED])
    if pending.exists():
        return

    # Check if all are completed (not just cancelled)
    completed = round_fixtures.filter(status=FixtureStatus.COMPLETED)
    if not completed.exists():
        return

    next_round = current_round + 1

    # Idempotency
    if Fixture.objects.filter(
        tournament=tournament,
        stage=FixtureStage.KNOCKOUT,
        round_number=next_round,
    ).exists():
        return

    # Collect winners from completed fixtures (bye winners = home_team)
    winners: list[TournamentTeam] = []
    for f in round_fixtures.order_by("pk").select_related("home_team", "away_team"):
        if f.status == FixtureStatus.CANCELLED:
            continue
        if f.is_bye:
            if f.home_team:
                winners.append(f.home_team)
            continue
        if f.home_score is None or f.away_score is None:
            continue
        if f.home_score > f.away_score:
            winners.append(f.home_team)
        elif f.away_score > f.home_score:
            winners.append(f.away_team)
        # Draw in knockout: home team advances (shouldn't happen in real play)
        else:
            winners.append(f.home_team)

    if len(winners) < 2:
        # Final or not enough data — mark tournament complete if only 1 winner
        if len(winners) == 1:
            Tournament.objects.filter(pk=tournament.pk).update(status=TournamentStatus.COMPLETED)
        return

    # Generate next round: pair high seed vs low seed inward
    start_dt = datetime.datetime.now(tz=datetime.UTC)
    fixtures_to_create = []
    lo, hi = 0, len(winners) - 1
    while lo < hi:
        fixtures_to_create.append(
            Fixture(
                tournament=tournament,
                home_team=winners[lo],
                away_team=winners[hi],
                round_number=next_round,
                scheduled_at=start_dt,
                status=FixtureStatus.SCHEDULED,
                stage=FixtureStage.KNOCKOUT,
                is_bye=False,
            )
        )
        lo += 1
        hi -= 1

    with transaction.atomic():
        Fixture.objects.bulk_create(fixtures_to_create)
