from typing import ClassVar

from rest_framework import serializers

from .models import Pitch


class PitchSerializer(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField()
    owner_email = serializers.ReadOnlyField(source="owner.email")

    class Meta:
        model: ClassVar = Pitch
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "description",
            "address",
            "price_per_hour",
            "surface_type",
            "amenities",
            "size",
            "owner",
            "owner_email",
            "is_active",
            "distance",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "owner", "created_at", "updated_at"]

    def get_distance(self, obj: Pitch) -> float | None:
        """Return distance in kilometers if annotated on the object."""
        if hasattr(obj, "distance") and obj.distance is not None:
            return round(obj.distance.km, 3)
        return None
