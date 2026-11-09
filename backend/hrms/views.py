import csv
import io
from datetime import date

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Announcement, AuditLog
from accounts.permissions import IsAdminOrHR, IsApprover

from . import services
from .models import Attendance, Department, Employee, Holiday, LeaveRequest, LeaveType
from .scoping import (
    can_approve_for,
    manageable_employees,
    my_employee,
    visible_attendance,
    visible_employees,
    visible_leave_requests,
)
from .serializers import (
    AttendanceSerializer,
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeWriteSerializer,
    HolidaySerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
)


def _parse_month(value, default_today=True):
    """'2026-10' -> (start_date, end_date)."""
    if not value:
        today = timezone.localdate()
        year, month = today.year, today.month
    else:
        try:
            year, month = (int(p) for p in value.split("-")[:2])
        except (ValueError, TypeError):
            raise ValidationError({"month": "Use the format YYYY-MM."})
    return services.month_bounds(year, month)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("head").prefetch_related("employees")
    serializer_class = DepartmentSerializer
    search_fields = ["name", "code"]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAdminOrHR()]

    def perform_create(self, serializer):
        dept = serializer.save()
        AuditLog.record(self.request.user, AuditLog.Action.CREATE, "department",
                        f"Created department {dept.name}", dept.pk)

    def perform_update(self, serializer):
        dept = serializer.save()
        AuditLog.record(self.request.user, AuditLog.Action.UPDATE, "department",
                        f"Updated department {dept.name}", dept.pk)

    def perform_destroy(self, instance):
        AuditLog.record(self.request.user, AuditLog.Action.DELETE, "department",
                        f"Deleted department {instance.name}", instance.pk)
        instance.delete()


