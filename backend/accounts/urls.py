from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityFeedView,
    AnnouncementViewSet,
    ChangePasswordView,
    LogoutView,
    MeView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("activity/", ActivityFeedView.as_view(), name="activity"),
    path("", include(router.urls)),
]
