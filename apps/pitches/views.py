from typing import ClassVar

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Pitch
from .serializers import PitchSerializer


class PitchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Pitch.
    Provides list, retrieve, and custom search action with geo-distance filtering.
    """

    serializer_class: ClassVar = PitchSerializer
    permission_classes: ClassVar[list] = [AllowAny]
    filter_backends: ClassVar[list] = [filters.SearchFilter]
    search_fields: ClassVar[list[str]] = ["name", "description"]

    def get_queryset(self):
        """Return active pitches with owner info pre-fetched."""
        return Pitch.objects.filter(is_active=True).select_related("owner")

    @action(
        detail=False,
        methods=["get"],
        url_path="search",
        permission_classes=[AllowAny],
    )
    def search(self, request):
        """
        Advanced search endpoint with geo-distance, filters, and full-text search.

        Query parameters:
        - lat, lng: User location for distance-based search
        - radius_km: Search radius (default: 10 km)
        - surface_type: Filter by surface (grass, artificial, futsal)
        - size: Filter by pitch size (5v5, 7v7, 11v11)
        - max_price: Filter by maximum price per hour
        - amenities: List of required amenities (can repeat)
        - q: Full-text search in name and description
        """
        queryset = self.get_queryset()

        # Geo-distance search
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius_km = request.query_params.get("radius_km")

        if lat and lng:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                # Validate coordinate ranges (WGS84)
                if -90 <= lat_f <= 90 and -180 <= lng_f <= 180:
                    point = Point(lng_f, lat_f, srid=4326)
                    radius = float(radius_km) if radius_km else 10.0
                    # Cap radius to reasonable value (e.g., 200 km)
                    radius = min(radius, 200.0)
                    queryset = (
                        queryset.filter(location__distance_lte=(point, D(km=radius)))
                        .annotate(distance=Distance("location", point))
                        .order_by("distance")
                    )
            except (ValueError, TypeError):
                # Invalid coordinates; skip geo filtering
                pass

        # Surface type filter
        surface_type = request.query_params.get("surface_type")
        if surface_type:
            queryset = queryset.filter(surface_type=surface_type)

        # Size filter
        size = request.query_params.get("size")
        if size:
            queryset = queryset.filter(size=size)

        # Price filter
        max_price = request.query_params.get("max_price")
        if max_price:
            try:
                queryset = queryset.filter(price_per_hour__lte=float(max_price))
            except (ValueError, TypeError):
                pass

        # Amenities filter (JSONField contains)
        amenities = request.query_params.getlist("amenities")
        if amenities:
            for amenity in amenities:
                queryset = queryset.filter(amenities__contains=[amenity])

        # Full-text search
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
