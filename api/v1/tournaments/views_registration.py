"""Player team registration endpoints."""

from apps.auth_users.permissions import IsPlayer
from apps.tournaments.models import (
    Tournament,
    TournamentPlayer,
    TournamentStatus,
    TournamentTeam,
)
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.tournaments.serializers import (
    TeamJoinSerializer,
    TeamRegisterSerializer,
    TournamentPlayerSerializer,
    TournamentTeamSerializer,
)


class TeamRegisterView(APIView):
    """POST /api/tournaments/<id>/register/

    Register a new team. The requesting player becomes captain.
    """

    permission_classes = [IsPlayer]

    def post(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != TournamentStatus.REGISTRATION_OPEN:
            return Response(
                {"detail": "Tournament registration is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TeamRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # Re-fetch inside atomic for select_for_update
            tournament = Tournament.objects.select_for_update().get(pk=pk)

            if tournament.status != TournamentStatus.REGISTRATION_OPEN:
                return Response(
                    {"detail": "Tournament registration is not open."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_count = TournamentTeam.objects.filter(tournament=tournament).count()
            if current_count >= tournament.max_teams:
                return Response(
                    {"detail": "Tournament is full."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Ensure player isn't already in a team in this tournament
            already_in = TournamentPlayer.objects.filter(
                team__tournament=tournament,
                player=request.user,
            ).exists()
            if already_in:
                return Response(
                    {"detail": "You are already registered in this tournament."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            team = TournamentTeam.objects.create(
                tournament=tournament,
                name=serializer.validated_data["team_name"],
                captain=request.user,
            )
            TournamentPlayer.objects.create(team=team, player=request.user)

            # Auto-close if max_teams reached
            new_count = current_count + 1
            if new_count >= tournament.max_teams:
                Tournament.objects.filter(pk=tournament.pk).update(
                    status=TournamentStatus.REGISTRATION_CLOSED
                )

        return Response(TournamentTeamSerializer(team).data, status=status.HTTP_201_CREATED)


class TeamJoinView(APIView):
    """POST /api/tournaments/join/

    Join an existing team via its join_code.
    """

    permission_classes = [IsPlayer]

    def post(self, request):
        serializer = TeamJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        join_code = serializer.validated_data["join_code"].upper().strip()

        try:
            team = TournamentTeam.objects.select_related("tournament", "tournament__stadium").get(
                join_code=join_code
            )
        except TournamentTeam.DoesNotExist:
            return Response({"detail": "Invalid join code."}, status=status.HTTP_400_BAD_REQUEST)

        tournament = team.tournament

        if tournament.status != TournamentStatus.REGISTRATION_OPEN:
            return Response(
                {"detail": "Tournament registration is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Ensure player not already in any team in this tournament
            already_in = TournamentPlayer.objects.filter(
                team__tournament=tournament,
                player=request.user,
            ).exists()
            if already_in:
                return Response(
                    {"detail": "You are already registered in this tournament."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            TournamentPlayer.objects.create(team=team, player=request.user)

        return Response(TournamentTeamSerializer(team).data, status=status.HTTP_201_CREATED)


class MyTeamView(APIView):
    """GET /api/tournaments/<id>/my-team/"""

    permission_classes = [IsPlayer]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            membership = TournamentPlayer.objects.select_related("team", "team__captain").get(
                team__tournament=tournament, player=request.user
            )
        except TournamentPlayer.DoesNotExist:
            return Response(
                {"detail": "You are not registered in this tournament."},
                status=status.HTTP_404_NOT_FOUND,
            )

        team = membership.team
        teammates = TournamentPlayer.objects.filter(team=team).select_related("player")

        return Response(
            {
                "team": TournamentTeamSerializer(team).data,
                "players": TournamentPlayerSerializer(teammates, many=True).data,
            }
        )
