"""Owner-specific booking views for the v1 API.

These views allow stadium owners to view and manage bookings for their stadiums.
Mounted at /api/v1/owner/bookings/ via api/v1/urls.py.
"""

from __future__ import annotations

from apps.auth_users.permissions import IsOwner
from apps.bookings.exceptions import BookingNotCancellable
from apps.bookings.models import Booking
from apps.bookings.services import cancel_booking_by_owner
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from api.v1.bookings.serializers import BookingSerializer, OwnerCancelBookingSerializer


class OwnerBookingListView(ListAPIView):
    """GET /api/v1/owner/bookings/ — bookings for all stadiums owned by the user."""

    permission_classes = [IsOwner]
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(stadium__owner=self.request.user)
            .select_related("slot", "stadium", "player")
            .order_by("-created_at")
        )


class OwnerCancelBookingView(GenericAPIView):
    """POST /api/v1/owner/bookings/<pk>/cancel/ — owner cancels a confirmed booking.

    Owner can cancel any confirmed booking for their stadiums with no time
    restriction. A non-empty cancellation_reason is required. On success the
    slot is returned to 'available' and the player receives an async notification.
    """

    permission_classes = [IsOwner]
    serializer_class = OwnerCancelBookingSerializer

    def post(self, request, pk: int) -> Response:
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Surface the first validation error as REASON_REQUIRED.
            return Response(
                {"code": "REASON_REQUIRED", "error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason: str = serializer.validated_data["cancellation_reason"]

        try:
            booking = cancel_booking_by_owner(
                owner=request.user,
                booking_id=pk,
                reason=reason,
            )
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except BookingNotCancellable:
            return Response(
                {"code": "NOT_CANCELLABLE", "error": "This booking cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"code": "REASON_REQUIRED", "error": "A cancellation reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = BookingSerializer(booking)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
