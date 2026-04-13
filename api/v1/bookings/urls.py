"""URL routes for the bookings API (v1).

Mounted under /api/v1/bookings/ by api/v1/urls.py.
"""

from __future__ import annotations

from django.urls import path

from api.v1.bookings.views import (
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
)
from api.v1.reviews.views import SubmitReviewView

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list"),
    path("<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:booking_pk>/review/", SubmitReviewView.as_view(), name="booking-review-submit"),
]
