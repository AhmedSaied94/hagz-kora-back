from typing import ClassVar

from django.contrib import admin

from .models import Pitch


@admin.register(Pitch)
class PitchAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "name",
        "surface_type",
        "size",
        "price_per_hour",
        "owner",
        "is_active",
    ]
    list_filter: ClassVar[list[str]] = ["surface_type", "size", "is_active"]
    search_fields: ClassVar[list[str]] = ["name", "description", "address"]
