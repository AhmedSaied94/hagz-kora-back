from __future__ import annotations

from typing import ClassVar

from apps.notifications.models import DeviceToken
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.notifications.serializers import DeviceTokenSerializer


class DeviceTokenView(APIView):
    """
    POST   /api/v1/devices/         — register (or reactivate) an FCM token
    DELETE /api/v1/devices/<token>/ — deregister a token on logout
    """

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @extend_schema(request=DeviceTokenSerializer, responses={201: DeviceTokenSerializer})
    def post(self, request: Request) -> Response:
        serializer = DeviceTokenSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, token: str) -> Response:
        DeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
