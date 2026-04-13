"""
Serializers for the stadiums API (v1).

Sections:
  - StadiumPhotoSerializer
  - OperatingHourSerializer
  - SlotSerializer
  - StadiumSerializer (owner CRUD)
  - StadiumListSerializer (lightweight list view)
  - AdminStadiumSerializer (admin review queue)
  - RejectSerializer (admin reject action)
"""

from __future__ import annotations

from apps.reviews.models import Review
from apps.stadiums.models import (
    OperatingHour,
    Slot,
    Stadium,
    StadiumPhoto,
)
from django.db.models import Avg
from rest_framework import serializers

# ---------------------------------------------------------------------------
# Photo
# ---------------------------------------------------------------------------


class StadiumPhotoSerializer(serializers.ModelSerializer):
    s3_url = serializers.SerializerMethodField()

    class Meta:
        model = StadiumPhoto
        fields = ["id", "s3_url", "thumbnail_url", "medium_url", "order", "is_cover", "created_at"]
        read_only_fields = ["id", "s3_url", "thumbnail_url", "medium_url", "created_at"]

    def get_s3_url(self, obj: StadiumPhoto) -> str:
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else ""


class StadiumPhotoUploadSerializer(serializers.ModelSerializer):
    """Used for POST (upload) — accepts an image file."""

    class Meta:
        model = StadiumPhoto
        fields = ["id", "image", "order", "is_cover"]
        read_only_fields = ["id"]

    # Magic-byte signatures for allowed image types (do NOT trust client Content-Type)
    _ALLOWED_MAGIC = (
        b"\xff\xd8\xff",  # JPEG
        b"\x89PNG\r\n\x1a\n",  # PNG
        b"RIFF",  # WebP (RIFF....WEBP)
    )

    def validate_image(self, image):
        max_size_bytes = 8 * 1024 * 1024  # 8 MB
        if image.size > max_size_bytes:
            raise serializers.ValidationError("Image file size must not exceed 8 MB.")
        # Validate actual file content via magic bytes — Content-Type is client-supplied
        # and trivially spoofable, so we never use it as the sole type guard.
        header = image.read(12)
        image.seek(0)
        if not any(header.startswith(sig) for sig in self._ALLOWED_MAGIC):
            raise serializers.ValidationError("Only JPEG, PNG, and WebP images are accepted.")
        return image

    def validate(self, attrs):
        stadium = self.context["stadium"]
        existing_count = stadium.photos.count()
        if existing_count >= 20:
            raise serializers.ValidationError("A stadium may have at most 20 photos.")
        return attrs


class StadiumPhotoUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH — allows updating order and is_cover only."""

    class Meta:
        model = StadiumPhoto
        fields = ["order", "is_cover"]


class PhotoReorderSerializer(serializers.Serializer):
    """Bulk reorder: ordered list of photo IDs."""

    photo_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        allow_empty=False,
    )


# ---------------------------------------------------------------------------
# Operating hours
# ---------------------------------------------------------------------------


class OperatingHourSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatingHour
        fields = ["id", "day_of_week", "open_time", "close_time", "is_closed"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        is_closed = attrs.get("is_closed", getattr(self.instance, "is_closed", False))
        open_time = attrs.get("open_time", getattr(self.instance, "open_time", None))
        close_time = attrs.get("close_time", getattr(self.instance, "close_time", None))

        if not is_closed:
            if not open_time:
                raise serializers.ValidationError(
                    {"open_time": "Required when the stadium is open."}
                )
            if not close_time:
                raise serializers.ValidationError(
                    {"close_time": "Required when the stadium is open."}
                )
            if open_time >= close_time:
                raise serializers.ValidationError(
                    {"close_time": "close_time must be later than open_time."}
                )
        return attrs


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = ["id", "date", "start_time", "end_time", "status"]
        read_only_fields = ["id", "date", "start_time", "end_time", "status"]


# ---------------------------------------------------------------------------
# Stadium
# ---------------------------------------------------------------------------


class StadiumSerializer(serializers.ModelSerializer):
    """
    Full serializer for owner CRUD (create / retrieve / update).
    Photos and operating hours are read-only nested representations.
    """

    photos = StadiumPhotoSerializer(many=True, read_only=True)
    operating_hours = OperatingHourSerializer(many=True, read_only=True)
    cover_photo_url = serializers.SerializerMethodField()
    avg_pitch_quality = serializers.SerializerMethodField()
    avg_facilities = serializers.SerializerMethodField()
    avg_value_for_money = serializers.SerializerMethodField()

    class Meta:
        model = Stadium
        fields = [
            "id",
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "sport_type",
            "location",
            "address_ar",
            "address_en",
            "city",
            "price_per_slot",
            "slot_duration_minutes",
            "phone",
            "whatsapp_number",
            "amenities",
            "status",
            "rejection_note",
            "avg_rating",
            "review_count",
            "photos",
            "operating_hours",
            "cover_photo_url",
            "avg_pitch_quality",
            "avg_facilities",
            "avg_value_for_money",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "rejection_note",
            "avg_rating",
            "review_count",
            "avg_pitch_quality",
            "avg_facilities",
            "avg_value_for_money",
            "created_at",
            "updated_at",
        ]

    def get_cover_photo_url(self, obj: Stadium) -> str | None:
        # Use the prefetch cache — do NOT call .filter() which bypasses it and causes N+1.
        photos = list(obj.photos.all())
        cover = next((p for p in photos if p.is_cover), None) or (photos[0] if photos else None)
        if cover is None:
            return None
        if cover.thumbnail_url:
            return cover.thumbnail_url
        request = self.context.get("request")
        return request.build_absolute_uri(cover.image.url) if request else cover.image.url

    def validate_location(self, value):
        if value is not None and value.srid != 4326:
            raise serializers.ValidationError("Location must use WGS84 (EPSG:4326).")
        return value

    def get_avg_pitch_quality(self, obj: Stadium) -> float | None:
        return Review.objects.filter(stadium=obj).aggregate(v=Avg("pitch_quality"))["v"]

    def get_avg_facilities(self, obj: Stadium) -> float | None:
        return Review.objects.filter(stadium=obj).aggregate(v=Avg("facilities"))["v"]

    def get_avg_value_for_money(self, obj: Stadium) -> float | None:
        return Review.objects.filter(stadium=obj).aggregate(v=Avg("value_for_money"))["v"]


class StadiumListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints — omits nested collections."""

    cover_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Stadium
        fields = [
            "id",
            "name_ar",
            "name_en",
            "sport_type",
            "city",
            "price_per_slot",
            "status",
            "avg_rating",
            "review_count",
            "cover_photo_url",
            "created_at",
        ]
        read_only_fields = ["avg_rating", "review_count"]

    def get_cover_photo_url(self, obj: Stadium) -> str | None:
        # Use the prefetch cache — do NOT call .filter() which bypasses it and causes N+1.
        photos = list(obj.photos.all())
        cover = next((p for p in photos if p.is_cover), None) or (photos[0] if photos else None)
        if cover is None:
            return None
        if cover.thumbnail_url:
            return cover.thumbnail_url
        request = self.context.get("request")
        return request.build_absolute_uri(cover.image.url) if request else cover.image.url


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class AdminStadiumSerializer(serializers.ModelSerializer):
    """Read-only serializer for admin review queue."""

    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    photos = StadiumPhotoSerializer(many=True, read_only=True)
    operating_hours = OperatingHourSerializer(many=True, read_only=True)

    class Meta:
        model = Stadium
        fields = [
            "id",
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "sport_type",
            "location",
            "address_ar",
            "address_en",
            "city",
            "price_per_slot",
            "slot_duration_minutes",
            "phone",
            "whatsapp_number",
            "amenities",
            "status",
            "rejection_note",
            "owner_name",
            "owner_phone",
            "photos",
            "operating_hours",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RejectSerializer(serializers.Serializer):
    rejection_note = serializers.CharField(min_length=5, max_length=1000)
