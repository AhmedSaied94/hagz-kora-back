"""Views for the bookings API (v1).

Views are thin HTTP adapters: they validate input, call a service, and map
domain exceptions to HTTP responses. All business logic lives in
`apps.bookings.services`.
"""

from __future__ import annotations

from apps.auth_users.permissions import IsPlayer
from apps.bookings.exceptions import (
    BookingLockUnavailable,
    BookingNotCancellable,
    LockAcquisitionFailed,
    SlotNotAvailable,
    StadiumInactive,
)
from apps.bookings.models import Booking
from apps.bookings.services import cancel_booking, create_booking
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from api.v1.bookings.serializers import BookingSerializer, CreateBookingSerializer


class BookingListCreateView(ListAPIView):
    """GET + POST /api/v1/bookings/

    GET  — player's own booking list (paginated).
    POST — reserve a slot for the authenticated player.
    """

    permission_classes = [IsPlayer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_create"
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(player=self.request.user)
            .select_related("slot", "stadium")
            .order_by("-created_at")
        )

    def post(self, request, *args, **kwargs):
        input_serializer = CreateBookingSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        slot_id = input_serializer.validated_data["slot_id"]

        try:
            booking = create_booking(request.user, slot_id)
        except (SlotNotAvailable, LockAcquisitionFailed) as exc:
            return Response(
                {"code": "SLOT_TAKEN", "error": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except StadiumInactive as exc:
            return Response(
                {"code": "STADIUM_INACTIVE", "error": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except BookingLockUnavailable as exc:
            return Response(
                {"code": "BOOKING_UNAVAILABLE", "error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class BookingDetailView(RetrieveAPIView):
    """GET /api/v1/bookings/<pk>/ — booking detail (scoped to current player)."""

    permission_classes = [IsPlayer]
    serializer_class = BookingSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return Booking.objects.filter(player=self.request.user).select_related("slot", "stadium")


class BookingCancelView(GenericAPIView):
    """POST /api/v1/bookings/<pk>/cancel/ — player cancels their own confirmed booking."""

    permission_classes = [IsPlayer]

    def post(self, request, pk: int):
        try:
            booking = cancel_booking(request.user, pk)
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except BookingNotCancellable as exc:
            return Response(
                {"code": "NOT_CANCELLABLE", "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # cancel_booking returns the instance with slot + stadium already loaded
        # via select_related — no second query needed.
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)
