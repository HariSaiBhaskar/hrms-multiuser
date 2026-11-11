"""Populate the database with a realistic multi-user demo.

    python manage.py seed_demo            # add demo data
    python manage.py seed_demo --flush    # wipe HR data first, then reseed

Everything is deterministic (fixed random seed), so two people running this
get the same dataset and screenshots stay comparable.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Announcement, AuditLog, Role, User
from hrms.models import Attendance, Department, Employee, Holiday, LeaveRequest, LeaveType

DEMO_PASSWORD = "Passw0rd!"

DEPARTMENTS = [
    ("Engineering", "ENG", "Product engineering and platform"),
    ("Human Resources", "HR", "People operations"),
    ("Sales", "SLS", "Revenue and account management"),
    ("Finance", "FIN", "Accounting, payroll and compliance"),
    ("Design", "DSN", "Product and brand design"),
]

LEAVE_TYPES = [
    ("Casual Leave", "CL", 12, True, True),
    ("Sick Leave", "SL", 10, True, True),
    ("Earned Leave", "EL", 15, True, True),
    ("Unpaid Leave", "LWP", 0, True, False),
]

PEOPLE = [
    # full_name, email, role, dept, designation, code
    ("Aarav Sharma", "admin@acme.test", Role.ADMIN, "Human Resources", "Director of Operations", "EMP001"),
    ("Priya Nair", "hr@acme.test", Role.HR, "Human Resources", "HR Business Partner", "EMP002"),
    ("Rahul Verma", "manager@acme.test", Role.MANAGER, "Engineering", "Engineering Manager", "EMP003"),
    ("Sneha Iyer", "employee@acme.test", Role.EMPLOYEE, "Engineering", "Backend Developer", "EMP004"),
    ("Karthik Reddy", "karthik@acme.test", Role.EMPLOYEE, "Engineering", "Frontend Developer", "EMP005"),
    ("Meera Krishnan", "meera@acme.test", Role.MANAGER, "Sales", "Sales Manager", "EMP006"),
    ("Ananya Bose", "ananya@acme.test", Role.EMPLOYEE, "Sales", "Account Executive", "EMP007"),
    ("Vikram Singh", "vikram@acme.test", Role.EMPLOYEE, "Design", "Product Designer", "EMP008"),
    ("Divya Menon", "divya@acme.test", Role.EMPLOYEE, "Finance", "Financial Analyst", "EMP009"),
    ("Arjun Pillai", "arjun@acme.test", Role.EMPLOYEE, "Engineering", "QA Engineer", "EMP010"),
]

ANNOUNCEMENTS = [
    ("Welcome to the new HR portal",
     "Everyone now has their own login. Attendance, leave requests and team "
     "directories are all in one place. Please check in before 09:30 each day.",
     True),
    ("Quarterly all-hands on Friday",
     "The all-hands is at 16:00 in the main hall. Attendance will be marked "
     "automatically - no need to check in that afternoon.", False),
    ("Updated leave policy",
     "Earned leave now carries forward up to 15 days. Anything beyond that lapses "
     "on 31 December. Speak to HR if you have questions.", False),
]


class Command(BaseCommand):
    help = "Seed the database with demo departments, users, employees and attendance."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Delete existing HR data before seeding.")
        parser.add_argument("--days", type=int, default=30,
                            help="How many past days of attendance to generate.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20261024)  # deterministic

        if options["flush"]:
            self.stdout.write("Flushing existing HR data...")
            LeaveRequest.objects.all().delete()
            Attendance.objects.all().delete()
            Employee.objects.all().update(user=None, manager=None)
            Department.objects.all().update(head=None)
            Employee.objects.all().delete()
            Department.objects.all().delete()
            LeaveType.objects.all().delete()
            Holiday.objects.all().delete()
            Announcement.objects.all().delete()
            AuditLog.objects.all().delete()
            User.objects.all().delete()

        # ---- leave types & holidays --------------------------------------
        leave_types = {}
        for name, code, quota, approval, paid in LEAVE_TYPES:
            lt, _ = LeaveType.objects.get_or_create(
                code=code,
                defaults={"name": name, "annual_quota": quota,
                          "requires_approval": approval, "is_paid": paid},
            )
            leave_types[code] = lt

        today = timezone.localdate()
        for name, offset in [("Diwali", 12), ("Christmas", 62), ("New Year", 69), ("Holi", 140)]:
            Holiday.objects.get_or_create(
                date=today + timedelta(days=offset), defaults={"name": name}
            )

        # ---- departments --------------------------------------------------
        depts = {}
        for name, code, desc in DEPARTMENTS:
            dept, _ = Department.objects.get_or_create(
                code=code, defaults={"name": name, "description": desc}
            )
            depts[name] = dept

        # ---- users + employees --------------------------------------------
        employees = {}
        for idx, (full_name, email, role, dept_name, designation, code) in enumerate(PEOPLE):
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": full_name,
                    "role": role,
                    "job_title": designation,
                    "phone": f"+91 90000 {10000 + idx}",
                    "is_staff": role in (Role.ADMIN, Role.HR),
                    "is_superuser": role == Role.ADMIN,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()

            emp, _ = Employee.objects.get_or_create(
                employee_code=code,
                defaults={
                    "user": user,
                    "full_name": full_name,
                    "email": email,
                    "phone": user.phone,
                    "department": depts[dept_name],
                    "designation": designation,
                    "employment_type": Employee.EmploymentType.FULL_TIME,
                    "date_of_joining": today - timedelta(days=random.randint(120, 1200)),
                },
            )
            if emp.user_id is None:
                emp.user = user
                emp.save(update_fields=["user"])
            employees[code] = emp

        # department heads + reporting lines
        heads = {"Engineering": "EMP003", "Human Resources": "EMP002",
                 "Sales": "EMP006", "Design": "EMP008", "Finance": "EMP009"}
        for dept_name, code in heads.items():
            depts[dept_name].head = employees[code]
            depts[dept_name].save(update_fields=["head"])

        reporting = {"EMP004": "EMP003", "EMP005": "EMP003", "EMP010": "EMP003",
                     "EMP007": "EMP006"}
        for emp_code, mgr_code in reporting.items():
            employees[emp_code].manager = employees[mgr_code]
            employees[emp_code].save(update_fields=["manager"])

        # ---- attendance for the past N days --------------------------------
        generated = 0
        for offset in range(options["days"], 0, -1):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:      # skip weekends
                continue
            if Holiday.objects.filter(date=day).exists():
                continue

            for code, emp in employees.items():
                if emp.date_of_joining > day:
                    continue

                roll = random.random()
                if roll < 0.06:
                    att_status = Attendance.Status.ABSENT
                elif roll < 0.10:
                    att_status = Attendance.Status.LEAVE
                elif roll < 0.16:
                    att_status = Attendance.Status.WFH
                else:
                    att_status = Attendance.Status.PRESENT

                check_in = check_out = None
                if att_status in (Attendance.Status.PRESENT, Attendance.Status.WFH):
                    hour = 9 if random.random() < 0.8 else 10
                    minute = random.randint(0, 29) if hour == 9 else random.randint(0, 45)
                    check_in = timezone.datetime(2000, 1, 1, hour, minute).time()
                    out_hour = 17 if random.random() < 0.5 else 18
                    check_out = timezone.datetime(
                        2000, 1, 1, out_hour, random.randint(0, 59)
                    ).time()

                Attendance.objects.update_or_create(
                    employee=emp, date=day,
                    defaults={
                        "status": att_status,
                        "check_in": check_in,
                        "check_out": check_out,
                        "marked_by": emp.user,
                    },
                )
                generated += 1

        # ---- leave requests ------------------------------------------------
        sample_requests = [
            ("EMP004", "CL", 6, 1, "PENDING", "Family function at home."),
            ("EMP005", "SL", 3, 2, "APPROVED", "Fever, doctor advised rest."),
            ("EMP007", "EL", 10, 5, "PENDING", "Annual vacation with family."),
            ("EMP010", "CL", 20, 1, "REJECTED", "Personal errand."),
            ("EMP008", "EL", 2, 3, "PENDING", "Cousin's wedding."),
            ("EMP009", "SL", 1, 1, "APPROVED", "Migraine."),
        ]
        for code, lt_code, start_offset, length, lv_status, reason in sample_requests:
            emp = employees[code]
            start = today + timedelta(days=start_offset)
            end = start + timedelta(days=length - 1)
            req, created = LeaveRequest.objects.get_or_create(
                employee=emp, leave_type=leave_types[lt_code], start_date=start,
                defaults={
                    "end_date": end,
                    "days": LeaveRequest.count_days(start, end),
                    "reason": reason,
                    "status": lv_status,
                },
            )
            if created and lv_status in (LeaveRequest.Status.APPROVED,
                                         LeaveRequest.Status.REJECTED):
                req.decided_by = User.objects.get(email="hr@acme.test")
                req.decided_at = timezone.now()
                req.save(update_fields=["decided_by", "decided_at"])

        # ---- announcements -------------------------------------------------
        hr_user = User.objects.get(email="hr@acme.test")
        for title, body, pinned in ANNOUNCEMENTS:
            Announcement.objects.get_or_create(
                title=title, defaults={"body": body, "is_pinned": pinned, "author": hr_user}
            )

        AuditLog.record(None, AuditLog.Action.CREATE, "system",
                        "Demo data seeded")

        # ---- summary -------------------------------------------------------
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded: {User.objects.count()} users, {Employee.objects.count()} employees, "
            f"{Department.objects.count()} departments, {Attendance.objects.count()} attendance rows, "
            f"{LeaveRequest.objects.count()} leave requests ({generated} attendance rows generated)."
        ))
        self.stdout.write("\nLogin accounts (all share the same demo password):\n")
        self.stdout.write(f"  {'ROLE':<10} {'EMAIL':<24} PASSWORD")
        for full_name, email, role, *_ in PEOPLE[:4]:
            self.stdout.write(f"  {role:<10} {email:<24} {DEMO_PASSWORD}")
        self.stdout.write(
            "\nChange these before letting anyone else use the app.\n"
        )
