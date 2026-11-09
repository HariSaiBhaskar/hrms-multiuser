import { useEffect, useState } from "react";
import api, { errorMessage, fieldErrors } from "../api";
import { useAuth } from "../auth";
import {
  Alert, Badge, Empty, Field, Modal, Pagination, Spinner, fmtDate, fmtDateTime,
  todayISO, useLive, useToast,
} from "../components/ui";

const BLANK = { leave_type: "", start_date: todayISO(), end_date: todayISO(), reason: "" };

export default function Leave() {
  const { can } = useAuth();
  const toast = useToast();

  const [tab, setTab] = useState("mine");
  const [page, setPage] = useState(1);
  const [applying, setApplying] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [formErr, setFormErr] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deciding, setDeciding] = useState(null); // { request, action }
  const [note, setNote] = useState("");
  const [types, setTypes] = useState([]);

  useEffect(() => {
    api.get("/leave-types/").then(({ data }) => setTypes(data.results || data)).catch(() => {});
  }, []);

  const balance = useLive(async () => {
    const { data } = await api.get("/leave-requests/balance/");
    return data;
  }, []);

  const mine = useLive(async () => {
    const { data } = await api.get("/leave-requests/", { params: { mine: "true", page } });
    return data;
  }, [page]);

  const approvals = useLive(async () => {
    if (!can.approveLeave) return null;
    const { data } = await api.get("/leave-requests/", {
      params: { pending_my_approval: "true", page },
    });
    return data;
  }, [page, can.approveLeave]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setFormErr({});
    try {
      await api.post("/leave-requests/", form);
      setApplying(false);
      setForm(BLANK);
      toast.show("Leave request submitted for approval.");
      mine.reload();
      balance.reload();
    } catch (err) {
      setFormErr(fieldErrors(err));
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const decide = async () => {
    const { request, action } = deciding;
    setBusy(true);
    try {
      await api.post(`/leave-requests/${request.id}/${action}/`, { note });
      toast.show(`Request ${action === "approve" ? "approved" : "rejected"}.`);
      setDeciding(null);
      setNote("");
      approvals.reload();
      mine.reload();
    } catch (err) {
      toast.show(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (request) => {
    try {
      await api.post(`/leave-requests/${request.id}/cancel/`);
      toast.show("Request cancelled.");
      mine.reload();
      balance.reload();
    } catch (err) {
      toast.show(errorMessage(err), "error");
    }
  };

  const rows = (tab === "mine" ? mine.data : approvals.data)?.results || [];
  const count = (tab === "mine" ? mine.data : approvals.data)?.count || 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Leave</h1>
          <div className="sub">
            Request time off, track balances, and approve your team's requests.
          </div>
        </div>
        <div className="page-head-actions">
          <button className="btn primary" onClick={() => { setForm(BLANK); setFormErr({}); setError(""); setApplying(true); }}>
            + Request leave
          </button>
        </div>
      </div>

      {toast.node}

      {/* balance cards */}
      <div className="grid cards" style={{ marginBottom: 16 }}>
        {(balance.data || []).map((b) => (
          <div className="card stat" key={b.leave_type}>
            <div className="stat-label">{b.name}</div>
            <div className="stat-value">
              {b.unlimited ? "∞" : b.remaining}
              <small>{b.unlimited ? " unlimited" : ` / ${b.quota}`}</small>
            </div>
            <div className="stat-hint">
              {b.used} used{b.pending > 0 ? ` · ${b.pending} pending` : ""}
            </div>
            {!b.unlimited && (
              <div className="progress" style={{ marginTop: 8 }}>
                <span style={{ width: `${Math.min(100, (b.used / Math.max(b.quota, 1)) * 100)}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-head">
          <div className="inline" style={{ gap: 4 }}>
            <button className={`btn ghost sm ${tab === "mine" ? "primary" : ""}`} onClick={() => { setTab("mine"); setPage(1); }}>
              My requests
            </button>
            {can.approveLeave && (
              <button className={`btn ghost sm ${tab === "approvals" ? "primary" : ""}`} onClick={() => { setTab("approvals"); setPage(1); }}>
                Awaiting my approval
                {approvals.data?.count > 0 && <span className="nav-badge">{approvals.data.count}</span>}
              </button>
            )}
          </div>
        </div>

        {(mine.error || approvals.error) && (
          <div className="card-body"><Alert kind="error">{mine.error || approvals.error}</Alert></div>
        )}

        {(tab === "mine" ? mine.loading : approvals.loading) && !rows.length ? (
          <Spinner block />
        ) : rows.length === 0 ? (
          <Empty icon="calendar" title={tab === "mine" ? "No leave requests yet" : "Nothing to approve"}>
            {tab === "mine"
              ? "Submit a request and it will appear here with its status."
              : "Requests from your team will show up here."}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {tab === "approvals" && <th>Employee</th>}
                    <th>Type</th>
                    <th>Dates</th>
                    <th className="num">Days</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th className="right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      {tab === "approvals" && (
                        <td>
                          <div className="cell-main">{r.employee_name}</div>
                          <div className="cell-sub">{r.department || "-"}</div>
                        </td>
                      )}
                      <td>{r.leave_type_name}</td>
                      <td className="mono">
                        {fmtDate(r.start_date)}
                        {r.end_date !== r.start_date && ` → ${fmtDate(r.end_date)}`}
                      </td>
                      <td className="num mono">{r.days}</td>
                      <td style={{ maxWidth: 240 }}>
                        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {r.reason}
                        </div>
                        {r.decided_by_name && (
                          <div className="cell-sub">
                            {r.status === "APPROVED" ? "Approved" : "Decided"} by {r.decided_by_name}
                            {r.decided_at ? ` · ${fmtDateTime(r.decided_at)}` : ""}
                            {r.decision_note ? ` · "${r.decision_note}"` : ""}
                          </div>
                        )}
                      </td>
                      <td><Badge value={r.status} /></td>
                      <td>
                        <div className="row-actions">
                          {r.can_decide && (
                            <>
                              <button className="btn sm success" onClick={() => { setDeciding({ request: r, action: "approve" }); setNote(""); }}>
                                Approve
                              </button>
                              <button className="btn sm danger" onClick={() => { setDeciding({ request: r, action: "reject" }); setNote(""); }}>
                                Reject
                              </button>
                            </>
                          )}
                          {r.can_cancel && (
                            <button className="btn sm" onClick={() => cancel(r)}>Cancel</button>
                          )}
                          {!r.can_decide && !r.can_cancel && <span className="faint">-</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={count} onChange={setPage} />
          </>
        )}
      </div>

      {applying && (
        <Modal
          title="Request leave"
          onClose={() => setApplying(false)}
          footer={
            <>
              <button className="btn" onClick={() => setApplying(false)}>Cancel</button>
              <button className="btn primary" onClick={submit} disabled={busy}>
                {busy ? "Submitting..." : "Submit request"}
              </button>
            </>
          }
        >
          <form onSubmit={submit}>
            {error && <Alert kind="error">{error}</Alert>}
            <Field label="Leave type" error={formErr.leave_type?.[0]}>
              <select
                className={formErr.leave_type ? "invalid" : ""}
                value={form.leave_type}
                onChange={(e) => setForm({ ...form, leave_type: e.target.value })}
                required
              >
                <option value="">Select a type...</option>
                {types.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} {t.annual_quota ? `(${t.annual_quota} days/year)` : "(unlimited)"}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid two" style={{ gap: 0 }}>
              <Field label="From" error={formErr.start_date?.[0]}>
                <input
                  type="date"
                  className={formErr.start_date ? "invalid" : ""}
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value, end_date: form.end_date < e.target.value ? e.target.value : form.end_date })}
                  required
                />
              </Field>
              <Field label="To" error={formErr.end_date?.[0]}>
                <input
                  type="date"
                  className={formErr.end_date ? "invalid" : ""}
                  min={form.start_date}
                  value={form.end_date}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                  required
                />
              </Field>
            </div>
            <Field label="Reason" hint="Weekends are excluded from the day count." error={formErr.reason?.[0]}>
              <textarea
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Why do you need this leave?"
                required
              />
            </Field>
          </form>
        </Modal>
      )}

      {deciding && (
        <Modal
          title={deciding.action === "approve" ? "Approve request" : "Reject request"}
          onClose={() => setDeciding(null)}
          footer={
            <>
              <button className="btn" onClick={() => setDeciding(null)}>Cancel</button>
              <button
                className={`btn ${deciding.action === "approve" ? "success" : "danger"}`}
                onClick={decide}
                disabled={busy}
              >
                {busy ? "Saving..." : deciding.action === "approve" ? "Approve" : "Reject"}
              </button>
            </>
          }
        >
          <p>
            <strong>{deciding.request.employee_name}</strong> · {deciding.request.leave_type_name} ·{" "}
            {deciding.request.days} day(s)
          </p>
          <p className="muted">
            {fmtDate(deciding.request.start_date)} → {fmtDate(deciding.request.end_date)}
          </p>
          <p className="faint">{deciding.request.reason}</p>
          <Field label="Note (optional)">
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. approved, enjoy!" />
          </Field>
          {deciding.action === "approve" && (
            <Alert kind="info">
              Approving also marks those working days as leave in the attendance table.
            </Alert>
          )}
        </Modal>
      )}
    </div>
  );
}
