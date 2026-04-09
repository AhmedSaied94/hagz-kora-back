from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Health check (no version prefix — used by load balancers)
    path("api/health/", include("apps.core.urls")),

    # REST API v1 — all serializers and views live in api/v1/
    path("api/v1/", include("api.v1.urls")),

    # Owner dashboard (server-rendered, session auth)
    path("owner/", include("apps.dashboards.owner_urls")),

    # Admin dashboard (server-rendered, session auth — not Django Admin)
    path("admin-panel/", include("apps.dashboards.admin_urls")),

    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
