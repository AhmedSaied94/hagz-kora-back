"""Public (no-auth) tournament read endpoints."""

from apps.tournaments.models import Fixture, FixtureStage, Tournament, TournamentTeam
from apps.tournaments.services.standings import compute_standings
from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.tournaments.serializers import (
    FixtureSerializer,
    PublicTournamentTeamSerializer,
    StandingRowSerializer,
    TournamentSerializer,
)


class TournamentPublicDetailView(APIView):
    """GET /api/tournaments/<id>/"""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        teams = (
            TournamentTeam.objects.filter(tournament=tournament)
            .select_related("captain")
            .annotate(players_count=Count("players"))
        )
        return Response(
            {
                "tournament": TournamentSerializer(tournament).data,
                "teams": PublicTournamentTeamSerializer(teams, many=True).data,
            }
        )


class TournamentFixtureListView(APIView):
    """GET /api/tournaments/<id>/fixtures/"""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        fixtures = (
            Fixture.objects.filter(tournament=tournament)
            .select_related("home_team", "away_team")
            .order_by("round_number", "stage", "group_name", "scheduled_at")
        )
        return Response(FixtureSerializer(fixtures, many=True).data)


class TournamentStandingsView(APIView):
    """GET /api/tournaments/<id>/standings/

    Returns standings for round-robin tournaments.
    For group-knockout tournaments, returns per-group standings under a
    'groups' key plus knockout fixtures.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Detect if tournament has group stage
        group_names = list(
            Fixture.objects.filter(tournament=tournament, stage=FixtureStage.GROUP)
            .values_list("group_name", flat=True)
            .distinct()
            .order_by("group_name")
        )

        if group_names:
            groups = {}
            for gname in group_names:
                rows = compute_standings(tournament, group_name=gname)
                groups[gname] = StandingRowSerializer(rows, many=True).data
            return Response({"type": "group_knockout", "groups": groups})

        # Plain round-robin
        rows = compute_standings(tournament)
        return Response(
            {
                "type": "round_robin",
                "standings": StandingRowSerializer(rows, many=True).data,
            }
        )
