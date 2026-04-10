from rest_framework.permissions import BasePermission

from apps.auth_users.models import KycStatus, UserRole


class IsPlayer(BasePermission):
    """Allow access only to authenticated users with role=player."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_player)


class IsOwner(BasePermission):
    """Allow access only to authenticated users with role=owner."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_owner)


class IsAdmin(BasePermission):
    """Allow access only to authenticated users with role=admin."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsOwnerOrAdmin(BasePermission):
    """Allow access to owners and admins."""

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.OWNER, UserRole.ADMIN)
        )


class IsKycApproved(BasePermission):
    """
    Allow access only to owners whose KYC has been approved.

    Use this alongside ``IsOwner`` for endpoints that require an active,
    verified stadium owner (e.g. creating a stadium).
    """

    message = "KYC approval required. Please complete identity verification."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.OWNER
            and request.user.kyc_status == KycStatus.APPROVED
        )
