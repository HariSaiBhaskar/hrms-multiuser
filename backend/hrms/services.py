"""Business rules that don't belong in a view or a serializer.

Keeping them here means the API, the admin site and the seed command all
behave identically.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import AuditLog

from .models import Attendance, Employee, Holiday, LeaveRequest, LeaveType


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
def _now_time():
    return timezone.localtime().time().replace(second=0, microsecond=0)


@transaction.atomic
def check_in(employee, actor, when=None):
    """Create today's attendance row with a check-in timestamp.

    Idempotent-ish: a second check-in on the same day is rejected rather than
    silently overwriting the first timestamp.
    """
    today = timezone.localdate()
    row = Attendance.objects.select_for_update().filter(employee=employee, date=today).first()

    if row and row.check_in:
        raise ValidationError({"detail": f"You already checked in at {row.check_in:%H:%M} today."})

    stamp = when or _now_time()
    if row is None:
        row = Attendance(employee=employee, date=today)
    row.check_in = stamp
    row.status = Attendance.Status.PRESENT
    row.marked_by = actor
    row.save()

    AuditLog.record(actor, AuditLog.Action.CHECK_IN, "attendance",
                    f"{employee.full_name} checked in at {stamp:%H:%M}", row.pk)
    return row


@transaction.atomic
def check_out(employee, actor, when=None):
    today = timezone.localdate()
    row = Attendance.objects.select_for_update().filter(employee=employee, date=today).first()

    if row is None or not row.check_in:
        raise ValidationError({"detail": "You have not checked in today."})
    if row.check_out:
        raise ValidationError({"detail": f"You already checked out at {row.check_out:%H:%M}."})

    stamp = when or _now_time()
    if stamp < row.check_in:
        raise ValidationError({"detail": "Check-out time cannot be before check-in."})
    row.check_out = stamp
    row.save()

    AuditLog.record(actor, AuditLog.Action.CHECK_OUT, "attendance",
                    f"{employee.full_name} checked out at {stamp:%H:%M}", row.pk)
    return row


def mark_attendance(employee, actor, date, status, check_in=None, check_out=None, notes=""):
    """Used by HR/manager to correct or backfill a day.

    ``date`` may arrive as a string from JSON, so normalise it to a date first.
    """
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"date": "Use the format YYYY-MM-DD."})

    row, created = Attendance.objects.update_or_create(
        employee=employee,
        date=date,
        defaults={
            "status": status,
            "check_in": check_in,
            "check_out": check_out,
            "notes": notes,
            "marked_by": actor,
        },
    )
    AuditLog.record(
        actor, AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE,
        "attendance",
        f"{'Marked' if created else 'Updated'} {employee.full_name} as "
        f"{Attendance.Status(status).label} on {date:%d %b %Y}",
        row.pk,
    )
    return row


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------
def leave_usage(employee, year=None):
    """Approved + pending day counts per leave type for one calendar year."""
    year = year or timezone.localdate().year
    usage = {}
    rows = LeaveRequest.objects.filter(
        employee=employee,
        start_date__year=year,
    ).exclude(status=LeaveRequest.Status.CANCELLED)
    for req in rows:
        bucket = usage.setdefault(
            req.leave_type_id, {"approved": 0, "pending": 0, "rejected": 0}
        )
        key = {"APPROVED": "approved", "PENDING": "pending", "REJECTED": "rejected"}[req.status]
        bucket[key] += req.days
    return usage


def leave_balance(employee, year=None):
    """Per-type quota/used/remaining for the UI's balance cards."""
    year = year or timezone.localdate().year
    usage = leave_usage(employee, year)
    result = []
    for lt in LeaveType.objects.all():
        used = usage.get(lt.id, {})
        approved = used.get("approved", 0)
        pending = used.get("pending", 0)
        unlimited = lt.annual_quota == 0
        result.append(
            {
                "leave_type": lt.id,
                "name": lt.name,
                "code": lt.code,
                "quota": lt.annual_quota,
                "unlimited": unlimited,
                "used": approved,
                "pending": pending,
                "remaining": None if unlimited else max(lt.annual_quota - approved - pending, 0),
            }
        )
    return result


