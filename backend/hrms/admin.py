from django.contrib import admin

from .models import Attendance, Department, Employee, Holiday, LeaveRequest, LeaveType


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "head", "headcount"]
    search_fields = ["name", "code"]
    autocomplete_fields = ["head"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["employee_code", "full_name", "department", "designation",
                    "status", "user"]
    list_filter = ["status", "department", "employment_type"]
    search_fields = ["employee_code", "full_name", "email"]
    autocomplete_fields = ["manager"]
    raw_id_fields = ["user"]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["date", "employee", "status", "check_in", "check_out",
                    "worked_minutes"]
    list_filter = ["status", "date"]
    search_fields = ["employee__full_name", "employee__employee_code"]
    date_hierarchy = "date"


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "annual_quota", "requires_approval", "is_paid"]


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "leave_type", "start_date", "end_date", "days",
                    "status", "decided_by"]
    list_filter = ["status", "leave_type"]
    search_fields = ["employee__full_name"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ["date", "name"]
    search_fields = ["name"]
