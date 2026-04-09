"""
Integration test for GET /api/health/

Marked as integration because it hits the real DB and Redis.
Runs automatically in CI after migrations.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.integration
def test_health_check_returns_ok(api_client):
    url = reverse("health-check")
    response = api_client.get(url)

    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["checks"]["database"] == "ok"
    assert response.data["checks"]["cache"] == "ok"
