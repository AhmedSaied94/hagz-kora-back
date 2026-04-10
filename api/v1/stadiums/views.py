"""
Views for the stadiums API (v1).

Sections:
  Owner
    - StadiumViewSet            — CRUD for own stadiums + submit action
    - OperatingHoursView        — GET/PUT operating hours for a stadium
    - StadiumPhotoViewSet       — Upload / list / update / delete photos
    - ReorderPhotosView         — Bulk reorder photos
    - BlockSlotView             — Block a slot
    - UnblockSlotView           — Unblock a slot

  Admin
    - AdminPendingStadiumListView  — Queue of pending_review stadiums
    - AdminApproveStadiumView      — Approve a stadium
    - AdminRejectStadiumView       — Reject a stadium with a note
"""

from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.stadiums.serializers import (
    AdminStadiumSerializer,
    OperatingHourSerializer,
    PhotoReorderSerializer,
    RejectSerializer,
    SlotSerializer,
    StadiumListSerializer,
    StadiumPhotoSerializer,
    StadiumPhotoUpdateSerializer,
    StadiumPhotoUploadSerializer,
    StadiumSerializer,
)
from apps.auth_users.permissions import IsAdmin, IsOwner
from apps.stadiums.models import OperatingHour, Slot, SlotStatus, Stadium, StadiumPhoto, StadiumStatus


# ---------------------------------------------------------------------------
# Owner — Stadium CRUD
# ---------------------------------------------------------------------------


