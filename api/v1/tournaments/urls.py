from django.urls import path

from api.v1.tournaments import (
    views_owner,
    views_public,
    views_registration,
)

urlpatterns = [
    # ------------------------------------------------------------------
    # Owner endpoints (requires IsOwner permission)
    # ------------------------------------------------------------------
    path(
        "owner/tournaments/",
        views_owner.TournamentListCreateView.as_view(),
        name="owner-tournament-list",
    ),
    path(
        "owner/tournaments/<int:pk>/",
        views_owner.TournamentDetailView.as_view(),
        name="owner-tournament-detail",
    ),
    path(
        "owner/tournaments/<int:pk>/publish/",
        views_owner.TournamentPublishView.as_view(),
        name="owner-tournament-publish",
    ),
    path(
        "owner/tournaments/<int:pk>/close-registration/",
        views_owner.TournamentCloseRegistrationView.as_view(),
        name="owner-tournament-close-reg",
    ),
    path(
        "owner/tournaments/<int:pk>/complete/",
        views_owner.TournamentCompleteView.as_view(),
        name="owner-tournament-complete",
    ),
    path(
        "owner/tournaments/<int:pk>/fixtures/<int:fixture_pk>/score/",
        views_owner.FixtureScoreView.as_view(),
        name="owner-fixture-score",
    ),
    # ------------------------------------------------------------------
    # Player registration endpoints (requires IsPlayer permission)
    # ------------------------------------------------------------------
    path(
        "tournaments/<int:pk>/register/",
        views_registration.TeamRegisterView.as_view(),
        name="tournament-team-register",
    ),
    path(
        "tournaments/join/",
        views_registration.TeamJoinView.as_view(),
        name="tournament-team-join",
    ),
    path(
        "tournaments/<int:pk>/my-team/",
        views_registration.MyTeamView.as_view(),
        name="tournament-my-team",
    ),
    # ------------------------------------------------------------------
    # Public endpoints (no auth required)
    # ------------------------------------------------------------------
    path(
        "tournaments/<int:pk>/",
        views_public.TournamentPublicDetailView.as_view(),
        name="tournament-public-detail",
    ),
    path(
        "tournaments/<int:pk>/fixtures/",
        views_public.TournamentFixtureListView.as_view(),
        name="tournament-fixture-list",
    ),
    path(
        "tournaments/<int:pk>/standings/",
        views_public.TournamentStandingsView.as_view(),
        name="tournament-standings",
    ),
]
