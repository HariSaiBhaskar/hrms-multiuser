# Multi-user HRMS — Django + MySQL + React

A real multi-user HR management system. **One shared MySQL database, four roles, and every
change instantly visible to every signed-in user.** Not a single-user CRUD demo.

- **Backend:** Django 5.2 LTS + Django REST Framework + SimpleJWT + MySQL 8 / MariaDB
- **Frontend:** React 18 + Vite (no UI framework — one hand-written stylesheet)
- **Database:** MySQL, with real constraints, indexes, joins and aggregates
- **Tests:** 44 automated tests, all passing against a real MySQL server

---

## What "multi-user" actually means here

| Concern | How it's handled |
|---|---|
| Every user shares data | Single MySQL database. Nothing is stored in the browser except JWTs. |
| Changes reach everyone | Every list/dashboard re-fetches on a 10s interval **and** on tab focus. New rows appear without a page reload. |
| Data isolation | Querysets are filtered **before** serialization, by role. A crafted request gets 404/403, not a hidden button. |
| Who did what | `AuditLog` row written on every create/update/delete/approve/check-in/login. Visible to everyone in the Activity feed. |
| Concurrent check-ins | `select_for_update()` transaction + a DB unique constraint on `(employee, date)`. Two clicks can't create two rows. |
| Roles | ADMIN / HR / MANAGER / EMPLOYEE, enforced server-side in permission classes. |

### Role matrix (verified by the test suite)

| Capability | Admin | HR | Manager | Employee |
|---|:--:|:--:|:--:|:--:|
| See own profile & attendance | ✅ | ✅ | ✅ | ✅ |
| Check in / out | ✅ | ✅ | ✅ | ✅ |
| Request own leave | ✅ | ✅ | ✅ | ✅ |
| See own department's people | ✅ | ✅ | ✅ | ❌ (self only) |
| See the whole organisation | ✅ | ✅ | ❌ | ❌ |
| Create / edit / delete employees | ✅ | ✅ | ❌ | ❌ |
| Mark attendance for others | ✅ | ✅ | ❌ | ❌ |
| Approve leave | ✅ | ✅ | own dept only | ❌ |
| Approve **own** leave | ❌ | ❌ | ❌ | ❌ |
| Post announcements | ✅ | ✅ | ❌ | ❌ |
| Manage user accounts & roles | ✅ | ❌ | ❌ | ❌ |
| View reports / export CSV | ✅ | ✅ | own dept | ❌ |

---

## Quick start (Windows + VS Code)

Prerequisites: **Python 3.11+**, **Node 18+**, **MySQL 8** (or MariaDB 10.6+) with Workbench.

### 1. Database

```powershell
mysql -u root -p < setup\database.sql
```

Creates the `hrms_db` schema and an `hrms_user` account with privileges on that schema only.

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1          # cmd.exe: venv\Scripts\activate.bat
pip install -r requirements.txt
pip install mysqlclient              # if this fails, use: pip install pymysql

Copy-Item .env.example .env          # then edit the password
python manage.py migrate
python manage.py seed_demo           # demo users, departments, 220 attendance rows
python manage.py runserver
```

Backend: <http://127.0.0.1:8000/> → `{"status": "ok", "database": "mysql", ...}`
API browser: <http://127.0.0.1:8000/api/> · Admin: <http://127.0.0.1:8000/admin/>

### 3. Frontend (second terminal)

```powershell
cd frontend
npm install
npm start
```

App: <http://localhost:5173/>

### 4. Sign in as four different people

| Role | Email | Password | Sees |
|---|---|---|---|
| Admin | `admin@acme.test` | `Passw0rd!` | everything + user accounts |
| HR | `hr@acme.test` | `Passw0rd!` | all employees, approvals |
| Manager | `manager@acme.test` | `Passw0rd!` | own department only |
| Employee | `employee@acme.test` | `Passw0rd!` | self-service only |

**The demo that proves it's multi-user:** open two browsers (or one normal + one private
window), sign in as HR in one and as the Employee in the other, keep both on the
Announcements page, and post a notice as HR. The employee's page picks it up in ~5 seconds
without anyone pressing reload.

---

## Architecture

```
React 18 (Vite, :5173)
  │  axios  ·  JWT in localStorage  ·  auto-refresh on 401  ·  10s polling
  ▼
Django REST Framework (:8000)
  ├── accounts/     User (email login), roles, AuditLog, Announcements, JWT auth
  ├── hrms/         Department, Employee, Attendance, LeaveType, LeaveRequest, Holiday
  │                 scoping.py  -> who may read which rows
  │                 services.py -> business rules (check-in, leave approval, balances)
  └── config/       settings (DB_ENGINE switch), urls
  ▼
MySQL 8
```

### Data model

```
User 1───1 Employee ───1 Department
              │  └──self-FK── manager
              ├──< Attendance        UNIQUE (employee, date)
              └──< LeaveRequest >── LeaveType
Department.head ──> Employee (nullable, circular on purpose)
```

Constraints that are enforced by **the database**, not just the API:

- `Attendance`: `UNIQUE (employee, date)` — one row per person per day.
- `Employee.employee_code`, `Employee.email`, `User.email`, `Department.code/name`,
  `Holiday.date`: unique.
- `LeaveRequest.leave_type` is `PROTECT` — you cannot delete a leave type that is in use.
- `Attendance(employee)` and `LeaveRequest(employee)` cascade on employee deletion.
- Indexes on `(status)`, `(department, status)`, `(date, status)`, `(employee, status)`.

### Where the SQL happens

`hrms/services.py` and the report views use real aggregate queries, not Python loops:

```python
Attendance.objects.filter(employee__in=team, date__range=(start, end))
    .values("employee_id", "employee__full_name")
    .annotate(
        present=Count("id", filter=Q(status="PRESENT")),
        absent=Count("id",  filter=Q(status="ABSENT")),
        total=Count("id"),
    )
