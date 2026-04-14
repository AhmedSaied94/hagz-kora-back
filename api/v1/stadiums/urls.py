"""
Stadium URL patterns — owner-facing endpoints.

Mounted at /api/v1/stadiums/ via api/v1/urls.py.
"""

from django.urls import path

from api.v1.reviews.views import StadiumReviewListView
from api.v1.stadiums.views import (
    OperatingHoursView,
    ReorderPhotosView,
    StadiumPhotoViewSet,
    StadiumViewSet,
)

# Stadium CRUD
stadium_list = StadiumViewSet.as_view({"get": "list", "post": "create"})
stadium_detail = StadiumViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
stadium_submit = StadiumViewSet.as_view({"post": "submit"})

# Photos
photo_list_create = StadiumPhotoViewSet.as_view({"get": "list", "post": "create"})
photo_detail = StadiumPhotoViewSet.as_view({"patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("", stadium_list, name="stadium-list"),
    path("<int:pk>/", stadium_detail, name="stadium-detail"),
    path("<int:pk>/submit/", stadium_submit, name="stadium-submit"),
    path(
        "<int:stadium_id>/operating-hours/",
        OperatingHoursView.as_view(),
        name="stadium-operating-hours",
    ),
    path("<int:stadium_id>/photos/", photo_list_create, name="stadium-photos"),
    path(
        "<int:stadium_id>/photos/reorder/",
        ReorderPhotosView.as_view(),
        name="stadium-photos-reorder",
    ),
    path("<int:stadium_id>/photos/<int:photo_id>/", photo_detail, name="stadium-photo-detail"),
    path("<int:stadium_pk>/reviews/", StadiumReviewListView.as_view(), name="stadium-reviews-list"),
]
