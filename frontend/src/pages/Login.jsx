import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Alert, Field, Spinner } from "../components/ui";
import { errorMessage } from "../api";

const DEMO = [
  { role: "Admin", email: "admin@acme.test", note: "everything + user accounts" },
  { role: "HR", email: "hr@acme.test", note: "all employees, approvals" },
  { role: "Manager", email: "manager@acme.test", note: "own department only" },
  { role: "Employee", email: "employee@acme.test", note: "self-service only" },
];
const DEMO_PASSWORD = "Passw0rd!";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || "/"} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(
        err?.response?.status === 401
          ? "Email or password is incorrect."
          : errorMessage(err)
      );
    } finally {
      setBusy(false);
    }
  };

  const useDemo = (demoEmail) => {
    setEmail(demoEmail);
    setPassword(DEMO_PASSWORD);
    setError("");
  };

  return (
    <div className="login-wrap">
      <div className="login-art">
        <div>
          <div className="inline" style={{ gap: 10, marginBottom: 34 }}>
            <div className="brand-mark">H</div>
            <strong style={{ fontSize: 15 }}>HRMS</strong>
          </div>
          <h1>One workspace, one shared source of truth.</h1>
          <p style={{ marginTop: 16 }}>
            Every employee, attendance mark and leave approval lives in a single
            database. What HR changes, the whole team sees - instantly.
          </p>
          <div className="feature-list">
            {[
              "Role-based access: admin, HR, manager and employee",
              "Self-service check-in, leave requests and balances",
              "Live team directory and attendance reporting",
              "Full audit trail of who changed what",
            ].map((text) => (
              <div className="feature" key={text}>
                <span className="dot">✓</span>
                <span>{text}</span>
              </div>
            ))}
          </div>
        </div>
        <p style={{ fontSize: 12.5, color: "#8e96c4" }}>
          Django REST Framework · MySQL · React
        </p>
      </div>

      <div className="login-form-side">
        <div className="login-card">
          <h2>Sign in</h2>
          <p className="sub">Use your work email address.</p>

          {error && <Alert kind="error">{error}</Alert>}

          <form onSubmit={submit}>
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="username"
                required
                autoFocus
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </Field>
            <button className="btn primary block" type="submit" disabled={busy}>
              {busy ? <Spinner /> : null}
              {busy ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="demo-accounts">
            <div className="title">Demo accounts · password {DEMO_PASSWORD}</div>
            <div className="demo-grid">
              {DEMO.map((d) => (
                <button type="button" className="demo-btn" key={d.email} onClick={() => useDemo(d.email)}>
                  <strong>{d.role}</strong>
                  {d.note}
                </button>
              ))}
            </div>
            <p className="faint" style={{ marginTop: 10 }}>
              Run <code>python manage.py seed_demo</code> to create these accounts.
              Open two browsers, sign in as two different people, and watch changes
              appear on both.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
