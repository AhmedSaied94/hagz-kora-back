"""Views for the reviews API (v1)."""

from __future__ import annotations

from apps.auth_users.permissions import IsOwner, IsPlayer
from apps.bookings.models import Booking, BookingStatus
from apps.reviews.models import Review
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated

from api.v1.reviews.serializers import (
    OwnerResponseSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
)


class SubmitReviewView(generics.CreateAPIView):
    """Player submits a review for a completed booking.

    POST /api/v1/bookings/<booking_pk>/review/
    """

    permission_classes = [IsAuthenticated, IsPlayer]
    serializer_class = ReviewCreateSerializer

    def perform_create(self, serializer: ReviewCreateSerializer) -> None:
        booking_pk = self.kwargs["booking_pk"]
        booking = get_object_or_404(
            Booking.objects.select_related("player", "stadium"),
            pk=booking_pk,
        )

        if booking.player != self.request.user:
            raise PermissionDenied("You do not have permission to review this booking.")

        if booking.status != BookingStatus.COMPLETED:
            raise ValidationError(
                {"detail": "Review can only be submitted for completed bookings."}
            )

        if Review.objects.filter(booking=booking).exists():
            raise ValidationError(
                {"detail": "A review has already been submitted for this booking."}
            )

        serializer.save(
            booking=booking,
            player=self.request.user,
            stadium=booking.stadium,
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Re-serialize with full read serializer for the 201 response body
        booking_pk = self.kwargs["booking_pk"]
        booking = get_object_or_404(
            Booking.objects.select_related("player", "stadium"),
            pk=booking_pk,
        )
        review = Review.objects.select_related("player", "stadium", "booking").get(booking=booking)
        response.data = ReviewSerializer(review).data
        return response


class StadiumReviewListView(generics.ListAPIView):
    """Public list of reviews for a stadium.

    GET /api/v1/stadiums/<stadium_pk>/reviews/
    """

    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        stadium_pk = self.kwargs["stadium_pk"]
        return (
            Review.objects.filter(stadium_id=stadium_pk)
            .select_related("player")
            .order_by("-created_at")
        )


class OwnerRespondView(generics.UpdateAPIView):
    """Owner posts or updates a response to a review.

    POST/PATCH /api/v1/owner/stadiums/<stadium_pk>/reviews/<pk>/respond/
    """

    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = OwnerResponseSerializer
    http_method_names = ["post", "patch", "head", "options"]

    def get_queryset(self):
        stadium_pk = self.kwargs["stadium_pk"]
        return Review.objects.filter(stadium_id=stadium_pk).select_related("stadium__owner")

    def perform_update(self, serializer: OwnerResponseSerializer) -> None:
        instance = serializer.instance
        if instance.stadium.owner != self.request.user:
            raise PermissionDenied("You do not own this stadium.")
        instance.owner_response = serializer.validated_data["owner_response"]
        instance.save(update_fields=["owner_response", "updated_at"])

    def post(self, request, *args, **kwargs):
        """Route POST to the same partial-update handler as PATCH."""
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Allow POST to behave like PATCH (partial update)
        kwargs["partial"] = True
        response = super().update(request, *args, **kwargs)
        review = self.get_object()
        response.data = ReviewSerializer(review).data
        return response
