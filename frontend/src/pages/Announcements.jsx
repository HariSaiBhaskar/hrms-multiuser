import { useState } from "react";
import api, { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Empty, Field, Modal, Spinner, fmtDateTime, useLive, useToast } from "../components/ui";

export default function Announcements() {
  const { can, user } = useAuth();
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title: "", body: "", is_pinned: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data, error: loadError, loading } = useLive(async () => {
    const { data } = await api.get("/announcements/");
    return data.results || data;
  }, []);

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      if (editing.id) await api.patch(`/announcements/${editing.id}/`, form);
      else await api.post("/announcements/", form);
      toast.show(editing.id ? "Announcement updated." : "Announcement posted to everyone.");
      setEditing(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`Delete "${item.title}"?`)) return;
    try {
      await api.delete(`/announcements/${item.id}/`);
      toast.show("Announcement deleted.");
    } catch (err) {
      toast.show(errorMessage(err), "error");
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Announcements</h1>
          <div className="sub">One board, read by every user in the workspace.</div>
        </div>
        {can.managePeople && (
          <div className="page-head-actions">
            <button className="btn primary" onClick={() => { setForm({ title: "", body: "", is_pinned: false }); setError(""); setEditing({ mode: "create" }); }}>
              + New announcement
            </button>
          </div>
        )}
      </div>

      {toast.node}
      {loadError && <Alert kind="error">{loadError}</Alert>}

      {loading && !data ? (
        <Spinner block />
      ) : !data?.length ? (
        <div className="card"><Empty icon="megaphone" title="No announcements yet" /></div>
      ) : (
        <div className="stack" style={{ gap: 14 }}>
          {data.map((a) => (
            <div className="card" key={a.id}>
              <div className="card-body">
                <div className="inline wrap" style={{ gap: 10 }}>
                  {a.is_pinned && <span className="badge amber dot">Pinned</span>}
                  <h2>{a.title}</h2>
                  <span style={{ flex: 1 }} />
                  {can.managePeople && (
                    <div className="inline" style={{ gap: 6 }}>
                      <button className="btn ghost sm" onClick={() => { setForm({ title: a.title, body: a.body, is_pinned: a.is_pinned }); setError(""); setEditing(a); }}>
                        Edit
                      </button>
                      <button className="btn ghost sm" onClick={() => remove(a)}>Delete</button>
                    </div>
                  )}
                </div>
                <p className="muted" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{a.body}</p>
                <div className="faint" style={{ marginTop: 10 }}>
                  {a.author_name} · {a.author_role ? a.author_role.toLowerCase() : ""} · {fmtDateTime(a.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? "Edit announcement" : "New announcement"}
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn primary" onClick={save} disabled={busy}>
                {busy ? "Saving..." : editing.id ? "Save changes" : "Post"}
              </button>
            </>
          }
        >
          {error && <Alert kind="error">{error}</Alert>}
          <Field label="Title">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={140} />
          </Field>
          <Field label="Message">
            <textarea style={{ minHeight: 130 }} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          </Field>
          <label className="inline" style={{ fontSize: 13, cursor: "pointer" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={form.is_pinned}
              onChange={(e) => setForm({ ...form, is_pinned: e.target.checked })}
            />
            Pin to the top
          </label>
        </Modal>
      )}
    </div>
  );
}
