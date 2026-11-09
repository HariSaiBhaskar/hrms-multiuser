import { useState } from "react";
import api, { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Field, Spinner, useLive } from "../components/ui";

export default function Profile() {
  const { user, reload } = useAuth();
  const [form, setForm] = useState({ full_name: user?.full_name || "", phone: user?.phone || "", job_title: user?.job_title || "" });
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [pwd, setPwd] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwdMsg, setPwdMsg] = useState("");
  const [pwdErr, setPwdErr] = useState("");
  const [pwdBusy, setPwdBusy] = useState(false);

  const me = useLive(async () => {
    const { data } = await api.get("/employees/me/").catch(() => ({ data: null }));
    return data;
  }, []);

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await api.patch("/auth/me/", form);
      await reload();
      setSaved("Profile updated.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    setPwdErr("");
    setPwdMsg("");
    if (pwd.new_password !== pwd.confirm) {
      setPwdErr("The two new passwords do not match.");
      return;
    }
    setPwdBusy(true);
    try {
      await api.post("/auth/change-password/", {
        current_password: pwd.current_password,
        new_password: pwd.new_password,
      });
      setPwdMsg("Password changed.");
      setPwd({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setPwdErr(errorMessage(err));
    } finally {
      setPwdBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>My profile</h1>
          <div className="sub">Your account details and password.</div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="card-head"><h2>Account</h2></div>
          <div className="card-body">
            {saved && <Alert kind="success">{saved}</Alert>}
            {error && <Alert kind="error">{error}</Alert>}
            <form onSubmit={saveProfile}>
              <Field label="Full name">
                <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              </Field>
              <Field label="Email" hint="Ask an administrator to change your sign-in email.">
                <input value={user?.email || ""} disabled />
              </Field>
              <Field label="Role">
                <input value={user?.role_label || ""} disabled />
              </Field>
              <Field label="Job title">
                <input value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />
              </Field>
              <Field label="Phone">
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </Field>
              <button className="btn primary" disabled={busy}>{busy ? "Saving..." : "Save profile"}</button>
            </form>
          </div>
        </div>

        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-head"><h2>Employment record</h2></div>
            <div className="card-body">
              {me.loading && !me.data ? (
                <Spinner block />
              ) : !me.data ? (
                <p className="muted" style={{ margin: 0 }}>
                  No employee record is linked to your account yet. An HR officer can create one.
                </p>
              ) : (
                <dl className="kv">
                  <dt>Employee code</dt><dd>{me.data.employee_code}</dd>
                  <dt>Department</dt><dd>{me.data.department_name || "-"}</dd>
                  <dt>Designation</dt><dd>{me.data.designation || "-"}</dd>
                  <dt>Employment</dt><dd>{me.data.employment_type_label}</dd>
                  <dt>Status</dt><dd>{me.data.status_label}</dd>
                  <dt>Joined</dt><dd>{new Date(me.data.date_of_joining).toLocaleDateString()}</dd>
                  <dt>Reports to</dt><dd>{me.data.manager_name || "-"}</dd>
                </dl>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h2>Change password</h2></div>
            <div className="card-body">
              {pwdMsg && <Alert kind="success">{pwdMsg}</Alert>}
              {pwdErr && <Alert kind="error">{pwdErr}</Alert>}
              <form onSubmit={changePassword}>
                <Field label="Current password">
                  <input type="password" value={pwd.current_password} onChange={(e) => setPwd({ ...pwd, current_password: e.target.value })} required />
                </Field>
                <Field label="New password" hint="At least 8 characters, not entirely numeric.">
                  <input type="password" value={pwd.new_password} onChange={(e) => setPwd({ ...pwd, new_password: e.target.value })} required />
                </Field>
                <Field label="Confirm new password">
                  <input type="password" value={pwd.confirm} onChange={(e) => setPwd({ ...pwd, confirm: e.target.value })} required />
                </Field>
                <button className="btn primary" disabled={pwdBusy}>{pwdBusy ? "Updating..." : "Update password"}</button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
