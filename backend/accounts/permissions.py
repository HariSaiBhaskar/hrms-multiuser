"""Role-based permission classes, shared by every viewset."""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


class IsAdmin(BasePermission):
    message = "Only administrators can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class IsAdminOrHR(BasePermission):
    message = "Only HR officers or administrators can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.can_manage_people)


class IsApprover(BasePermission):
    """Admin, HR or Manager - the people who may approve leave."""

    message = "Only managers, HR officers or administrators can approve leave."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.can_approve_leave)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
