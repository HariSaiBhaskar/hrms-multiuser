from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse

from accounts.views import LoginView, RefreshView
from hrms.views import DashboardView, AttendanceReportCSV


def health(request):
    """Unauthenticated liveness probe - useful when wiring up the frontend."""
    from django.db import connection

    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:  # pragma: no cover
        db_ok = False
    return JsonResponse(
        {
            "status": "ok",
            "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
            "database_connected": db_ok,
        }
    )


urlpatterns = [
    path("", health),
    path("admin/", admin.site.urls),

    # --- auth (JWT) ---
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/refresh/", RefreshView.as_view(), name="auth-refresh"),

    # --- app ---
    path("api/", include("accounts.urls")),
    path("api/", include("hrms.urls")),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/reports/attendance.csv", AttendanceReportCSV.as_view(), name="attendance-csv"),
]
