# START HERE

You have a working multi-user HRMS. This file is the 10-minute path from zero to
two people using it at once. Deeper detail is in `README.md`, and
`docs/WALKTHROUGH.md` shows what each screen looks like.

---

## 0. What you need installed

| Tool | Version | Check |
|---|---|---|
| Python | 3.11 – 3.13 | `python --version` |
| Node.js | 18 or 20 LTS | `node --version` |
| MySQL Server | 8.x (or MariaDB 10.6+) | `mysql --version` |

Open **this folder** in VS Code (`File → Open Folder`), not `backend/` — the tasks and
interpreter path assume the workspace root.

---

## 1. Create the database (once)

```powershell
mysql -u root -p < setup\database.sql
```

Edit the password inside `setup/database.sql` first if you want something other than the
placeholder, and use the same value in step 2.

---

## 2. Configure the backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1          # cmd.exe: venv\Scripts\activate.bat
pip install -r requirements.txt
pip install mysqlclient              # if this fails: pip install pymysql
Copy-Item .env.example .env
```

Open `backend/.env` and set `DB_PASSWORD` to the password from step 1. That's the only edit
required — `DB_ENGINE=mysql` is already set.

---

## 3. Create tables and demo data

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

`seed_demo` builds 10 employees, 5 departments, 4 leave types, 220 attendance rows and 6 leave
requests, and prints the login accounts. Expect:

```
Seeded: 10 users, 10 employees, 5 departments, 220 attendance rows, 6 leave requests
```

Backend is up when <http://127.0.0.1:8000/> returns
`{"status": "ok", "database": "mysql", "database_connected": true}`.

---

## 4. Start the frontend (second terminal)

```powershell
cd frontend
npm install
npm start
```

Vite opens <http://localhost:5173/>. The dev server proxies `/api` to Django, so there is no
CORS setup to get wrong.

---

## 5. Sign in

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@acme.test` | `Passw0rd!` |
| HR officer | `hr@acme.test` | `Passw0rd!` |
| Manager | `manager@acme.test` | `Passw0rd!` |
| Employee | `employee@acme.test` | `Passw0rd!` |

They all share one database. Sign in as HR in a normal window and as the employee in a private
window, then compare what each one sees.

---

## 6. Prove it is multi-user

1. Both windows: open **Announcements**.
2. As HR, click **+ New announcement**, write something, **Post**.
3. Leave the employee window alone. Within ~10 seconds (or immediately when you click back to
   that tab) the notice appears — no reload.

Do it in the other direction too: as the employee, change your name under **My profile**, then
look at HR's **Employees** table. Same rows, same database.

Then try to break the isolation:

- As the employee, open <http://127.0.0.1:8000/api/employees/> in a browser where you are
  logged out → `401`.
- With the employee's token, request a colleague's record by id → `404`.
- Try to approve your own leave → `403`.

---

## Everyday commands

```powershell
# backend  (from backend\ with the venv active)
python manage.py runserver
python manage.py test                 # 44 tests, runs against real MySQL
python manage.py seed_demo --flush    # wipe HR data and reseed
python manage.py createsuperuser      # extra admin for /admin/

# frontend (from frontend\)
npm start
npm run build                         # production bundle into frontend/dist
```

VS Code: `Ctrl+Shift+B` → **Run everything (backend + frontend)**.
`F5` → **Django: runserver (debug)** for breakpoints.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Error loading MySQLdb module` | `pip install mysqlclient`, or `pip install pymysql` (the project already accepts either) |
| `(1045, "Access denied")` | `DB_PASSWORD` in `backend/.env` differs from MySQL; restart `runserver` after editing |
| `(2003, "Can't connect")` | MySQL service isn't running: `Get-Service *mysql*` |
| `'mysql' is not recognized` | MySQL `bin` is not on PATH; use the full path or MySQL Workbench |
| Frontend loads but every request fails | Is Django running? Check <http://127.0.0.1:8000/> |
| Port 5173 in use | Vite picks 5174 automatically and the proxy still works |
| `Unknown database 'test_hrms_db'` in tests | run `setup/database.sql` again — it grants the test DB too |
| Login says incorrect password | demo users only exist after `seed_demo` |
| Want to start clean | `python manage.py seed_demo --flush` |

---

## Where things live

```
backend/accounts/   users, roles, JWT, audit log, announcements
backend/hrms/       departments, employees, attendance, leave + tests.py (44 tests)
backend/config/     settings.py (DB switch), urls.py
frontend/src/pages/ one file per screen
frontend/src/api.js axios + token refresh + error handling
docs/WALKTHROUGH.md screenshots of every screen
```

Read `hrms/scoping.py` first if you want to understand the security model — that single file
decides who may see which rows, and every viewset goes through it.
