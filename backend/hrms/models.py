"""HR domain: departments, employees, attendance, leave, holidays.

Relationships (this is the "SQL" part worth studying):

    Department 1 ──< Employee >── 1 User        (login account)
    Employee   1 ──< Attendance                 (one row per person per day)
    Employee   1 ──< LeaveRequest >── 1 LeaveType
    Employee   self-FK manager                  (reporting line)

Every constraint below is enforced by the database, not just by the UI.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(Timestamped):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=12, unique=True)
    description = models.TextField(blank=True)
    # Nullable FK to Employee: a department can exist before it has a head.
    head = models.ForeignKey(
        "hrms.Employee", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="headed_departments",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def headcount(self):
        return self.employees.filter(status=Employee.Status.ACTIVE).count()


class Employee(Timestamped):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full time"
        PART_TIME = "PART_TIME", "Part time"
        CONTRACT = "CONTRACT", "Contract"
        INTERN = "INTERN", "Intern"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_LEAVE = "ON_LEAVE", "On leave"
        RESIGNED = "RESIGNED", "Resigned"

    # Links the HR record to the login account. Null means "record only,
    # no portal access yet" - useful for staff who never log in.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employee",
    )
    employee_code = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=120, db_index=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(
        Department, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employees",
    )
    designation = models.CharField(max_length=80, blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    date_of_joining = models.DateField(default=timezone.localdate)
    manager = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reports",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department", "status"]),
        ]

    def __str__(self):
        return f"{self.employee_code} - {self.full_name}"

    def clean(self):
        if self.manager_id and self.pk and self.manager_id == self.pk:
            raise ValidationError({"manager": "An employee cannot report to themselves."})


class Attendance(Timestamped):
    """One row per employee per calendar day; enforced by a unique constraint."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        HALF_DAY = "HALF_DAY", "Half day"
        LEAVE = "LEAVE", "On leave"
        WFH = "WFH", "Work from home"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PRESENT)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    worked_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="marked_attendance",
    )

    class Meta:
        ordering = ["-date", "employee__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="unique_attendance_per_employee_per_day"
            )
        ]
        indexes = [models.Index(fields=["date", "status"])]

    def __str__(self):
        return f"{self.employee.full_name} @ {self.date} ({self.status})"

    def clean(self):
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError({"check_out": "Check-out cannot be earlier than check-in."})

    def save(self, *args, **kwargs):
        if self.check_in and self.check_out:
            start = self.check_in.hour * 60 + self.check_in.minute
            end = self.check_out.hour * 60 + self.check_out.minute
            self.worked_minutes = max(end - start, 0)
        super().save(*args, **kwargs)

    @property
    def is_late(self):
        if not self.check_in:
            return False
        late_after = getattr(settings, "LATE_AFTER", "09:30")
        hh, mm = (int(x) for x in late_after.split(":"))
        return (self.check_in.hour, self.check_in.minute) > (hh, mm)


class LeaveType(Timestamped):
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=12, unique=True)
    annual_quota = models.PositiveIntegerField(
        default=12, help_text="Days per calendar year. 0 means unlimited."
    )
    requires_approval = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveRequest(Timestamped):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="requests"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decided_leaves",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["employee", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.full_name}: {self.start_date}..{self.end_date}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    # -- derived values -----------------------------------------------------
    @staticmethod
    def count_days(start, end):
        """Inclusive day count, weekends excluded."""
        if not start or not end or end < start:
            return 0
        days = 0
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:  # Mon-Fri
                days += 1
            cursor += timedelta(days=1)
        return days

    def overlaps(self):
        """Other non-cancelled requests for the same employee that clash."""
        if not (self.employee_id and self.start_date and self.end_date):
            return LeaveRequest.objects.none()
        qs = LeaveRequest.objects.filter(
            employee_id=self.employee_id,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
        ).exclude(status=self.Status.CANCELLED)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs


class Holiday(Timestamped):
    name = models.CharField(max_length=100)
    date = models.DateField(unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.name} ({self.date})"

    @classmethod
    def between(cls, start, end):
        return cls.objects.filter(date__range=(start, end))
