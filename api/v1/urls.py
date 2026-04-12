"""
API v1 URL aggregator.
Mounted at /api/v1/ in config/urls.py.
Each sub-module registers its own urlpatterns here.
"""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("api.v1.auth.urls")),
    path("players/", include("api.v1.auth.player_urls")),
    path("owners/", include("api.v1.auth.owner_urls")),
    path("stadiums/", include("api.v1.stadiums.urls")),
    path("owner/stadiums/", include("api.v1.stadiums.owner_urls")),
    path("owner/bookings/", include("api.v1.bookings.owner_urls")),
    path("admin/stadiums/", include("api.v1.stadiums.admin_urls")),
    path("bookings/", include("api.v1.bookings.urls")),
    path("tournaments/", include("api.v1.tournaments.urls")),
    path("reviews/", include("api.v1.reviews.urls")),
    path("notifications/", include("api.v1.notifications.urls")),
    path("devices/", include("api.v1.notifications.device_urls")),
    path("", include("apps.pitches.urls")),
]