@transaction.atomic
def apply_leave(employee, actor, leave_type, start_date, end_date, reason):
    """Validate and store a leave request. All rules live here."""
    if end_date < start_date:
        raise ValidationError({"end_date": "End date cannot be before the start date."})

    days = LeaveRequest.count_days(start_date, end_date)
    if days == 0:
        raise ValidationError(
            {"start_date": "That range contains no working days (weekends only)."}
        )

    candidate = LeaveRequest(
        employee=employee, leave_type=leave_type,
        start_date=start_date, end_date=end_date,
    )
    if candidate.overlaps().exists():
        raise ValidationError(
            {"detail": "You already have a leave request overlapping those dates."}
        )

    # Balance check: approval is not required to *ask*, but an obviously
    # over-quota request is blocked up front.
    if leave_type.annual_quota:
        used = leave_usage(employee, start_date.year).get(leave_type.id, {})
        already = used.get("approved", 0) + used.get("pending", 0)
        if already + days > leave_type.annual_quota:
            raise ValidationError(
                {"days": f"Insufficient {leave_type.name} balance: "
                         f"{leave_type.annual_quota - already} day(s) left, {days} requested."}
            )

    req = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=reason,
        status=LeaveRequest.Status.PENDING,
    )
    AuditLog.record(actor, AuditLog.Action.CREATE, "leave_request",
                    f"{employee.full_name} requested {days} day(s) of {leave_type.name}",
                    req.pk)
    return req


@transaction.atomic
def decide_leave(leave_request, actor, approve: bool, note=""):
    """Approve or reject. Approving writes LEAVE rows into attendance."""
    if leave_request.status != LeaveRequest.Status.PENDING:
        raise ValidationError(
            {"detail": f"This request is already {leave_request.get_status_display().lower()}."}
        )

    leave_request.status = (
        LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    )
    leave_request.decided_by = actor
    leave_request.decided_at = timezone.now()
    leave_request.decision_note = note or ""
    leave_request.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"])

    if approve:
        _sync_attendance_for_leave(leave_request, actor)

    AuditLog.record(
        actor,
        AuditLog.Action.APPROVE if approve else AuditLog.Action.REJECT,
        "leave_request",
        f"{'Approved' if approve else 'Rejected'} {leave_request.employee.full_name}'s "
        f"{leave_request.leave_type.name} "
        f"({leave_request.start_date:%d %b} - {leave_request.end_date:%d %b})",
        leave_request.pk,
    )
    return leave_request


def _sync_attendance_for_leave(leave_request, actor):
    """Mark weekdays in the approved range as LEAVE, skipping holidays."""
    holidays = set(
        Holiday.between(leave_request.start_date, leave_request.end_date)
        .values_list("date", flat=True)
    )
    cursor = leave_request.start_date
    while cursor <= leave_request.end_date:
        if cursor.weekday() < 5 and cursor not in holidays:
            Attendance.objects.update_or_create(
                employee=leave_request.employee,
                date=cursor,
                defaults={
                    "status": Attendance.Status.LEAVE,
                    "check_in": None,
                    "check_out": None,
                    "notes": f"{leave_request.leave_type.name} (approved)",
                    "marked_by": actor,
                },
            )
        cursor += timedelta(days=1)


@transaction.atomic
def cancel_leave(leave_request, actor):
    if leave_request.status not in (
        LeaveRequest.Status.PENDING,
        LeaveRequest.Status.APPROVED,
    ):
        raise ValidationError({"detail": "Only pending or approved requests can be cancelled."})

    was_approved = leave_request.status == LeaveRequest.Status.APPROVED
    leave_request.status = LeaveRequest.Status.CANCELLED
    leave_request.save(update_fields=["status", "updated_at"])

    if was_approved:
        Attendance.objects.filter(
            employee=leave_request.employee,
            date__range=(leave_request.start_date, leave_request.end_date),
            status=Attendance.Status.LEAVE,
        ).delete()

    AuditLog.record(actor, AuditLog.Action.UPDATE, "leave_request",
                    f"Cancelled {leave_request.employee.full_name}'s "
                    f"{leave_request.leave_type.name}", leave_request.pk)
    return leave_request


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
def month_bounds(year, month):
    start = datetime(year, month, 1).date()
    end = (datetime(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)).date()
    return start, end


def attendance_summary(employees, start, end):
    """Per-employee present/absent/leave counts between two dates."""
    from django.db.models import Count, Q

    rows = (
        Attendance.objects.filter(employee__in=employees, date__range=(start, end))
        .values("employee_id", "employee__full_name", "employee__employee_code")
        .annotate(
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
            wfh=Count("id", filter=Q(status=Attendance.Status.WFH)),
            total=Count("id"),
        )
        .order_by("employee__full_name")
    )
    out = []
    for r in rows:
        total = r["total"] or 1
        out.append(
            {
                "employee_id": r["employee_id"],
                "employee_name": r["employee__full_name"],
                "employee_code": r["employee__employee_code"],
                "present": r["present"],
                "absent": r["absent"],
                "leave": r["leave"],
                "wfh": r["wfh"],
                "total": r["total"],
                "attendance_rate": round(
                    (r["present"] + r["wfh"]) / total * 100, 1
                ),
            }
        )
    return out
