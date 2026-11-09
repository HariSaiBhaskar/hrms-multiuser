import secrets
import string

from django.utils import timezone
from rest_framework import serializers

from accounts.models import AuditLog, Role, User

from .models import Attendance, Department, Employee, Holiday, LeaveRequest, LeaveType


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source="head.full_name", read_only=True, default=None)
    headcount = serializers.IntegerField(read_only=True)
    employee_total = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "head", "head_name",
                  "headcount", "employee_total", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_employee_total(self, obj):
        return obj.employees.count()


class EmployeeSerializer(serializers.ModelSerializer):
    """Read serializer. Department/manager are flattened for the table view."""

    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    department_code = serializers.CharField(source="department.code", read_only=True, default=None)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    employment_type_label = serializers.CharField(source="get_employment_type_display", read_only=True)
    has_account = serializers.SerializerMethodField()
    account_role = serializers.CharField(source="user.role", read_only=True, default=None)

    class Meta:
        model = Employee
        fields = [
            "id", "employee_code", "full_name", "email", "phone",
            "department", "department_name", "department_code",
            "designation", "employment_type", "employment_type_label",
            "status", "status_label", "date_of_joining",
            "manager", "manager_name", "user", "has_account", "account_role",
            "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_has_account(self, obj):
        return obj.user_id is not None


class EmployeeWriteSerializer(serializers.ModelSerializer):
    """Create/update an employee record, optionally with a login account.

    If ``create_account`` is true and the employee has no user yet, a User row
    is created in the same transaction and the generated temporary password is
    returned exactly once, in the response to this request.
    """

    create_account = serializers.BooleanField(write_only=True, required=False, default=False)
    account_role = serializers.ChoiceField(
        write_only=True, required=False, default=Role.EMPLOYEE, choices=Role.choices
    )
    temporary_password = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)
    has_account = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "employee_code", "full_name", "email", "phone", "department",
            "designation", "employment_type", "status", "date_of_joining", "manager",
            "notes", "create_account", "account_role", "temporary_password",
            "status_label", "department_name", "manager_name", "has_account",
            "user", "created_at",
        ]
        read_only_fields = ["id", "user", "created_at", "temporary_password"]

    def get_has_account(self, obj):
        return obj.user_id is not None

    def validate_employee_code(self, value):
        return value.strip().upper()

    def validate_email(self, value):
        return value.lower().strip()

    def validate_manager(self, value):
        if value and self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError("An employee cannot report to themselves.")
        return value

    @staticmethod
    def _temp_password():
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(10))

    def create(self, validated_data):
        create_account = validated_data.pop("create_account", False)
        account_role = validated_data.pop("account_role", Role.EMPLOYEE)
        actor = self.context["request"].user

        temp_password = None
        if create_account:
            if not validated_data.get("email"):
                raise serializers.ValidationError(
                    {"email": "An email address is required to create a login account."}
                )
            if User.objects.filter(email=validated_data["email"]).exists():
                raise serializers.ValidationError(
                    {"email": "A login account with this email already exists."}
                )
            if account_role in (Role.ADMIN, Role.HR) and not actor.is_admin_role:
                raise serializers.ValidationError(
                    {"account_role": "Only an administrator can create HR or admin accounts."}
                )
            temp_password = self._temp_password()
            user = User.objects.create_user(
                email=validated_data["email"],
                password=temp_password,
                full_name=validated_data.get("full_name", ""),
                role=account_role,
                job_title=validated_data.get("designation", ""),
                phone=validated_data.get("phone", ""),
                must_change_password=True,
            )
            validated_data["user"] = user

        employee = super().create(validated_data)
        if temp_password:
            employee.temporary_password = temp_password

        AuditLog.record(
            actor, AuditLog.Action.CREATE, "employee",
            f"Added employee {employee.full_name} ({employee.employee_code})"
            + (f" with a {account_role} login" if temp_password else ""),
            employee.pk,
        )
        return employee

    def update(self, instance, validated_data):
        validated_data.pop("create_account", None)
        validated_data.pop("account_role", None)
        employee = super().update(instance, validated_data)
        AuditLog.record(self.context["request"].user, AuditLog.Action.UPDATE, "employee",
                        f"Updated employee {employee.full_name} ({employee.employee_code})",
                        employee.pk)
        return employee


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    department = serializers.CharField(source="employee.department.name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    marked_by_name = serializers.CharField(source="marked_by.full_name", read_only=True, default=None)

    class Meta:
        model = Attendance
        fields = ["id", "employee", "employee_name", "employee_code", "department",
                  "date", "status", "status_label", "check_in", "check_out",
                  "worked_minutes", "is_late", "notes", "marked_by", "marked_by_name",
                  "created_at"]
        read_only_fields = ["id", "marked_by", "worked_minutes", "created_at"]

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Attendance cannot be marked for a future date.")
        return value

    def validate(self, attrs):
        check_in = attrs.get("check_in", getattr(self.instance, "check_in", None))
        check_out = attrs.get("check_out", getattr(self.instance, "check_out", None))
        if check_in and check_out and check_out < check_in:
            raise serializers.ValidationError({"check_out": "Check-out must be after check-in."})
        return attrs


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "code", "annual_quota", "requires_approval", "is_paid"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    department = serializers.CharField(source="employee.department.name", read_only=True, default=None)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.full_name", read_only=True, default=None)
    can_decide = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = ["id", "employee", "employee_name", "employee_code", "department",
                  "leave_type", "leave_type_name", "start_date", "end_date", "days",
                  "reason", "status", "status_label", "decided_by", "decided_by_name",
                  "decided_at", "decision_note", "can_decide", "can_cancel",
                  "created_at"]
        read_only_fields = ["id", "employee", "days", "status", "decided_by",
                            "decided_at", "decision_note", "created_at"]

    def get_can_decide(self, obj):
        from .scoping import can_approve_for

        user = self.context.get("request").user if self.context.get("request") else None
        return bool(user and obj.status == LeaveRequest.Status.PENDING and can_approve_for(user, obj))

    def get_can_cancel(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        user = request.user
        mine = getattr(user, "employee", None)
        if not mine or obj.employee_id != mine.pk:
            return False
        return obj.status in (LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED)


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "name", "date", "description"]