class StadiumViewSet(viewsets.ModelViewSet):
    """
    Owner-only CRUD for stadiums.

    - list / retrieve: own stadiums only
    - create: always starts as draft
    - update / partial_update: only draft or pending_review stadiums
    - destroy: only draft stadiums
    - submit: POST /stadiums/<id>/submit/ — draft → pending_review
    """

    permission_classes = [IsOwner]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Stadium.objects.filter(owner=self.request.user)
            .prefetch_related("photos", "operating_hours")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return StadiumListSerializer
        return StadiumSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, status=StadiumStatus.DRAFT)

    def update(self, request: Request, *args, **kwargs):
        stadium = self.get_object()
        if stadium.status not in (StadiumStatus.DRAFT, StadiumStatus.PENDING_REVIEW):
            return Response(
                {"detail": "Only draft or pending_review stadiums can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request: Request, *args, **kwargs):
        stadium = self.get_object()
        if stadium.status != StadiumStatus.DRAFT:
            return Response(
                {"detail": "Only draft stadiums can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request: Request, pk=None):
        """Submit a draft stadium for admin review."""
        stadium = self.get_object()
        # Use the prefetch cache — .exists()/.filter() bypass it and cause extra queries.
        photos = list(stadium.photos.all())
        if not photos:
            return Response(
                {"detail": "Upload at least one photo before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not any(p.is_cover for p in photos):
            return Response(
                {"detail": "Designate a cover photo before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            stadium.submit_for_review()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = StadiumSerializer(stadium, context={"request": request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Owner — Operating hours
# ---------------------------------------------------------------------------


class OperatingHoursView(APIView):
    """
    GET  /stadiums/<stadium_id>/operating-hours/  — list all 7 days
    PUT  /stadiums/<stadium_id>/operating-hours/  — bulk replace all days
    """

    permission_classes = [IsOwner]

    def _get_stadium(self, request: Request, stadium_id: int) -> Stadium:
        return get_object_or_404(Stadium, pk=stadium_id, owner=request.user)

    def get(self, request: Request, stadium_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)
        hours = stadium.operating_hours.all()
        serializer = OperatingHourSerializer(hours, many=True)
        return Response(serializer.data)

    def put(self, request: Request, stadium_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)

        if not isinstance(request.data, list):
            return Response(
                {"detail": "Expected a list of operating hours."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OperatingHourSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            stadium.operating_hours.all().delete()
            OperatingHour.objects.bulk_create([
                OperatingHour(stadium=stadium, **item)
                for item in serializer.validated_data
            ])

        hours = stadium.operating_hours.all()
        return Response(OperatingHourSerializer(hours, many=True).data)


# ---------------------------------------------------------------------------
# Owner — Photos
# ---------------------------------------------------------------------------


class StadiumPhotoViewSet(viewsets.ViewSet):
    """
    Photo management for a single stadium (owner only).

    list   GET    /stadiums/<stadium_id>/photos/
    create POST   /stadiums/<stadium_id>/photos/
    update PATCH  /stadiums/<stadium_id>/photos/<photo_id>/
    delete DELETE /stadiums/<stadium_id>/photos/<photo_id>/
    """

    permission_classes = [IsOwner]
    parser_classes = [MultiPartParser, FormParser]

    def _get_stadium(self, request: Request, stadium_id: int) -> Stadium:
        return get_object_or_404(Stadium, pk=stadium_id, owner=request.user)

    def _get_photo(self, stadium: Stadium, photo_id: int) -> StadiumPhoto:
        return get_object_or_404(StadiumPhoto, pk=photo_id, stadium=stadium)

    def list(self, request: Request, stadium_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)
        photos = stadium.photos.all()
        serializer = StadiumPhotoSerializer(photos, many=True, context={"request": request})
        return Response(serializer.data)

    def create(self, request: Request, stadium_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)
        serializer = StadiumPhotoUploadSerializer(
            data=request.data,
            context={"stadium": stadium, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        # If this is the first photo, make it the cover automatically
        is_first = not stadium.photos.exists()
        photo = serializer.save(stadium=stadium, is_cover=is_first)

        # Kick off async variant generation
        from apps.stadiums.tasks import process_stadium_photo
        process_stadium_photo.delay(photo.pk)

        out = StadiumPhotoSerializer(photo, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, stadium_id: int, photo_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)
        photo = self._get_photo(stadium, photo_id)
        serializer = StadiumPhotoUpdateSerializer(photo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Enforce single cover: clear previous cover if setting a new one
        if serializer.validated_data.get("is_cover"):
            with transaction.atomic():
                stadium.photos.exclude(pk=photo.pk).filter(is_cover=True).update(is_cover=False)
                updated_photo = serializer.save()
        else:
            updated_photo = serializer.save()

        out = StadiumPhotoSerializer(updated_photo, context={"request": request})
        return Response(out.data)

    def destroy(self, request: Request, stadium_id: int, photo_id: int) -> Response:
        stadium = self._get_stadium(request, stadium_id)
        photo = self._get_photo(stadium, photo_id)
        photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReorderPhotosView(APIView):
    """POST /stadiums/<stadium_id>/photos/reorder/ — set order from a list of IDs."""

    permission_classes = [IsOwner]

    def post(self, request: Request, stadium_id: int) -> Response:
        stadium = get_object_or_404(Stadium, pk=stadium_id, owner=request.user)
        serializer = PhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo_ids: list[int] = serializer.validated_data["photo_ids"]

        existing_ids = set(stadium.photos.values_list("pk", flat=True))
        if set(photo_ids) != existing_ids:
            return Response(
                {"detail": "photo_ids must contain exactly the IDs of this stadium's photos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for order, photo_id in enumerate(photo_ids):
                StadiumPhoto.objects.filter(pk=photo_id, stadium=stadium).update(order=order)

        photos = stadium.photos.all()
        return Response(StadiumPhotoSerializer(photos, many=True, context={"request": request}).data)


# ---------------------------------------------------------------------------
# Owner — Slot blocking
# ---------------------------------------------------------------------------


class BlockSlotView(APIView):
    """POST /owner/stadiums/<stadium_id>/slots/<slot_id>/block/"""

    permission_classes = [IsOwner]

    def post(self, request: Request, stadium_id: int, slot_id: int) -> Response:
        stadium = get_object_or_404(Stadium, pk=stadium_id, owner=request.user)

        with transaction.atomic():
            slot = get_object_or_404(
                Slot.objects.select_for_update(), pk=slot_id, stadium=stadium
            )
            if slot.status == SlotStatus.BOOKED:
                return Response(
                    {"detail": "Cannot block a booked slot."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if slot.status == SlotStatus.BLOCKED:
                return Response(
                    {"detail": "Slot is already blocked."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            slot.status = SlotStatus.BLOCKED
            slot.save(update_fields=["status", "updated_at"])

        return Response(SlotSerializer(slot).data)


class UnblockSlotView(APIView):
    """POST /owner/stadiums/<stadium_id>/slots/<slot_id>/unblock/"""

    permission_classes = [IsOwner]

    def post(self, request: Request, stadium_id: int, slot_id: int) -> Response:
        stadium = get_object_or_404(Stadium, pk=stadium_id, owner=request.user)

        with transaction.atomic():
            slot = get_object_or_404(
                Slot.objects.select_for_update(), pk=slot_id, stadium=stadium
            )
            if slot.status != SlotStatus.BLOCKED:
                return Response(
                    {"detail": "Only blocked slots can be unblocked."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            slot.status = SlotStatus.AVAILABLE
            slot.save(update_fields=["status", "updated_at"])

        return Response(SlotSerializer(slot).data)


# ---------------------------------------------------------------------------
# Admin — Stadium approval workflow
# ---------------------------------------------------------------------------


class AdminPendingStadiumListView(generics.ListAPIView):
    """GET /admin/stadiums/pending/ — paginated queue of pending_review stadiums."""

    permission_classes = [IsAdmin]
    serializer_class = AdminStadiumSerializer

    def get_queryset(self):
        return (
            Stadium.objects.filter(status=StadiumStatus.PENDING_REVIEW)
            .select_related("owner")
            .prefetch_related("photos", "operating_hours")
            .order_by("created_at")
        )


class AdminApproveStadiumView(APIView):
    """POST /admin/stadiums/<id>/approve/"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, pk: int) -> Response:
        stadium = get_object_or_404(Stadium, pk=pk)
        try:
            stadium.approve()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Trigger slot generation only for this newly active stadium
        from apps.stadiums.tasks import generate_slots_for_stadium
        generate_slots_for_stadium.delay(stadium.pk)

        # Notify owner (fire-and-forget; notification app is Phase 6)
        _notify_owner_approval(stadium)

        return Response({"detail": "Stadium approved.", "id": stadium.pk})


class AdminRejectStadiumView(APIView):
    """POST /admin/stadiums/<id>/reject/"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, pk: int) -> Response:
        stadium = get_object_or_404(Stadium, pk=pk)
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            stadium.reject(note=serializer.validated_data["rejection_note"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _notify_owner_rejection(stadium)

        return Response({"detail": "Stadium rejected.", "id": stadium.pk})


# ---------------------------------------------------------------------------
# Notification stubs (Phase 6 will implement real delivery)
# ---------------------------------------------------------------------------


def _notify_owner_approval(stadium: Stadium) -> None:
    """Placeholder — Phase 6 wires up FCM + SMS."""


def _notify_owner_rejection(stadium: Stadium) -> None:
    """Placeholder — Phase 6 wires up FCM + SMS."""
