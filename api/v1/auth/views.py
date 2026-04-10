from __future__ import annotations

import logging
from typing import ClassVar

from apps.auth_users.models import OwnerProfile, PlayerProfile, UserRole
from apps.auth_users.otp import (
    OTPError,
    OTPExpired,
    OTPInvalid,
    OTPLockedOut,
    OTPRateLimitExceeded,
    generate_otp,
    verify_otp,
)
from apps.auth_users.permissions import IsOwner, IsPlayer
from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.auth.serializers import (
    EmailLoginSerializer,
    EmailRegisterSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    OwnerProfileSerializer,
    OwnerRegisterSerializer,
    PlayerProfileSerializer,
    UserTokenResponseSerializer,
    _jwt_pair,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _token_response(user) -> Response:
    """Return 200 with JWT pair + minimal user info."""
    tokens = _jwt_pair(user)
    return Response(
        {
            **tokens,
            "user_id": user.pk,
            "role": user.role,
            "full_name": user.full_name,
        },
        status=status.HTTP_200_OK,
    )


# ── Phone OTP — production flow ───────────────────────────────────────────────


@extend_schema(request=OTPRequestSerializer, responses={200: {"description": "OTP sent"}})
class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/

    Send a 6-digit OTP to the supplied phone number.
    Rate-limited to 3 requests per phone per 15 minutes.
    Active only when DJANGO_AUTH_BACKEND=phone.
    """

    permission_classes: ClassVar[list] = [AllowAny]
    throttle_scope = "otp_request"

    def post(self, request: Request) -> Response:
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone: str = serializer.validated_data["phone"]

        try:
            otp = generate_otp(phone)
        except OTPRateLimitExceeded:
            return Response(
                {"detail": "Too many requests. Try again in 15 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # In production, send OTP via SMS gateway here.
        # In dev/test, the OTP is logged to the console so we can inspect it.
        if settings.DEBUG:
            logger.info("OTP for %s: %s", phone, otp)

        return Response({"detail": "OTP sent."}, status=status.HTTP_200_OK)


@extend_schema(
    request=OTPVerifySerializer,
    responses={200: UserTokenResponseSerializer},
)
class OTPVerifyView(APIView):
    """
    POST /api/v1/auth/otp/verify/

    Verify OTP and return a JWT pair. Creates the user on first login.
    Active only when DJANGO_AUTH_BACKEND=phone.
    """

    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone: str = serializer.validated_data["phone"]
        otp: str = serializer.validated_data["otp"]

        try:
            verify_otp(phone, otp)
        except OTPLockedOut:
            return Response(
                {"detail": "Too many failed attempts. Phone locked for 15 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except OTPExpired:
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OTPInvalid:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OTPError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Get-or-create user by phone
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                "email": f"{phone.lstrip('+')}@placeholder.hagzkora.internal",
                "full_name": "",
                "role": UserRole.PLAYER,
            },
        )
        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return _token_response(user)


# ── Email + password — dev / staging only ─────────────────────────────────────


@extend_schema(
    request=EmailRegisterSerializer,
    responses={201: UserTokenResponseSerializer},
)
class EmailRegisterView(APIView):
    """
    POST /api/v1/auth/register/

    Register a new user with email + password.
    Only available when DJANGO_AUTH_BACKEND=email.
    """

    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = EmailRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = _jwt_pair(user)
        return Response(
            {
                **tokens,
                "user_id": user.pk,
                "role": user.role,
                "full_name": user.full_name,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    request=EmailLoginSerializer,
    responses={200: UserTokenResponseSerializer},
)
class EmailLoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticate with email + password and return a JWT pair.
    Only available when DJANGO_AUTH_BACKEND=email.
    """

    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = EmailLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return _token_response(user)


# ── JWT token management ──────────────────────────────────────────────────────


@extend_schema(
    request=LogoutSerializer,
    responses={204: None},
)
class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklist the provided refresh token (requires authentication).
    """

    permission_classes: ClassVar[list] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Player profile ────────────────────────────────────────────────────────────


class PlayerMeView(APIView):
    """
    GET  /api/v1/players/me/   — retrieve own player profile
    PATCH /api/v1/players/me/  — update own player profile
    """

    permission_classes: ClassVar[list] = [IsPlayer]

    def _get_or_create_profile(self, user) -> PlayerProfile:
        profile, _ = PlayerProfile.objects.get_or_create(user=user)
        return profile

    @extend_schema(responses={200: PlayerProfileSerializer})
    def get(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        return Response(PlayerProfileSerializer(profile).data)

    @extend_schema(request=PlayerProfileSerializer, responses={200: PlayerProfileSerializer})
    def patch(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        serializer = PlayerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ── Owner registration & profile ──────────────────────────────────────────────


@extend_schema(
    request=OwnerRegisterSerializer,
    responses={201: UserTokenResponseSerializer},
)
class OwnerRegisterView(APIView):
    """
    POST /api/v1/owners/register/

    Register a new stadium owner account (email-backend only).
    In the phone flow, owners are created via OTP verify + a follow-up
    PATCH to /api/v1/owners/me/.
    """

    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = OwnerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = _jwt_pair(user)
        return Response(
            {
                **tokens,
                "user_id": user.pk,
                "role": user.role,
                "full_name": user.full_name,
            },
            status=status.HTTP_201_CREATED,
        )


class OwnerMeView(APIView):
    """
    GET   /api/v1/owners/me/  — retrieve own owner profile
    PATCH /api/v1/owners/me/  — update own owner profile
    """

    permission_classes: ClassVar[list] = [IsOwner]

    def _get_or_create_profile(self, user) -> OwnerProfile:
        profile, _ = OwnerProfile.objects.get_or_create(
            user=user,
            defaults={"business_name_ar": "", "national_id_number": ""},
        )
        return profile

    @extend_schema(responses={200: OwnerProfileSerializer})
    def get(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        return Response(OwnerProfileSerializer(profile).data)

    @extend_schema(request=OwnerProfileSerializer, responses={200: OwnerProfileSerializer})
    def patch(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        serializer = OwnerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
