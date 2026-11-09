"""Tests for the multi-user rules.

These are the tests that matter for a *multi-user* app: not "does the endpoint
return 200", but "can Sneha (an employee) read Karthik's attendance or approve
her own leave?" Run with:

    python manage.py test
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Announcement, AuditLog, Role, User
from hrms.models import Attendance, Department, Employee, LeaveRequest, LeaveType
from hrms.services import leave_balance


class BaseFixture(APITestCase):
    """Two departments, four users, one employee each - the minimum needed to
    prove that people cannot see or edit each other's rows."""

    @classmethod
    def setUpTestData(cls):
        cls.eng = Department.objects.create(name="Engineering", code="ENG")
        cls.sales = Department.objects.create(name="Sales", code="SLS")

        cls.admin = User.objects.create_user(
            "admin@test.local", "Passw0rd!", full_name="Ada Admin", role=Role.ADMIN)
        cls.hr = User.objects.create_user(
            "hr@test.local", "Passw0rd!", full_name="Hana HR", role=Role.HR)
        cls.manager = User.objects.create_user(
            "manager@test.local", "Passw0rd!", full_name="Mo Manager", role=Role.MANAGER)
        cls.alice = User.objects.create_user(
            "alice@test.local", "Passw0rd!", full_name="Alice Employee", role=Role.EMPLOYEE)
        cls.bob = User.objects.create_user(
            "bob@test.local", "Passw0rd!", full_name="Bob Employee", role=Role.EMPLOYEE)

        cls.emp_manager = Employee.objects.create(
            user=cls.manager, employee_code="E001", full_name="Mo Manager",
            email="manager@test.local", department=cls.eng, designation="Manager")
        cls.emp_alice = Employee.objects.create(
            user=cls.alice, employee_code="E002", full_name="Alice Employee",
            email="alice@test.local", department=cls.eng, manager=cls.emp_manager)
        cls.emp_bob = Employee.objects.create(
            user=cls.bob, employee_code="E003", full_name="Bob Employee",
            email="bob@test.local", department=cls.sales)

        cls.casual = LeaveType.objects.create(name="Casual", code="CL", annual_quota=12)

    def auth(self, user):
        self.client.force_authenticate(user=user)
        return self.client


