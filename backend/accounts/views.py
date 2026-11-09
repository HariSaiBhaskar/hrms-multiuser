from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Announcement, AuditLog, User
from .permissions import IsAdmin, IsAdminOrHR
from .serializers import (
    AnnouncementSerializer,
    AuditLogSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    UserSerializer,
    UserWriteSerializer,
)


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/  {email, password} -> {access, refresh, user}"""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            email = (request.data.get("email") or "").lower()
            user = User.objects.filter(email=email).first()
            if user:
                user.last_seen_at = timezone.now()
                user.save(update_fields=["last_seen_at"])
                AuditLog.record(user, AuditLog.Action.LOGIN, "session",
                                f"{user.full_name} signed in")
        return response


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ {refresh} -> {access, refresh}"""

    permission_classes = [AllowAny]


class LogoutView(APIView):
    """Audit-only logout. JWTs are stateless, so the client drops its tokens."""

    def post(self, request):
        AuditLog.record(request.user, AuditLog.Action.LOGOUT, "session",
                        f"{request.user.full_name} signed out")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ - the logged-in user's own profile."""

    serializer_class = MeSerializer

    def get_object(self):
        user = self.request.user
        user.last_seen_at = timezone.now()
        user.save(update_fields=["last_seen_at"])
        return user


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditLog.record(request.user, AuditLog.Action.UPDATE, "user",
                        f"{request.user.full_name} changed their password", request.user.pk)
        return Response({"detail": "Password updated. Please sign in again."})


class UserViewSet(viewsets.ModelViewSet):
    """Admin-only user administration (create accounts, change roles, deactivate)."""

    queryset = User.objects.all().select_related("employee__department")
    permission_classes = [IsAdmin]
    search_fields = ["email", "full_name"]
    filterset_fields = ["role", "is_active"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(email__icontains=search) | Q(full_name__icontains=search))
        active = self.request.query_params.get("is_active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        return qs.order_by("full_name")

    def perform_create(self, serializer):
        user = serializer.save()
        AuditLog.record(self.request.user, AuditLog.Action.CREATE, "user",
                        f"Created account for {user.full_name} ({user.get_role_display()})",
                        user.pk)

    def perform_update(self, serializer):
        user = serializer.save()
        AuditLog.record(self.request.user, AuditLog.Action.UPDATE, "user",
                        f"Updated account {user.full_name} ({user.get_role_display()})", user.pk)

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "You cannot delete your own account."})
        AuditLog.record(self.request.user, AuditLog.Action.DELETE, "user",
                        f"Deleted account {instance.full_name}", instance.pk)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """Admin sets a temporary password; the user must change it next login."""
        from django.contrib.auth.password_validation import validate_password
        from rest_framework.exceptions import ValidationError

        user = self.get_object()
        password = request.data.get("password") or ""
        try:
            validate_password(password, user)
        except Exception as exc:
            raise ValidationError({"password": list(exc.messages)})
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        AuditLog.record(request.user, AuditLog.Action.UPDATE, "user",
                        f"Reset password for {user.full_name}", user.pk)
        return Response({"detail": f"Password reset for {user.full_name}."})


class AnnouncementViewSet(viewsets.ModelViewSet):
    """Everyone reads; only Admin/HR write. Shared across all users."""

    queryset = Announcement.objects.select_related("author")
    serializer_class = AnnouncementSerializer
    search_fields = ["title", "body"]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAdminOrHR()]

    def perform_create(self, serializer):
        ann = serializer.save(author=self.request.user)
        AuditLog.record(self.request.user, AuditLog.Action.CREATE, "announcement",
                        f"Posted announcement: {ann.title}", ann.pk)

    def perform_update(self, serializer):
        ann = serializer.save()
        AuditLog.record(self.request.user, AuditLog.Action.UPDATE, "announcement",
                        f"Edited announcement: {ann.title}", ann.pk)

    def perform_destroy(self, instance):
        AuditLog.record(self.request.user, AuditLog.Action.DELETE, "announcement",
                        f"Deleted announcement: {instance.title}", instance.pk)
        instance.delete()


class ActivityFeedView(ListAPIView):
    """GET /api/activity/ - shared audit trail, newest first.

    Visible to everyone: it is how a team sees each other's changes.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor")
        actor = self.request.query_params.get("actor")
        if actor:
            qs = qs.filter(actor_id=actor)
        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter.upper())
        limit = min(int(self.request.query_params.get("limit", 50)), 200)
        return qs[:limit]
