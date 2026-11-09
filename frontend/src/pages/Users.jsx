import { useState } from "react";
import api, { errorMessage, fieldErrors } from "../api";
import {
  Alert, Badge, Empty, Field, Modal, Pagination, Spinner, fmtDateTime, useLive, useToast,
} from "../components/ui";

const BLANK = { email: "", full_name: "", role: "EMPLOYEE", phone: "", job_title: "", password: "" };

export default function Users() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState("");
  const [fieldErr, setFieldErr] = useState({});
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  const { data, error: loadError, loading } = useLive(async () => {
    const params = { page };
    if (search) params.search = search;
    if (role) params.role = role;
    const { data } = await api.get("/users/", { params });
    return data;
  }, [page, search, role]);

  const save = async () => {
    setBusy(true);
    setError("");
    setFieldErr({});
    try {
      if (editing.id) {
        const payload = { ...form };
        delete payload.password;
        payload.email = undefined;
        await api.patch(`/users/${editing.id}/`, payload);
        toast.show("Account updated.");
      } else {
        await api.post("/users/", form);
        toast.show("Account created - share the password securely.");
      }
      setEditing(null);
    } catch (err) {
      setFieldErr(fieldErrors(err));
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (user) => {
    try {
      await api.patch(`/users/${user.id}/`, { is_active: !user.is_active });
      toast.show(user.is_active ? "Account deactivated." : "Account reactivated.");
    } catch (err) {
      toast.show(errorMessage(err), "error");
    }
  };

  const resetPassword = async () => {
    setBusy(true);
    try {
      await api.post(`/users/${resetting.id}/reset-password/`, { password: newPassword });
      toast.show(`Password reset. ${resetting.full_name} must change it at next sign-in.`);
      setResetting(null);
      setNewPassword("");
    } catch (err) {
      toast.show(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const rows = data?.results || [];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>User accounts</h1>
          <div className="sub">
            Who can sign in, and what they are allowed to do. Role changes take effect
            immediately for everyone.
          </div>
        </div>
        <div className="page-head-actions">
          <button className="btn primary" onClick={() => { setForm(BLANK); setFieldErr({}); setError(""); setEditing({ mode: "create" }); }}>
            + New account
          </button>
        </div>
      </div>

      {toast.node}

      <div className="card">
        <div className="card-head">
          <div className="filters" style={{ flex: 1 }}>
            <div className="field">
              <input
                className="search-input"
                placeholder="Search name or email..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              />
            </div>
            <div className="field">
              <select value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
                <option value="">All roles</option>
                <option value="ADMIN">Administrator</option>
                <option value="HR">HR officer</option>
                <option value="MANAGER">Manager</option>
                <option value="EMPLOYEE">Employee</option>
              </select>
            </div>
          </div>
        </div>

        {loadError && <div className="card-body"><Alert kind="error">{loadError}</Alert></div>}

        {loading && !data ? (
          <Spinner block />
        ) : rows.length === 0 ? (
          <Empty icon="shield" title="No accounts found" />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Role</th>
                    <th>Linked employee</th>
                    <th>Last seen</th>
                    <th>Status</th>
                    <th className="right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <div className="cell-main">{u.full_name}</div>
                        <div className="cell-sub">{u.email}</div>
                      </td>
                      <td><Badge value={u.role} /></td>
                      <td className="faint">{u.employee_code || "not linked"}</td>
                      <td className="faint">{u.last_seen_at ? fmtDateTime(u.last_seen_at) : "never"}</td>
                      <td>
                        {u.is_active ? <Badge value="ACTIVE" label="Active" /> : <Badge value="RESIGNED" label="Disabled" />}
                        {u.must_change_password && <span className="badge amber" style={{ marginLeft: 6 }}>temp password</span>}
                      </td>
                      <td>
                        <div className="row-actions">
                          <button className="btn sm" onClick={() => { setForm({ ...u, password: "" }); setFieldErr({}); setError(""); setEditing(u); }}>
                            Edit
                          </button>
                          <button className="btn sm" onClick={() => setResetting(u)}>Reset password</button>
                          <button className="btn sm danger" onClick={() => toggleActive(u)}>
                            {u.is_active ? "Disable" : "Enable"}
                          </button>
                        </div>
                      </td>
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
          title={editing.id ? "Edit account" : "New account"}
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn primary" onClick={save} disabled={busy}>
                {busy ? "Saving..." : "Save"}
              </button>
            </>
          }
        >
          {error && <Alert kind="error">{error}</Alert>}
          <Field label="Full name" error={fieldErr.full_name?.[0]}>
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <Field label="Email" error={fieldErr.email?.[0]} hint={editing.id ? "Email cannot be changed." : "Used to sign in."}>
            <input
              type="email"
              value={form.email}
              disabled={!!editing.id}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label="Role" error={fieldErr.role?.[0]} hint="Determines data visibility across the whole app.">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="EMPLOYEE">Employee - self service only</option>
              <option value="MANAGER">Manager - own department</option>
              <option value="HR">HR officer - all employees</option>
              <option value="ADMIN">Administrator - full control</option>
            </select>
          </Field>
          <Field label="Job title">
            <input value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />
          </Field>
          <Field label="Phone">
            <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          {!editing.id && (
            <Field label="Initial password" error={fieldErr.password?.[0]} hint="At least 8 characters. The user should change it after signing in.">
              <input
                type="text"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="e.g. Welcome@2026"
              />
            </Field>
          )}
        </Modal>
      )}

      {resetting && (
        <Modal
          title={`Reset password for ${resetting.full_name}`}
          onClose={() => setResetting(null)}
          footer={
            <>
              <button className="btn" onClick={() => setResetting(null)}>Cancel</button>
              <button className="btn primary" onClick={resetPassword} disabled={busy || newPassword.length < 8}>
                {busy ? "Saving..." : "Reset password"}
              </button>
            </>
          }
        >
          <Field label="New password" hint="They will be asked to change it on next sign-in.">
            <input type="text" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="At least 8 characters" />
          </Field>
        </Modal>
      )}
    </div>
  );
}
