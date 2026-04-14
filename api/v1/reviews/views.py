"""Views for the reviews API (v1)."""

from __future__ import annotations

from apps.auth_users.permissions import IsOwner, IsPlayer
from apps.bookings.models import Booking, BookingStatus
from apps.reviews.models import Review
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

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

        # Wrap in atomic + catch IntegrityError so a concurrent duplicate request
        # returns a clean 400 instead of an unhandled 500 (DB unique constraint).
        try:
            with transaction.atomic():
                serializer.save(
                    booking=booking,
                    player=self.request.user,
                    stadium=booking.stadium,
                )
        except IntegrityError:
            raise ValidationError(
                {"detail": "A review has already been submitted for this booking."}
            ) from None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Re-serialize with full ReviewSerializer; use saved instance pk — no second booking fetch.
        review = Review.objects.select_related("player", "stadium", "booking").get(
            pk=serializer.instance.pk
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class StadiumReviewListView(generics.ListAPIView):
    """Public list of reviews for a stadium.

    GET /api/v1/stadiums/<stadium_pk>/reviews/
    """

    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer
    pagination_class = PageNumberPagination
    queryset = Review.objects.none()  # overridden by get_queryset; satisfies drf-spectacular

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
        if serializer.instance.stadium.owner != self.request.user:
            raise PermissionDenied("You do not own this stadium.")
        serializer.save()

    def post(self, request, *args, **kwargs):
        """Route POST to the same partial-update handler as PATCH."""
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Inline partial update to keep a single get_object() call and return
        # the full ReviewSerializer representation in the response.
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(ReviewSerializer(serializer.instance).data)
