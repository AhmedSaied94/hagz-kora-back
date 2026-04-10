"""
Admin stadium-approval endpoints.

Mounted at /api/v1/admin/stadiums/ via api/v1/urls.py.
"""

from django.urls import path

from api.v1.stadiums.views import (
    AdminApproveStadiumView,
    AdminPendingStadiumListView,
    AdminRejectStadiumView,
)

urlpatterns = [
    path("pending/", AdminPendingStadiumListView.as_view(), name="admin-stadiums-pending"),
    path("<int:pk>/approve/", AdminApproveStadiumView.as_view(), name="admin-stadium-approve"),
    path("<int:pk>/reject/", AdminRejectStadiumView.as_view(), name="admin-stadium-reject"),
]
