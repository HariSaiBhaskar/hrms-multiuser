import { useEffect, useState } from "react";
import api, { errorMessage, fieldErrors } from "../api";
import { useAuth } from "../auth";
import {
  Alert, Badge, Empty, Field, Modal, Pagination, Spinner, fmtDate, useLive, useToast,
} from "../components/ui";

const BLANK = {
  employee_code: "", full_name: "", email: "", phone: "", department: "",
  designation: "", employment_type: "FULL_TIME", status: "ACTIVE",
  date_of_joining: new Date().toISOString().slice(0, 10), manager: "", notes: "",
  create_account: false, account_role: "EMPLOYEE",
};

export default function Employees() {
  const { can } = useAuth();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState(null); // null | {} | employee
  const [deleting, setDeleting] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [fieldErr, setFieldErr] = useState({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [createdCreds, setCreatedCreds] = useState(null);
  const [departments, setDepartments] = useState([]);

  const { data, error: loadError, loading } = useLive(async () => {
    const params = { page };
    if (search) params.search = search;
    if (department) params.department = department;
    if (status) params.status = status;
    const res = await api.get("/employees/", { params });
    return res.data;
  }, [page, search, department, status]);

  useEffect(() => {
    api.get("/departments/").then(({ data }) => setDepartments(data.results || data)).catch(() => {});
  }, []);

  const openCreate = () => {
    setForm(BLANK);
    setFieldErr({});
    setError("");
    setEditing({ mode: "create" });
  };

  const openEdit = (employee) => {
    setForm({
      ...BLANK,
      ...employee,
      department: employee.department || "",
      manager: employee.manager || "",
    });
    setFieldErr({});
    setError("");
    setEditing({ mode: "edit", id: employee.id });
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setFieldErr({});
    const payload = {
      ...form,
      department: form.department || null,
      manager: form.manager || null,
    };
    if (editing.mode === "edit") {
      delete payload.create_account;
      delete payload.account_role;
    }
    try {
      if (editing.mode === "create") {
        const { data } = await api.post("/employees/", payload);
        setEditing(null);
        if (data.temporary_password) {
          setCreatedCreds({
            name: data.full_name,
            email: data.email,
            password: data.temporary_password,
          });
        } else {
          toast.show(`${data.full_name} added.`);
        }
      } else {
        await api.patch(`/employees/${editing.id}/`, payload);
        setEditing(null);
        toast.show("Employee updated.");
      }
    } catch (err) {
      setFieldErr(fieldErrors(err));
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    try {
      await api.delete(`/employees/${deleting.id}/`);
      toast.show(`${deleting.full_name} removed.`);
      setDeleting(null);
    } catch (err) {
      toast.show(errorMessage(err), "error");
      setDeleting(null);
    }
  };

  const rows = data?.results || [];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{can.managePeople ? "Employees" : "People directory"}</h1>
          <div className="sub">
            {can.managePeople
              ? "Everyone in the organisation. Changes are visible to the whole team immediately."
              : "You can see the people you work with."}
          </div>
        </div>
        {can.managePeople && (
          <div className="page-head-actions">
            <button className="btn primary" onClick={openCreate}>+ Add employee</button>
          </div>
        )}
      </div>

      {toast.node}

      {createdCreds && (
        <Alert kind="success" onClose={() => setCreatedCreds(null)}>
          <strong>{createdCreds.name}</strong> can now sign in.
          <div style={{ marginTop: 6, fontFamily: "monospace", fontSize: 12.5 }}>
            {createdCreds.email} / {createdCreds.password}
          </div>
          <div style={{ marginTop: 6, fontSize: 12 }}>
            This password is shown once and is not stored anywhere - share it securely.
            It must be changed at first sign-in.
          </div>
        </Alert>
      )}

      <div className="card">
        <div className="card-head">
          <div className="filters" style={{ flex: 1 }}>
            <div className="field">
              <input
                className="search-input"
                placeholder="Search name, code, email..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              />
            </div>
            <div className="field">
              <select value={department} onChange={(e) => { setDepartment(e.target.value); setPage(1); }}>
                <option value="">All departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                <option value="">Any status</option>
                <option value="ACTIVE">Active</option>
                <option value="ON_LEAVE">On leave</option>
                <option value="RESIGNED">Resigned</option>
              </select>
            </div>
          </div>
        </div>

        {loadError && <div className="card-body"><Alert kind="error">{loadError}</Alert></div>}
        {loading && !data ? (
          <Spinner block />
        ) : rows.length === 0 ? (
          <Empty icon="users" title="No employees found">
            {can.managePeople ? "Add your first employee to get started." : "Nothing matches your filters."}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Designation</th>
                    <th>Joined</th>
                    <th>Login</th>
                    <th>Status</th>
                    {can.managePeople && <th className="right">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((emp) => (
                    <tr key={emp.id}>
                      <td>
                        <div className="inline" style={{ gap: 10 }}>
                          <div className="avatar sm">
                            {emp.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                          </div>
                          <div>
                            <div className="cell-main">{emp.full_name}</div>
                            <div className="cell-sub">{emp.employee_code} · {emp.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>{emp.department_name || <span className="faint">Unassigned</span>}</td>
                      <td>{emp.designation || <span className="faint">-</span>}</td>
                      <td className="mono">{fmtDate(emp.date_of_joining)}</td>
                      <td>
                        {emp.has_account ? (
                          <Badge value={emp.account_role} />
                        ) : (
                          <span className="faint">no account</span>
                        )}
                      </td>
                      <td><Badge value={emp.status} /></td>
                      {can.managePeople && (
                        <td>
                          <div className="row-actions">
                            <button className="btn sm" onClick={() => openEdit(emp)}>Edit</button>
                            <button className="btn sm danger" onClick={() => setDeleting(emp)}>Delete</button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </>
        )}
      </div>

      {editing && (
        <Modal
          title={editing.mode === "create" ? "Add employee" : "Edit employee"}
          onClose={() => setEditing(null)}
          wide
          footer={
            <>
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn primary" onClick={save} disabled={saving}>
                {saving ? "Saving..." : editing.mode === "create" ? "Create employee" : "Save changes"}
              </button>
            </>
          }
        >
          <form onSubmit={save}>
            {error && <Alert kind="error">{error}</Alert>}
            <div className="grid two" style={{ gap: 0 }}>
              <Field label="Full name" error={fieldErr.full_name?.[0]}>
                <input
                  className={fieldErr.full_name ? "invalid" : ""}
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </Field>
              <Field label="Employee code" error={fieldErr.employee_code?.[0]} hint="Unique, e.g. EMP011">
                <input
                  className={fieldErr.employee_code ? "invalid" : ""}
                  value={form.employee_code}
                  onChange={(e) => setForm({ ...form, employee_code: e.target.value })}
                  required
                />
              </Field>
              <Field label="Work email" error={fieldErr.email?.[0]}>
                <input
                  type="email"
                  className={fieldErr.email ? "invalid" : ""}
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </Field>
              <Field label="Phone">
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </Field>
              <Field label="Department" error={fieldErr.department?.[0]}>
                <select value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
                  <option value="">Unassigned</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Designation">
                <input value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} />
              </Field>
              <Field label="Employment type">
                <select value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })}>
                  <option value="FULL_TIME">Full time</option>
                  <option value="PART_TIME">Part time</option>
                  <option value="CONTRACT">Contract</option>
                  <option value="INTERN">Intern</option>
                </select>
              </Field>
              <Field label="Status">
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option value="ACTIVE">Active</option>
                  <option value="ON_LEAVE">On leave</option>
                  <option value="RESIGNED">Resigned</option>
                </select>
              </Field>
              <Field label="Date of joining">
                <input type="date" value={form.date_of_joining} onChange={(e) => setForm({ ...form, date_of_joining: e.target.value })} />
              </Field>
              <Field label="Reports to">
                <select value={form.manager} onChange={(e) => setForm({ ...form, manager: e.target.value })}>
                  <option value="">Nobody</option>
                  {rows.filter((r) => r.id !== editing.id).map((r) => (
                    <option key={r.id} value={r.id}>{r.full_name}</option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Notes">
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>

            {editing.mode === "create" && (
              <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 10, padding: 14 }}>
                <label className="inline" style={{ fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    style={{ width: "auto" }}
                    checked={form.create_account}
                    onChange={(e) => setForm({ ...form, create_account: e.target.checked })}
                  />
                  Create a login account for this employee
                </label>
                {form.create_account && (
                  <div style={{ marginTop: 12 }}>
                    <Field
                      label="Account role"
                      hint="Determines what this person can see and do. A temporary password is generated for you to share."
                      error={fieldErr.account_role?.[0]}
                    >
                      <select value={form.account_role} onChange={(e) => setForm({ ...form, account_role: e.target.value })}>
                        <option value="EMPLOYEE">Employee - self service only</option>
                        <option value="MANAGER">Manager - own department</option>
                        <option value="HR">HR - all employees</option>
                        <option value="ADMIN">Administrator - full control</option>
                      </select>
                    </Field>
                  </div>
                )}
              </div>
            )}
          </form>
        </Modal>
      )}

      {deleting && (
        <Modal
          title="Remove employee"
          onClose={() => setDeleting(null)}
          footer={
            <>
              <button className="btn" onClick={() => setDeleting(null)}>Cancel</button>
              <button className="btn danger" onClick={confirmDelete}>Delete permanently</button>
            </>
          }
        >
          <p>
            Delete <strong>{deleting.full_name}</strong> ({deleting.employee_code})?
          </p>
          <p className="faint">
            Their attendance and leave records are deleted with them. The login account
            is kept but unlinked - deactivate it under User accounts.
          </p>
        </Modal>
      )}
    </div>
  );
}
