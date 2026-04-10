from django.conf import settings
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from api.v1.auth.views import (
    EmailLoginView,
    EmailRegisterView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
)

# ── Common endpoints ──────────────────────────────────────────────────────────
urlpatterns = [
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
]

# ── Auth backend: phone OTP (production) ──────────────────────────────────────
if settings.DJANGO_AUTH_BACKEND == "phone":
    urlpatterns += [
        path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
        path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    ]

# ── Auth backend: email + password (dev / staging) ────────────────────────────
else:
    urlpatterns += [
        path("register/", EmailRegisterView.as_view(), name="auth-register"),
        path("login/", EmailLoginView.as_view(), name="auth-login"),
        # Also expose OTP endpoints in dev so they can be manually tested
        path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
        path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    ]
