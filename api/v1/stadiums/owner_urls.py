"""
Owner slot-management endpoints.

Mounted at /api/v1/owner/stadiums/ via api/v1/urls.py.
"""

from django.urls import path

from api.v1.reviews.views import OwnerRespondView
from api.v1.stadiums.views import BlockSlotView, UnblockSlotView

urlpatterns = [
    path(
        "<int:stadium_id>/slots/<int:slot_id>/block/",
        BlockSlotView.as_view(),
        name="owner-slot-block",
    ),
    path(
        "<int:stadium_id>/slots/<int:slot_id>/unblock/",
        UnblockSlotView.as_view(),
        name="owner-slot-unblock",
    ),
    path(
        "<int:stadium_pk>/reviews/<int:pk>/respond/",
        OwnerRespondView.as_view(),
        name="review-owner-respond",
    ),
]
