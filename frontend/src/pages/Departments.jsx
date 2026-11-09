import { useState } from "react";
import api, { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Empty, Field, Modal, Spinner, useLive, useToast } from "../components/ui";

const BLANK = { name: "", code: "", description: "", head: "" };

export default function Departments() {
  const { can } = useAuth();
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [people, setPeople] = useState([]);

  const { data, error: loadError, loading } = useLive(async () => {
    const { data } = await api.get("/departments/");
    return data.results || data;
  }, []);

  const open = async (dept) => {
    setForm(dept ? { ...BLANK, ...dept, head: dept.head || "" } : BLANK);
    setError("");
    setEditing(dept || { mode: "create" });
    if (can.managePeople) {
      const { data } = await api.get("/employees/lookup/");
      setPeople(data);
    }
  };

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const payload = { ...form, head: form.head || null };
      if (editing.id) await api.patch(`/departments/${editing.id}/`, payload);
      else await api.post("/departments/", payload);
      toast.show(editing.id ? "Department updated." : "Department created.");
      setEditing(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (dept) => {
    if (!window.confirm(`Delete ${dept.name}? Employees stay, but become unassigned.`)) return;
    try {
      await api.delete(`/departments/${dept.id}/`);
      toast.show("Department deleted.");
    } catch (err) {
      toast.show(errorMessage(err), "error");
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Departments</h1>
          <div className="sub">Teams across the organisation and their heads.</div>
        </div>
        {can.managePeople && (
          <div className="page-head-actions">
            <button className="btn primary" onClick={() => open(null)}>+ New department</button>
          </div>
        )}
      </div>

      {toast.node}
      {loadError && <Alert kind="error">{loadError}</Alert>}

      {loading && !data ? (
        <Spinner block />
      ) : !data?.length ? (
        <div className="card"><Empty icon="building" title="No departments yet" /></div>
      ) : (
        <div className="grid cards">
          {data.map((d) => (
            <div className="card" key={d.id}>
              <div className="card-body">
                <div className="inline" style={{ justifyContent: "space-between" }}>
                  <div>
                    <h3>{d.name}</h3>
                    <div className="faint">{d.code}</div>
                  </div>
                  <div className="stat-icon" style={{ background: "var(--brand-soft)", color: "var(--brand)", margin: 0 }}>
                    {d.headcount}
                  </div>
                </div>
                <p className="muted" style={{ fontSize: 12.5, marginTop: 10, minHeight: 34 }}>
                  {d.description || "No description."}
                </p>
                <div className="divider" />
                <div className="inline" style={{ justifyContent: "space-between" }}>
                  <div className="faint">
                    Head: <strong style={{ color: "var(--text)" }}>{d.head_name || "unassigned"}</strong>
                  </div>
                  {can.managePeople && (
                    <div className="inline" style={{ gap: 6 }}>
                      <button className="btn ghost sm" onClick={() => open(d)}>Edit</button>
                      <button className="btn ghost sm" onClick={() => remove(d)}>Delete</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? "Edit department" : "New department"}
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
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="Code" hint="Short unique code, e.g. ENG">
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          </Field>
          <Field label="Description">
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="Department head">
            <select value={form.head} onChange={(e) => setForm({ ...form, head: e.target.value })}>
              <option value="">Unassigned</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name}</option>
              ))}
            </select>
          </Field>
        </Modal>
      )}
    </div>
  );
}
