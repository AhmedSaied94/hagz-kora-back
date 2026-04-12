"""Owner booking-management endpoints.

Mounted at /api/v1/owner/bookings/ via api/v1/urls.py.
"""

from __future__ import annotations

from django.urls import path

from api.v1.bookings.owner_views import OwnerBookingListView, OwnerCancelBookingView

urlpatterns = [
    path("", OwnerBookingListView.as_view(), name="owner-booking-list"),
    path("<int:pk>/cancel/", OwnerCancelBookingView.as_view(), name="owner-booking-cancel"),
]
