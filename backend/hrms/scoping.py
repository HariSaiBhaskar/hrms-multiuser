"""Who is allowed to see which rows.

Filtering happens in the **queryset**, before serialization. A hidden UI button
is not security - if a user crafts the request by hand they still get 403/404
because the row is simply not in their queryset.
"""

from django.db.models import Q

from .models import Attendance, Employee, LeaveRequest


def my_employee(user):
    """The Employee row attached to this login, or None.

    Read fresh from the database rather than using ``user.employee``: the
    reverse one-to-one is cached on the User instance, so a cached object can
    go stale (e.g. right after an HR edit). One indexed lookup on a unique
    foreign key is cheap; serving stale data is not.
    """
    if not user or not user.is_authenticated:
        return None
    return (
        Employee.objects.select_related("department")
        .filter(user_id=user.pk)
        .first()
    )


def visible_employees(user):
    """Every Employee row the given user may read."""
    if not user or not user.is_authenticated:
        return Employee.objects.none()

    if user.can_manage_people:            # ADMIN / HR
        return Employee.objects.all()

    me = my_employee(user)
    if me is None:
        return Employee.objects.none()

    if user.is_manager_role:
        # Manager: their own record plus everyone in the same department and
        # anyone who reports to them directly.
        dept_id = me.department_id
        return Employee.objects.filter(
            Q(pk=me.pk) | Q(manager=me) | Q(department_id=dept_id, department__isnull=False)
        ).distinct()

    return Employee.objects.filter(pk=me.pk)


def manageable_employees(user):
    """Rows the user may *write* (mark attendance for, edit)."""
    if user.can_manage_people:
        return Employee.objects.all()
    me = my_employee(user)
    if me and user.is_manager_role:
        return Employee.objects.filter(Q(pk=me.pk) | Q(manager=me)).distinct()
    return Employee.objects.filter(pk=me.pk) if me else Employee.objects.none()


def visible_attendance(user):
    return Attendance.objects.filter(employee__in=visible_employees(user))


def visible_leave_requests(user):
    return LeaveRequest.objects.filter(employee__in=visible_employees(user))


def can_approve_for(user, leave_request):
    """A manager may not approve their own leave; HR/admin may approve anyone else's."""
    if not user.can_approve_leave:
        return False
    me = my_employee(user)
    if me and leave_request.employee_id == me.pk:
        return False
    if user.can_manage_people:
        return True
    if user.is_manager_role and me:
        emp = leave_request.employee
        return emp.manager_id == me.pk or emp.department_id == me.department_id
    return False
