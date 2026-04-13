"""Owner-facing tournament management endpoints."""

from apps.auth_users.permissions import IsOwner
from apps.tournaments.models import (
    Fixture,
    FixtureStatus,
    Tournament,
    TournamentStatus,
)
from apps.tournaments.services import generate_fixtures, validate_team_count
from apps.tournaments.services.knockout import maybe_generate_next_round
from django.db import transaction
from django.db.models import Count
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.tournaments.serializers import (
    FixtureSerializer,
    ScoreEntrySerializer,
    TournamentCreateSerializer,
    TournamentSerializer,
)


class TournamentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsOwner]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TournamentCreateSerializer
        return TournamentSerializer

    def get_queryset(self):
        return (
            Tournament.objects.filter(organizer=self.request.user)
            .annotate(teams_count=Count("teams", distinct=True))
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tournament = serializer.save(organizer=request.user)
        return Response(
            TournamentSerializer(tournament).data,
            status=status.HTTP_201_CREATED,
        )


class TournamentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsOwner]
    serializer_class = TournamentSerializer

    def get_queryset(self):
        return Tournament.objects.filter(organizer=self.request.user).annotate(
            teams_count=Count("teams", distinct=True)
        )

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return TournamentCreateSerializer
        return TournamentSerializer

    def update(self, request, *args, **kwargs):
        tournament = self.get_object()
        if tournament.status != TournamentStatus.DRAFT:
            return Response(
                {"detail": "Only draft tournaments can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        tournament = self.get_object()
        if tournament.status != TournamentStatus.DRAFT:
            return Response(
                {"detail": "Only draft tournaments can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class TournamentPublishView(APIView):
    permission_classes = [IsOwner]

    def post(self, request, pk):
        tournament = self._get_tournament(request, pk)
        if tournament is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != TournamentStatus.DRAFT:
            return Response(
                {"detail": "Only draft tournaments can be published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tournament.status = TournamentStatus.REGISTRATION_OPEN
        tournament.save(update_fields=["status", "updated_at"])
        return Response(TournamentSerializer(tournament).data)

    def _get_tournament(self, request, pk) -> Tournament | None:
        try:
            return Tournament.objects.get(pk=pk, organizer=request.user)
        except Tournament.DoesNotExist:
            return None


class TournamentCloseRegistrationView(APIView):
    permission_classes = [IsOwner]

    def post(self, request, pk):
        try:
            tournament = Tournament.objects.prefetch_related("teams").get(
                pk=pk, organizer=request.user
            )
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status not in (
            TournamentStatus.REGISTRATION_OPEN,
            TournamentStatus.REGISTRATION_CLOSED,
        ):
            return Response(
                {"detail": "Registration can only be closed when open or already closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_team_count(tournament)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                generate_fixtures(tournament)
                tournament.status = TournamentStatus.IN_PROGRESS
                tournament.save(update_fields=["status", "updated_at"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TournamentSerializer(tournament).data)


class TournamentCompleteView(APIView):
    permission_classes = [IsOwner]

    def post(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk, organizer=request.user)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != TournamentStatus.IN_PROGRESS:
            return Response(
                {"detail": "Only in-progress tournaments can be completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tournament.status = TournamentStatus.COMPLETED
        tournament.save(update_fields=["status", "updated_at"])
        return Response(TournamentSerializer(tournament).data)


class FixtureScoreView(APIView):
    permission_classes = [IsOwner]

    def patch(self, request, pk, fixture_pk):
        try:
            tournament = Tournament.objects.get(pk=pk, organizer=request.user)
        except Tournament.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != TournamentStatus.IN_PROGRESS:
            return Response(
                {"detail": "Scores can only be entered for in-progress tournaments."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fixture = Fixture.objects.select_related("home_team", "away_team").get(
                pk=fixture_pk, tournament=tournament
            )
        except Fixture.DoesNotExist:
            return Response({"detail": "Fixture not found."}, status=status.HTTP_404_NOT_FOUND)

        if fixture.is_bye:
            return Response(
                {"detail": "Cannot enter scores for bye fixtures."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fixture.status == FixtureStatus.CANCELLED:
            return Response(
                {"detail": "Cannot enter scores for cancelled fixtures."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ScoreEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fixture.home_score = serializer.validated_data["home_score"]
        fixture.away_score = serializer.validated_data["away_score"]
        fixture.status = FixtureStatus.COMPLETED
        fixture.save(update_fields=["home_score", "away_score", "status", "updated_at"])

        # Trigger next-round generation after the transaction commits
        fixture_pk_local = fixture.pk
        transaction.on_commit(lambda: maybe_generate_next_round(fixture_pk_local))

        return Response(FixtureSerializer(fixture).data)