```

Set `SQL_LOG_LEVEL=DEBUG` in `.env` to print every statement Django runs, if you want to
watch the ORM turn these into `SELECT ... LEFT JOIN ... GROUP BY`.

---

## API reference

All endpoints require `Authorization: Bearer <access>`. Errors share one envelope:
`{"detail": "...", "errors": {"field": ["message"]}}`.

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/login/` | `{email, password}` → `{access, refresh, user}` (rate-limited) |
| POST | `/api/auth/refresh/` | rotate the access token |
| POST | `/api/auth/logout/` | audit entry |
| GET/PATCH | `/api/auth/me/` | own profile; name/phone/title sync to the employee record |
| POST | `/api/auth/change-password/` | current + new password |

### HR domain
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/api/employees/` | role-scoped list; `?search=&department=&status=&page=` |
| GET | `/api/employees/me/` | own employee record |
| GET | `/api/employees/lookup/` | flat list for dropdowns |
| GET | `/api/employees/{id}/attendance/?month=YYYY-MM` | one person's month |
| GET | `/api/employees/{id}/leave_balance/` | quota vs used |
| POST | `/api/attendance/check-in/` · `check-out/` | self service, idempotent |
| GET | `/api/attendance/today/` | today's row |
| POST | `/api/attendance/mark/` | HR bulk mark `{date, employee_ids[], status}` |
| GET | `/api/attendance/summary/?month=&department=` | aggregates per employee |
| GET/POST | `/api/leave-requests/` | `?mine=true`, `?pending_my_approval=true` |
| POST | `/api/leave-requests/{id}/approve/` · `reject/` · `cancel/` | workflow |
| GET | `/api/leave-requests/balance/` | per-type balance |
| CRUD | `/api/departments/` `/api/leave-types/` `/api/holidays/` | HR writes, everyone reads |
| GET | `/api/dashboard/` | role-scoped summary in one call |
| GET | `/api/reports/attendance.csv?month=` | Excel-friendly export (manager+) |
| CRUD | `/api/users/` | admin only; plus `POST /api/users/{id}/reset-password/` |
| GET | `/api/activity/` | shared audit feed |

---

## Tests

```powershell
cd backend
python manage.py test
```

44 tests. They assert the things that actually matter in a multi-user app:

```
test_employee_sees_only_their_own_record
test_employee_cannot_open_a_colleagues_detail_page      -> 404
test_employee_cannot_mark_attendance_for_someone_else   -> 403
test_employee_cannot_approve_their_own_leave            -> 403
test_manager_can_approve_teammate_but_not_other_department
test_approval_writes_leave_into_attendance
test_approved_leave_reduces_balance
test_duplicate_attendance_blocked_by_db                 -> IntegrityError
test_change_by_hr_is_visible_to_employee
test_announcement_written_by_hr_appears_for_everyone
test_admin_cannot_deactivate_self
test_name_change_propagates_to_employee_record
```

Run against MySQL by default (uses `test_hrms_db`), so constraints and collation behave
exactly as in production. `DB_ENGINE=sqlite python manage.py test` also works.

---

## Security notes

Present and working:

- JWT access + refresh with automatic rotation; the SPA refreshes silently on 401.
- Password hashing via Django's PBKDF2; validators enforce length, common-password and
  numeric-only checks.
- Login rate-limited (`20/min` by default, `LOGIN_RATE` in `.env`), and every attempt is logged.
- `IsAuthenticated` is the **default** permission — endpoints opt out, not in.
- Object-level access control in querysets, so URL guessing returns 404.
- Admin cannot deactivate or demote their own account (no self-lockout).
- HR cannot mint ADMIN accounts (no privilege escalation).
- `SECRET_KEY` and DB credentials come from the environment; `DEBUG=False` requires a real key.

Before exposing this to the internet, also do: set `DEBUG=False`, a strong `SECRET_KEY`,
an explicit `ALLOWED_HOSTS`, HTTPS-only cookies, `gunicorn` instead of `runserver`, and — for
a genuinely multi-tenant product — replace polling with WebSockets and keep JWTs in
`httpOnly` cookies rather than `localStorage`.

---

## Layout

```
backend/
  accounts/    custom User (email login), roles, permissions, audit, announcements, JWT views
  hrms/        models, scoping, services, serializers, views, 44 tests
  config/      settings (DB switch), urls, wsgi/asgi, MySQL driver shim
  manage.py  requirements.txt  .env.example
frontend/
  src/api.js           axios + silent token refresh + unified error parsing
  src/auth.jsx         auth context, permission helpers
  src/components/      Layout (sidebar/topbar), ui.jsx (icons, modal, table helpers, useLive)
  src/pages/           Login, Dashboard, Employees, Attendance, Leave, Reports,
                       Departments, Announcements, Activity, Users, Profile
  src/styles.css       the whole design system
setup/database.sql     schema + app user
docs/                  screenshots and the walkthrough
```

## Everyday commands

```powershell
# backend
cd backend\hrms_backend 2>$null; cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver
python manage.py test
python manage.py seed_demo --flush      # reset demo data

# frontend
cd frontend
npm start
```