class AuthenticationTests(BaseFixture):
    def test_login_returns_tokens_and_profile(self):
        client = APIClient()
        res = client.post("/api/auth/login/",
                          {"email": "alice@test.local", "password": "Passw0rd!"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["email"], "alice@test.local")
        self.assertEqual(res.data["user"]["role"], Role.EMPLOYEE)
        self.assertNotIn("password", res.data["user"])

    def test_login_is_case_insensitive_on_email(self):
        res = APIClient().post("/api/auth/login/",
                               {"email": "ALICE@test.local", "password": "Passw0rd!"},
                               format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_wrong_password_rejected(self):
        res = APIClient().post("/api/auth/login/",
                               {"email": "alice@test.local", "password": "nope"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_cannot_read_anything(self):
        client = APIClient()
        for url in ["/api/employees/", "/api/attendance/", "/api/leave-requests/",
                    "/api/dashboard/", "/api/users/", "/api/activity/"]:
            self.assertEqual(client.get(url).status_code, status.HTTP_401_UNAUTHORIZED, url)

    def test_login_is_audited(self):
        APIClient().post("/api/auth/login/",
                         {"email": "alice@test.local", "password": "Passw0rd!"}, format="json")
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN).exists())


class EmployeeVisibilityTests(BaseFixture):
    def test_employee_sees_only_their_own_record(self):
        res = self.auth(self.alice).get("/api/employees/")
        self.assertEqual(res.status_code, 200)
        ids = [row["id"] for row in res.data["results"]]
        self.assertEqual(ids, [self.emp_alice.id])

    def test_manager_sees_their_department_only(self):
        res = self.auth(self.manager).get("/api/employees/")
        ids = {row["id"] for row in res.data["results"]}
        self.assertIn(self.emp_alice.id, ids)      # same department
        self.assertIn(self.emp_manager.id, ids)    # themselves
        self.assertNotIn(self.emp_bob.id, ids)     # different department

    def test_hr_sees_everyone(self):
        res = self.auth(self.hr).get("/api/employees/")
        self.assertEqual(res.data["count"], 3)

    def test_employee_cannot_open_a_colleagues_detail_page(self):
        res = self.auth(self.alice).get(f"/api/employees/{self.emp_bob.id}/")
        self.assertEqual(res.status_code, 404)

    def test_employee_cannot_create_or_delete_employees(self):
        client = self.auth(self.alice)
        res = client.post("/api/employees/", {
            "employee_code": "E999", "full_name": "Mallory", "email": "m@test.local",
        }, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(client.delete(f"/api/employees/{self.emp_bob.id}/").status_code, 403)

    def test_hr_can_create_employee_with_login_account(self):
        res = self.auth(self.hr).post("/api/employees/", {
            "employee_code": "e100", "full_name": "New Hire", "email": "new@test.local",
            "department": self.eng.id, "designation": "Analyst",
            "create_account": True, "account_role": "EMPLOYEE",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["has_account"])
        temp_password = res.data["temporary_password"]
        self.assertTrue(temp_password and len(temp_password) >= 8)
        # the new starter can actually log in with that password
        login = APIClient().post("/api/auth/login/",
                                 {"email": "new@test.local", "password": temp_password},
                                 format="json")
        self.assertEqual(login.status_code, 200)
        # login returns the same shape as GET /auth/me/
        self.assertEqual(login.data["user"]["employee"]["employee_code"], "E100")  # upper-cased
        self.assertTrue(login.data["user"]["must_change_password"])

    def test_hr_cannot_create_admin_login(self):
        res = self.auth(self.hr).post("/api/employees/", {
            "employee_code": "E200", "full_name": "Sneaky", "email": "sneaky@test.local",
            "create_account": True, "account_role": "ADMIN",
        }, format="json")
        self.assertEqual(res.status_code, 400)


class AttendanceTests(BaseFixture):
    def test_check_in_then_check_out(self):
        client = self.auth(self.alice)
        res = client.post("/api/attendance/check-in/")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNotNone(res.data["check_in"])

        again = client.post("/api/attendance/check-in/")
        self.assertEqual(again.status_code, 400)   # no double check-in

        out = client.post("/api/attendance/check-out/")
        self.assertEqual(out.status_code, 200)
        self.assertIsNotNone(out.data["check_out"])
        self.assertIsNotNone(out.data["worked_minutes"])

    def test_check_out_without_check_in_fails(self):
        res = self.auth(self.bob).post("/api/attendance/check-out/")
        self.assertEqual(res.status_code, 400)

    def test_employee_cannot_see_colleagues_attendance(self):
        Attendance.objects.create(employee=self.emp_bob, date=timezone.localdate(),
                                  status=Attendance.Status.PRESENT)
        res = self.auth(self.alice).get("/api/attendance/")
        self.assertEqual(res.data["count"], 0)

    def test_employee_cannot_mark_attendance_for_someone_else(self):
        res = self.auth(self.alice).post("/api/attendance/", {
            "employee": self.emp_bob.id, "date": str(timezone.localdate()),
            "status": "ABSENT",
        }, format="json")
        self.assertEqual(res.status_code, 403)

    def test_one_row_per_employee_per_day(self):
        today = timezone.localdate()
        Attendance.objects.create(employee=self.emp_alice, date=today,
                                  status=Attendance.Status.PRESENT)
        res = self.auth(self.hr).post("/api/attendance/", {
            "employee": self.emp_alice.id, "date": str(today), "status": "ABSENT",
        }, format="json")
        self.assertEqual(res.status_code, 400)  # unique constraint -> clean 400
        self.assertEqual(Attendance.objects.filter(employee=self.emp_alice).count(), 1)

    def test_hr_bulk_mark(self):
        res = self.auth(self.hr).post("/api/attendance/mark/", {
            "date": str(timezone.localdate()),
            "employee_ids": [self.emp_alice.id, self.emp_bob.id],
            "status": "PRESENT",
        }, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["updated"], 2)

    def test_summary_uses_aggregates(self):
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        for day_offset in range(3):
            Attendance.objects.create(
                employee=self.emp_alice, date=start_of_month + timedelta(days=day_offset),
                status=Attendance.Status.PRESENT)
        Attendance.objects.create(employee=self.emp_alice,
                                  date=start_of_month + timedelta(days=5),
                                  status=Attendance.Status.ABSENT)
        res = self.auth(self.hr).get(f"/api/attendance/summary/?month={today:%Y-%m}")
        self.assertEqual(res.status_code, 200)
        row = next(r for r in res.data["rows"] if r["employee_id"] == self.emp_alice.id)
        self.assertEqual(row["present"], 3)
        self.assertEqual(row["total"], 4)


class LeaveWorkflowTests(BaseFixture):
    def _apply(self, user, start_offset=7, days=2, leave_type=None):
        start = timezone.localdate() + timedelta(days=start_offset)
        while start.weekday() >= 5:      # requests must span working days
            start += timedelta(days=1)
        end = start + timedelta(days=days - 1)
        return self.auth(user).post("/api/leave-requests/", {
            "leave_type": (leave_type or self.casual).id,
            "start_date": str(start), "end_date": str(end),
            "reason": "Testing",
        }, format="json")

    def test_apply_leave(self):
        res = self._apply(self.alice)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["status"], "PENDING")
        self.assertGreaterEqual(res.data["days"], 1)

    def test_overlapping_request_rejected(self):
        self._apply(self.alice, start_offset=10, days=3)
        res = self._apply(self.alice, start_offset=11, days=2)
        self.assertEqual(res.status_code, 400)
        self.assertIn("overlapping", str(res.data).lower())

    def test_cannot_request_more_than_balance(self):
        big = LeaveType.objects.create(name="Study", code="ST", annual_quota=2)
        res = self._apply(self.alice, start_offset=20, days=5, leave_type=big)
        self.assertEqual(res.status_code, 400)
        self.assertIn("balance", str(res.data).lower())

    def test_employee_cannot_approve_their_own_leave(self):
        req_id = self._apply(self.alice).data["id"]
        res = self.auth(self.alice).post(f"/api/leave-requests/{req_id}/approve/")
        self.assertEqual(res.status_code, 403)

    def test_manager_can_approve_teammate_but_not_other_department(self):
        alice_req = self._apply(self.alice).data["id"]
        bob_req = self._apply(self.bob).data["id"]

        ok = self.auth(self.manager).post(f"/api/leave-requests/{alice_req}/approve/",
                                          {"note": "fine"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data["status"], "APPROVED")

        not_ok = self.auth(self.manager).post(f"/api/leave-requests/{bob_req}/approve/")
        self.assertIn(not_ok.status_code, (403, 404))

    def test_approval_writes_leave_into_attendance(self):
        start = timezone.localdate() + timedelta(days=14)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        end = start + timedelta(days=2)
        res = self.auth(self.alice).post("/api/leave-requests/", {
            "leave_type": self.casual.id, "start_date": str(start),
            "end_date": str(end), "reason": "Trip",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)

        self.auth(self.hr).post(f"/api/leave-requests/{res.data['id']}/approve/")
        marked = Attendance.objects.filter(
            employee=self.emp_alice, date__range=(start, end),
            status=Attendance.Status.LEAVE).count()
        self.assertGreater(marked, 0)

    def test_approved_leave_reduces_balance(self):
        before = next(b for b in leave_balance(self.emp_alice) if b["code"] == "CL")["remaining"]
        req_id = self._apply(self.alice, start_offset=30, days=2).data["id"]
        self.auth(self.hr).post(f"/api/leave-requests/{req_id}/approve/")
        after = next(b for b in leave_balance(self.emp_alice) if b["code"] == "CL")["remaining"]
        self.assertLess(after, before)

    def test_employee_sees_only_own_requests(self):
        self._apply(self.alice)
        self._apply(self.bob)
        res = self.auth(self.alice).get("/api/leave-requests/")
        names = {row["employee_name"] for row in res.data["results"]}
        self.assertEqual(names, {"Alice Employee"})

    def test_cancel_removes_attendance_rows(self):
        start = timezone.localdate() + timedelta(days=21)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        res = self.auth(self.alice).post("/api/leave-requests/", {
            "leave_type": self.casual.id, "start_date": str(start),
            "end_date": str(start), "reason": "Errand",
        }, format="json")
        req_id = res.data["id"]
        self.auth(self.hr).post(f"/api/leave-requests/{req_id}/approve/")
        self.assertTrue(Attendance.objects.filter(
            employee=self.emp_alice, date=start, status=Attendance.Status.LEAVE).exists())

        self.auth(self.alice).post(f"/api/leave-requests/{req_id}/cancel/")
        self.assertFalse(Attendance.objects.filter(
            employee=self.emp_alice, date=start, status=Attendance.Status.LEAVE).exists())


class UserAdministrationTests(BaseFixture):
    def test_only_admin_lists_users(self):
        self.assertEqual(self.auth(self.hr).get("/api/users/").status_code, 403)
        self.assertEqual(self.auth(self.admin).get("/api/users/").status_code, 200)

    def test_admin_creates_and_deactivates_user(self):
        client = self.auth(self.admin)
        res = client.post("/api/users/", {
            "email": "temp@test.local", "full_name": "Temp Person",
            "role": "EMPLOYEE", "password": "Str0ngPass!23",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        uid = res.data["id"]

        deactivate = client.patch(f"/api/users/{uid}/", {"is_active": False}, format="json")
        self.assertEqual(deactivate.status_code, 200)
        login = APIClient().post("/api/auth/login/",
                                 {"email": "temp@test.local", "password": "Str0ngPass!23"},
                                 format="json")
        self.assertEqual(login.status_code, 401)

    def test_weak_password_rejected(self):
        res = self.auth(self.admin).post("/api/users/", {
            "email": "weak@test.local", "full_name": "Weak", "role": "EMPLOYEE",
            "password": "123",
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_admin_cannot_deactivate_self(self):
        res = self.auth(self.admin).patch(f"/api/users/{self.admin.id}/",
                                          {"is_active": False}, format="json")
        self.assertEqual(res.status_code, 400)


class SharedStateTests(BaseFixture):
    """The point of the whole app: one database, everybody sees the same rows."""

    def test_change_by_hr_is_visible_to_employee(self):
        patch = self.auth(self.hr).patch(f"/api/employees/{self.emp_alice.id}/",
                                         {"designation": "Senior Engineer"}, format="json")
        self.assertEqual(patch.status_code, 200, patch.data)
        res = self.auth(self.alice).get("/api/employees/me/")
        self.assertEqual(res.data["designation"], "Senior Engineer")

    def test_announcement_written_by_hr_appears_for_everyone(self):
        self.auth(self.hr).post("/api/announcements/", {
            "title": "Office closed Friday", "body": "Holiday.", "is_pinned": True,
        }, format="json")
        for user in (self.alice, self.manager, self.admin):
            res = self.auth(user).get("/api/announcements/")
            titles = [a["title"] for a in res.data["results"]]
            self.assertIn("Office closed Friday", titles)

    def test_employee_cannot_post_announcement(self):
        res = self.auth(self.alice).post("/api/announcements/", {
            "title": "Nope", "body": "Nope"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_activity_feed_records_who_did_what(self):
        self.auth(self.hr).patch(f"/api/employees/{self.emp_alice.id}/",
                                 {"designation": "Lead"}, format="json")
        res = self.auth(self.alice).get("/api/activity/")
        summaries = [row["summary"] for row in res.data["results"]]
        self.assertTrue(any("Alice Employee" in s for s in summaries))
        self.assertTrue(any(row["actor_name"] == "Hana HR" for row in res.data["results"]))


class DashboardTests(BaseFixture):
    def test_dashboard_is_scoped_by_role(self):
        emp = self.auth(self.alice).get("/api/dashboard/").data
        self.assertEqual(emp["scope"], "self")
        self.assertNotIn("org", emp)
        self.assertIn("me", emp)

        hr_dash = self.auth(self.hr).get("/api/dashboard/").data
        self.assertEqual(hr_dash["scope"], "org")
        self.assertEqual(hr_dash["org"]["total_employees"], 3)
        self.assertIn("department_breakdown", hr_dash)

    def test_report_csv_permissions(self):
        self.assertEqual(self.auth(self.alice).get("/api/reports/attendance.csv").status_code, 403)
        res = self.auth(self.hr).get("/api/reports/attendance.csv")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res["Content-Type"])


class ConstraintTests(BaseFixture):
    """Database-level guarantees, independent of the API."""

    def test_duplicate_attendance_blocked_by_db(self):
        from django.db import IntegrityError, transaction

        today = timezone.localdate()
        Attendance.objects.create(employee=self.emp_alice, date=today,
                                  status=Attendance.Status.PRESENT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(employee=self.emp_alice, date=today,
                                          status=Attendance.Status.ABSENT)

    def test_employee_code_is_unique(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Employee.objects.create(employee_code="E002", full_name="Clone",
                                        email="clone@test.local")

    def test_leave_days_exclude_weekends(self):
        friday = timezone.localdate() + timedelta(days=(4 - timezone.localdate().weekday()) % 7)
        monday = friday + timedelta(days=3)
        self.assertEqual(LeaveRequest.count_days(friday, monday), 2)


class ProfileSyncTests(BaseFixture):
    """A self-service profile edit must not desync the two rows."""

    def test_name_change_propagates_to_employee_record(self):
        res = self.auth(self.alice).patch("/api/auth/me/",
                                          {"full_name": "Alice A. Employee"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.emp_alice.refresh_from_db()
        self.assertEqual(self.emp_alice.full_name, "Alice A. Employee")
        # and HR sees the same name in the directory
        listing = self.auth(self.hr).get("/api/employees/").data["results"]
        self.assertIn("Alice A. Employee", [row["full_name"] for row in listing])

    def test_user_cannot_change_own_role_or_email(self):
        self.auth(self.alice).patch("/api/auth/me/",
                                    {"role": "ADMIN", "email": "hacker@test.local"}, format="json")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, Role.EMPLOYEE)
        self.assertEqual(self.alice.email, "alice@test.local")


class AttendanceScopeOnMyTabTests(BaseFixture):
    def test_mine_true_narrows_even_for_admin(self):
        today = timezone.localdate()
        Attendance.objects.create(employee=self.emp_alice, date=today,
                                  status=Attendance.Status.PRESENT)
        Attendance.objects.create(employee=self.emp_bob, date=today,
                                  status=Attendance.Status.ABSENT)

        # admin can see both, but the "my records" filter shows only their own
        self.assertEqual(self.auth(self.admin).get("/api/attendance/").data["count"], 2)
        self.assertEqual(
            self.auth(self.admin).get("/api/attendance/?mine=true").data["count"], 0
        )
        self.assertEqual(
            self.auth(self.alice).get("/api/attendance/?mine=true").data["count"], 1
        )
