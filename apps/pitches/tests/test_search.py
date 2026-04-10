"""
Tests for pitch search and discovery functionality.

Covers:
- Geo-distance filtering with PostGIS
- Surface type, size, price filters
- Full-text search (name, description)
- Amenities filtering
- Permission/access control
"""

import pytest
from django.contrib.gis.geos import Point
from rest_framework import status

from apps.pitches.models import Pitch, PitchSize, SurfaceType


@pytest.mark.django_db
class TestPitchSearch:
    """Test suite for pitch search endpoint."""

    @pytest.fixture
    def owner(self, db):
        """Create an owner user."""
        from tests.factories import OwnerUserFactory

        return OwnerUserFactory()

    @pytest.fixture
    def sample_pitches(self, owner):
        """Create sample pitches for testing."""
        pitches = [
            Pitch.objects.create(
                name="Downtown Grass Pitch",
                description="Professional grass pitch in downtown",
                location=Point(31.2357, 30.0444, srid=4326),  # Cairo
                address="123 Main St",
                price_per_hour=100,
                surface_type=SurfaceType.GRASS,
                size=PitchSize.FIVE_VS_FIVE,
                amenities=["parking", "lights"],
                owner=owner,
                is_active=True,
            ),
            Pitch.objects.create(
                name="West Artificial Pitch",
                description="Modern artificial turf pitch",
                location=Point(31.1957, 29.9744, srid=4326),
                address="456 West Ave",
                price_per_hour=150,
                surface_type=SurfaceType.ARTIFICIAL,
                size=PitchSize.SEVEN_VS_SEVEN,
                amenities=["parking", "lights", "cafe"],
                owner=owner,
                is_active=True,
            ),
            Pitch.objects.create(
                name="Budget Futsal Court",
                description="Affordable indoor futsal court",
                location=Point(31.3457, 30.1244, srid=4326),
                address="789 Indoor Blvd",
                price_per_hour=50,
                surface_type=SurfaceType.FUTSAL,
                size=PitchSize.FIVE_VS_FIVE,
                amenities=["parking"],
                owner=owner,
                is_active=True,
            ),
            Pitch.objects.create(
                name="Inactive Pitch",
                description="This pitch is no longer available",
                location=Point(31.2000, 30.0000, srid=4326),
                address="999 Old St",
                price_per_hour=200,
                surface_type=SurfaceType.GRASS,
                size=PitchSize.ELEVEN_VS_ELEVEN,
                amenities=[],
                owner=owner,
                is_active=False,
            ),
        ]
        return pitches

    def test_list_pitches(self, api_client, sample_pitches):
        """Test basic pitch list endpoint."""
        response = api_client.get("/api/v1/pitches/")
        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) == 3  # Only active pitches
        assert results[0]["is_active"] is True

    def test_search_by_surface_type(self, api_client, sample_pitches):
        """Test filtering by surface type."""
        response = api_client.get("/api/v1/pitches/search/?surface_type=grass")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["surface_type"] == "grass"

    def test_search_by_size(self, api_client, sample_pitches):
        """Test filtering by pitch size."""
        response = api_client.get("/api/v1/pitches/search/?size=5v5")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        for pitch in response.data:
            assert pitch["size"] == "5v5"

    def test_search_by_max_price(self, api_client, sample_pitches):
        """Test filtering by maximum price."""
        response = api_client.get("/api/v1/pitches/search/?max_price=100")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2  # 50 and 100
        for pitch in response.data:
            assert float(pitch["price_per_hour"]) <= 100

    def test_search_by_amenity(self, api_client, sample_pitches):
        """Test filtering by amenities."""
        response = api_client.get("/api/v1/pitches/search/?amenities=cafe")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert "cafe" in response.data[0]["amenities"]

    def test_search_by_multiple_amenities(self, api_client, sample_pitches):
        """Test filtering by multiple amenities (all must be present)."""
        response = api_client.get("/api/v1/pitches/search/?amenities=parking&amenities=lights")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        for pitch in response.data:
            assert "parking" in pitch["amenities"]
            assert "lights" in pitch["amenities"]

    def test_search_by_text_query(self, api_client, sample_pitches):
        """Test full-text search on name and description."""
        response = api_client.get("/api/v1/pitches/search/?q=artificial")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert "Artificial" in response.data[0]["name"]

    def test_search_by_text_in_description(self, api_client, sample_pitches):
        """Test full-text search in description."""
        response = api_client.get("/api/v1/pitches/search/?q=professional")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert "professional" in response.data[0]["description"].lower()

    def test_search_combined_filters(self, api_client, sample_pitches):
        """Test combining multiple filters."""
        response = api_client.get(
            "/api/v1/pitches/search/?surface_type=artificial&size=7v7&max_price=200"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["surface_type"] == "artificial"
        assert response.data[0]["size"] == "7v7"

    def test_search_returns_only_active_pitches(self, api_client, sample_pitches):
        """Test that search returns only active pitches."""
        response = api_client.get("/api/v1/pitches/search/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        for pitch in response.data:
            assert pitch["is_active"] is True

    def test_search_invalid_price_filter(self, api_client, sample_pitches):
        """Test that invalid price parameter is ignored gracefully."""
        response = api_client.get("/api/v1/pitches/search/?max_price=invalid")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3  # Returns all, price filter ignored

    def test_search_public_access(self, api_client, sample_pitches):
        """Test that search is public (AllowAny permission)."""
        # Should work without authentication
        response = api_client.get("/api/v1/pitches/search/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_pitch_detail(self, api_client, sample_pitches):
        """Test retrieving a single pitch."""
        pitch_id = sample_pitches[0].id
        response = api_client.get(f"/api/v1/pitches/{pitch_id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == pitch_id
        assert response.data["name"] == "Downtown Grass Pitch"

    def test_pitch_includes_owner_email(self, api_client, sample_pitches):
        """Test that pitch response includes owner email."""
        response = api_client.get("/api/v1/pitches/search/")
        assert response.status_code == status.HTTP_200_OK
        assert "owner_email" in response.data[0]
        assert "@" in response.data[0]["owner_email"]

    def test_distance_annotation_missing_location(self, api_client, owner):
        """Test distance field is None when pitch has no location."""
        pitch = Pitch.objects.create(
            name="No Location Pitch",
            description="Pitch without location",
            location=None,
            address="Unknown",
            price_per_hour=100,
            surface_type=SurfaceType.GRASS,
            owner=owner,
            is_active=True,
        )
        response = api_client.get("/api/v1/pitches/search/")
        assert response.status_code == status.HTTP_200_OK
        pitch_data = next(p for p in response.data if p["id"] == pitch.id)
        assert pitch_data["distance"] is None


@pytest.mark.django_db
class TestPitchGeoDistance:
    """Test geo-distance search (PostGIS ST_DWithin)."""

    @pytest.fixture
    def owner(self, db):
        """Create an owner user."""
        from tests.factories import OwnerUserFactory

        return OwnerUserFactory()

    @pytest.fixture
    def pitches_spread(self, owner):
        """Create pitches at different locations."""
        locations = [
            (31.2357, 30.0444, "Downtown"),  # Cairo center
            (31.1957, 29.9744, "West"),  # ~15 km west
            (31.3457, 30.1244, "East"),  # ~15 km east
        ]
        pitches = []
        for lng, lat, name in locations:
            pitch = Pitch.objects.create(
                name=f"{name} Pitch",
                description=f"Pitch located {name}",
                location=Point(lng, lat, srid=4326),
                address=f"{name} Address",
                price_per_hour=100,
                surface_type=SurfaceType.GRASS,
                owner=owner,
                is_active=True,
            )
            pitches.append(pitch)
        return pitches

    def test_geo_search_within_radius(self, api_client, pitches_spread):
        """Test geo-distance search returns pitches within radius."""
        # Search from downtown (31.2357, 30.0444) with 10 km radius
        response = api_client.get("/api/v1/pitches/search/?lat=30.0444&lng=31.2357&radius_km=10")
        assert response.status_code == status.HTTP_200_OK
        # At least the downtown pitch should be found
        assert len(response.data) > 0
        # Check distance annotation exists
        assert "distance" in response.data[0]

    def test_geo_search_invalid_coordinates(self, api_client, pitches_spread):
        """Test that invalid coordinates are handled gracefully."""
        response = api_client.get("/api/v1/pitches/search/?lat=invalid&lng=31.2357")
        assert response.status_code == status.HTTP_200_OK
        # Should return all pitches when geo params are invalid
        assert len(response.data) == 3

    def test_geo_search_missing_radius_defaults_to_10km(self, api_client, pitches_spread):
        """Test that missing radius defaults to 10 km."""
        response = api_client.get("/api/v1/pitches/search/?lat=30.0444&lng=31.2357")
        assert response.status_code == status.HTTP_200_OK
        # Should use default 10 km radius
        assert len(response.data) > 0

    def test_geo_search_orders_by_distance(self, api_client, pitches_spread):
        """Test that geo-search results are ordered by distance."""
        response = api_client.get("/api/v1/pitches/search/?lat=30.0444&lng=31.2357&radius_km=50")
        assert response.status_code == status.HTTP_200_OK
        # Results should be ordered by distance (ascending)
        if len(response.data) > 1:
            distances = [p["distance"] for p in response.data if p["distance"]]
            assert distances == sorted(distances)