class EmployeeViewSet(viewsets.ModelViewSet):
    """Employee records. Read scope depends on role; writes are Admin/HR only."""

    queryset = Employee.objects.select_related("department", "manager", "user")
    search_fields = ["full_name", "email", "employee_code", "designation"]
    ordering_fields = ["full_name", "date_of_joining", "employee_code"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return EmployeeWriteSerializer
        return EmployeeSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminOrHR()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = visible_employees(self.request.user).select_related(
            "department", "manager", "user"
        )
        params = self.request.query_params

        if search := params.get("search"):
            qs = qs.filter(
                Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(employee_code__icontains=search)
                | Q(designation__icontains=search)
            )
        if dept := params.get("department"):
            qs = qs.filter(department_id=dept)
        if emp_status := params.get("status"):
            qs = qs.filter(status=emp_status)
        if params.get("without_account") == "true":
            qs = qs.filter(user__isnull=True)
        return qs.order_by("full_name")

    def perform_destroy(self, instance):
        actor = self.request.user
        AuditLog.record(actor, AuditLog.Action.DELETE, "employee",
                        f"Deleted employee {instance.full_name} ({instance.employee_code})",
                        instance.pk)
        if instance.user and instance.user.pk == actor.pk:
            raise ValidationError({"detail": "You cannot delete your own employee record."})
        instance.delete()

    @action(detail=False, methods=["get"])
    def me(self, request):
        """The caller's own employee record (404 if they have none)."""
        emp = my_employee(request.user)
        if not emp:
            return Response({"detail": "No employee profile is linked to your account."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeSerializer(emp).data)

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        """Flat list for dropdowns - only the fields a selector needs."""
        rows = visible_employees(request.user).filter(status=Employee.Status.ACTIVE)
        return Response(
            [
                {
                    "id": e.id,
                    "employee_code": e.employee_code,
                    "full_name": e.full_name,
                    "department": e.department.name if e.department else None,
                }
                for e in rows.order_by("full_name")
            ]
        )

    @action(detail=True, methods=["get"])
    def attendance(self, request, pk=None):
        employee = self.get_object()
        start, end = _parse_month(request.query_params.get("month"))
        rows = Attendance.objects.filter(employee=employee, date__range=(start, end))
        return Response(
            {
                "employee": EmployeeSerializer(employee).data,
                "month": f"{start:%Y-%m}",
                "records": AttendanceSerializer(rows, many=True).data,
            }
        )

    @action(detail=True, methods=["get"])
    def leave_balance(self, request, pk=None):
        employee = self.get_object()
        return Response(services.leave_balance(employee))


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.select_related("employee", "employee__department", "marked_by")
    serializer_class = AttendanceSerializer

    def get_permissions(self):
        # Everyone may read their own scope and use check-in/out; only Admin/HR
        # may create/edit/delete arbitrary attendance rows.
        if self.action in ("create", "update", "partial_update", "destroy", "mark"):
            return [IsAdminOrHR()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = visible_attendance(self.request.user).select_related(
            "employee", "employee__department", "marked_by"
        )
        params = self.request.query_params

        if params.get("mine") == "true":
            # "My records" must mean *only mine*, even for an admin: the role
            # scope widens what you may see, not what this tab shows.
            me = my_employee(self.request.user)
            qs = qs.filter(employee=me) if me else qs.none()

        if d := params.get("date"):
            qs = qs.filter(date=d)
        if month := params.get("month"):
            start, end = _parse_month(month)
            qs = qs.filter(date__range=(start, end))
        if emp := params.get("employee"):
            qs = qs.filter(employee_id=emp)
        if dept := params.get("department"):
            qs = qs.filter(employee__department_id=dept)
        if att_status := params.get("status"):
            qs = qs.filter(status=att_status)
        return qs.order_by("-date", "employee__full_name")

    def perform_create(self, serializer):
        row = serializer.save(marked_by=self.request.user)
        AuditLog.record(self.request.user, AuditLog.Action.CREATE, "attendance",
                        f"Marked {row.employee.full_name} as {row.get_status_display()} "
                        f"on {row.date:%d %b %Y}", row.pk)

    def perform_update(self, serializer):
        row = serializer.save(marked_by=self.request.user)
        AuditLog.record(self.request.user, AuditLog.Action.UPDATE, "attendance",
                        f"Updated {row.employee.full_name} on {row.date:%d %b %Y}", row.pk)

    # -- self service -------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="check-in")
    def check_in(self, request):
        emp = my_employee(request.user)
        if not emp:
            raise ValidationError({"detail": "No employee profile is linked to your account."})
        row = services.check_in(emp, request.user)
        return Response(AttendanceSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="check-out")
    def check_out(self, request):
        emp = my_employee(request.user)
        if not emp:
            raise ValidationError({"detail": "No employee profile is linked to your account."})
        row = services.check_out(emp, request.user)
        return Response(AttendanceSerializer(row).data)

    @action(detail=False, methods=["get"])
    def today(self, request):
        emp = my_employee(request.user)
        if not emp:
            return Response({"record": None})
        row = Attendance.objects.filter(employee=emp, date=timezone.localdate()).first()
        return Response(
            {
                "record": AttendanceSerializer(row).data if row else None,
                "employee": {
                    "id": emp.id, "full_name": emp.full_name,
                    "employee_code": emp.employee_code,
                    "department": emp.department.name if emp.department else None,
                },
            }
        )

    @action(detail=False, methods=["post"])
    def mark(self, request):
        """Bulk mark: {"date": "...", "employee_ids": [..], "status": "PRESENT"}"""
        date_str = request.data.get("date") or str(timezone.localdate())
        ids = request.data.get("employee_ids") or []
        att_status = request.data.get("status")
        if not ids:
            raise ValidationError({"employee_ids": "Select at least one employee."})
        if att_status not in Attendance.Status.values:
            raise ValidationError({"status": f"Must be one of {Attendance.Status.values}."})

        allowed = manageable_employees(request.user).filter(pk__in=ids)
        rows = [services.mark_attendance(e, request.user, date_str, att_status) for e in allowed]
        return Response({"updated": len(rows)})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Per-employee totals for a month - drives the reports table."""
        start, end = _parse_month(request.query_params.get("month"))
        emps = visible_employees(request.user)
        if dept := request.query_params.get("department"):
            emps = emps.filter(department_id=dept)
        return Response(
            {
                "month": f"{start:%Y-%m}",
                "start": start,
                "end": end,
                "rows": services.attendance_summary(emps, start, end),
            }
        )


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAdminOrHR()]


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related(
        "employee", "employee__department", "leave_type", "decided_by"
    )
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        qs = visible_leave_requests(self.request.user).select_related(
            "employee", "employee__department", "leave_type", "decided_by"
        )
        params = self.request.query_params
        if leave_status := params.get("status"):
            qs = qs.filter(status=leave_status.upper())
        if emp := params.get("employee"):
            qs = qs.filter(employee_id=emp)
        if lt := params.get("leave_type"):
            qs = qs.filter(leave_type_id=lt)
        if params.get("mine") == "true":
            me = my_employee(self.request.user)
            qs = qs.filter(employee=me) if me else qs.none()
        if params.get("pending_my_approval") == "true":
            qs = qs.filter(status=LeaveRequest.Status.PENDING)
            approvable = [r.pk for r in qs if can_approve_for(self.request.user, r)]
            return LeaveRequest.objects.filter(pk__in=approvable).select_related(
                "employee", "employee__department", "leave_type", "decided_by"
            ).order_by("-created_at")
        return qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """Anyone may request leave - but only for themselves."""
        emp = my_employee(request.user)
        if not emp:
            raise ValidationError({"detail": "No employee profile is linked to your account."})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        req = services.apply_leave(
            employee=emp,
            actor=request.user,
            leave_type=serializer.validated_data["leave_type"],
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(
            LeaveRequestSerializer(req, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        req = self.get_object()
        if not can_approve_for(request.user, req):
            raise PermissionDenied("You cannot approve this request.")
        req = services.decide_leave(req, request.user, approve=True,
                                    note=request.data.get("note", ""))
        return Response(LeaveRequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = self.get_object()
        if not can_approve_for(request.user, req):
            raise PermissionDenied("You cannot reject this request.")
        req = services.decide_leave(req, request.user, approve=False,
                                    note=request.data.get("note", ""))
        return Response(LeaveRequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = self.get_object()
        me = my_employee(request.user)
        if not me or req.employee_id != me.pk:
            raise PermissionDenied("You can only cancel your own leave requests.")
        req = services.cancel_leave(req, request.user)
        return Response(LeaveRequestSerializer(req, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def balance(self, request):
        emp = my_employee(request.user)
        if target := request.query_params.get("employee"):
            if not request.user.can_manage_people:
                raise PermissionDenied("Only HR or administrators can view another person's balance.")
            emp = Employee.objects.filter(pk=target).first()
        if not emp:
            return Response([])
        return Response(services.leave_balance(emp))


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAdminOrHR()]


class DashboardView(APIView):
    """One call that powers the home screen, scoped to the caller's role."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()
        month_start, month_end = services.month_bounds(today.year, today.month)
        people = visible_employees(user)
        payload = {
            "today": today,
            "month": f"{today:%Y-%m}",
            "scope": "org" if user.can_manage_people else ("team" if user.is_manager_role else "self"),
            "role": user.role,
            "role_label": user.get_role_display(),
            "can_manage_people": user.can_manage_people,
            "can_approve_leave": user.can_approve_leave,
        }

        # --- organisation-wide cards (Admin / HR) --------------------------
        if user.can_manage_people:
            todays = Attendance.objects.filter(date=today, employee__in=people)
            payload["org"] = {
                "total_employees": people.count(),
                "active_employees": people.filter(status=Employee.Status.ACTIVE).count(),
                "departments": Department.objects.count(),
                "present_today": todays.filter(
                    status__in=[Attendance.Status.PRESENT, Attendance.Status.WFH]
                ).count(),
                "absent_today": todays.filter(status=Attendance.Status.ABSENT).count(),
                "on_leave_today": todays.filter(status=Attendance.Status.LEAVE).count(),
                "not_marked_today": max(
                    people.filter(status=Employee.Status.ACTIVE).count() - todays.count(), 0
                ),
                "pending_leave_requests": LeaveRequest.objects.filter(
                    status=LeaveRequest.Status.PENDING
                ).count(),
                "new_this_month": people.filter(date_of_joining__range=(month_start, month_end)).count(),
            }
            payload["department_breakdown"] = list(
                Department.objects.annotate(
                    headcount=Count("employees", filter=Q(employees__status=Employee.Status.ACTIVE))
                ).values("id", "name", "code", "headcount").order_by("-headcount")
            )

        # --- team cards (Manager) ------------------------------------------
        if user.is_manager_role or user.can_manage_people:
            team = people
            payload["team"] = {
                "team_size": team.count(),
                "present_today": Attendance.objects.filter(
                    date=today, employee__in=team,
                    status__in=[Attendance.Status.PRESENT, Attendance.Status.WFH],
                ).count(),
                "pending_requests": len(
                    [r for r in LeaveRequest.objects.filter(
                        status=LeaveRequest.Status.PENDING, employee__in=team)
                     if can_approve_for(user, r)]
                ),
            }

        # --- personal cards (everybody) ------------------------------------
        me = my_employee(user)
        if me:
            mine_today = Attendance.objects.filter(employee=me, date=today).first()
            my_month = Attendance.objects.filter(
                employee=me, date__range=(month_start, month_end)
            )
            payload["me"] = {
                "employee_id": me.id,
                "full_name": me.full_name,
                "employee_code": me.employee_code,
                "designation": me.designation,
                "department": me.department.name if me.department else None,
                "checked_in": bool(mine_today and mine_today.check_in),
                "checked_out": bool(mine_today and mine_today.check_out),
                "today_status": mine_today.get_status_display() if mine_today else "Not marked",
                "check_in": mine_today.check_in.strftime("%H:%M") if mine_today and mine_today.check_in else None,
                "check_out": mine_today.check_out.strftime("%H:%M") if mine_today and mine_today.check_out else None,
                "present_this_month": my_month.filter(
                    status__in=[Attendance.Status.PRESENT, Attendance.Status.WFH]
                ).count(),
                "working_days_this_month": services.LeaveRequest.count_days(month_start, month_end),
                "leave_balance": services.leave_balance(me),
                "pending_my_requests": LeaveRequest.objects.filter(
                    employee=me, status=LeaveRequest.Status.PENDING
                ).count(),
            }

        payload["announcements"] = [
            {
                "id": a.id, "title": a.title, "body": a.body, "is_pinned": a.is_pinned,
                "author_name": a.author.full_name if a.author else "System",
                "created_at": a.created_at,
            }
            for a in Announcement.objects.select_related("author")[:3]
        ]
        payload["recent_activity"] = [
            {
                "id": log.id,
                "actor_name": log.actor.full_name if log.actor else "System",
                "action": log.action,
                "action_label": log.get_action_display(),
                "summary": log.summary,
                "created_at": log.created_at,
            }
            for log in AuditLog.objects.select_related("actor")[:8]
        ]
        payload["upcoming_holidays"] = [
            {"id": h.id, "name": h.name, "date": h.date}
            for h in Holiday.objects.filter(date__gte=today)[:3]
        ]
        return Response(payload)


class AttendanceReportCSV(APIView):
    """GET /api/reports/attendance.csv?month=YYYY-MM - Excel-friendly export."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.can_manage_people or user.is_manager_role):
            raise PermissionDenied("Reports are available to managers, HR and administrators.")

        start, end = _parse_month(request.query_params.get("month"))
        emps = visible_employees(user)
        rows = services.attendance_summary(emps, start, end)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="attendance-{start:%Y-%m}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            ["Employee code", "Employee", "Present", "WFH", "Leave", "Absent",
             "Recorded days", "Attendance %"]
        )
        for r in rows:
            writer.writerow(
                [r["employee_code"], r["employee_name"], r["present"], r["wfh"],
                 r["leave"], r["absent"], r["total"], r["attendance_rate"]]
            )
        return response
