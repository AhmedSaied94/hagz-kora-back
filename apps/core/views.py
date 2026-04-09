from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/

    Checks DB and Redis connectivity.
    Returns 200 if all backing services are reachable, 503 otherwise.
    Used by load balancers and container orchestration.
    """
    checks = {}
    healthy = True

    # Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        healthy = False

    # Redis / cache
    try:
        cache.set("health_check_ping", "pong", timeout=5)
        result = cache.get("health_check_ping")
        checks["cache"] = "ok" if result == "pong" else "error"
        if result != "pong":
            healthy = False
    except Exception:
        checks["cache"] = "error"
        healthy = False

    status_code = 200 if healthy else 503
    return Response(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=status_code,
    )
