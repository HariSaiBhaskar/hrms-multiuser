import { useState } from "react";
import api, { errorMessage, fieldErrors } from "../api";
import { useAuth } from "../auth";
import {
  Alert, Badge, Empty, Field, Modal, Pagination, Spinner, fmtDate, fmtTime, monthISO,
  todayISO, useLive, useToast,
} from "../components/ui";

export default function Attendance() {
  const { can, user } = useAuth();
  const toast = useToast();

  const [tab, setTab] = useState("mine");
  const [month, setMonth] = useState(monthISO());
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);
  const [marking, setMarking] = useState(false);
  const [markForm, setMarkForm] = useState({ date: todayISO(), employee_ids: [], status: "PRESENT" });
  const [markErr, setMarkErr] = useState("");
  const [busy, setBusy] = useState(false);

  // --- my own status -----------------------------------------------------
  const mine = useLive(async () => {
    const { data } = await api.get("/attendance/today/");
    return data;
  }, []);

  const myRecords = useLive(async () => {
    const { data } = await api.get("/attendance/", { params: { month, page, mine: "true" } });
    return data;
  }, [month, page]);

  const team = useLive(async () => {
    if (!can.managePeople && !can.manager) return null;
    const params = { month, page };
    if (department) params.department = department;
    const { data } = await api.get("/attendance/", { params });
    return data;
  }, [month, page, department, can.managePeople, can.manager]);

  const lookup = useLive(async () => {
    if (!can.managePeople) return [];
    const { data } = await api.get("/employees/lookup/");
    return data;
  }, [can.managePeople]);

  const checkIn = async () => {
    setBusy(true);
    try {
      await api.post("/attendance/check-in/");
      toast.show("Checked in. Have a good day.");
      mine.reload();
    } catch (err) {
      toast.show(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const checkOut = async () => {
    setBusy(true);
    try {
      await api.post("/attendance/check-out/");
      toast.show("Checked out. See you tomorrow.");
      mine.reload();
    } catch (err) {
      toast.show(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const submitMark = async () => {
    setBusy(true);
    setMarkErr("");
    try {
      const { data } = await api.post("/attendance/mark/", markForm);
      toast.show(`${data.updated} record(s) updated.`);
      setMarking(false);
      setMarkForm({ date: todayISO(), employee_ids: [], status: "PRESENT" });
    } catch (err) {
      setMarkErr(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const record = mine.data?.record;
  const rows = (tab === "mine" ? myRecords.data : team.data)?.results || [];
  const count = (tab === "mine" ? myRecords.data : team.data)?.count || 0;
  const people = lookup.data || [];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Attendance</h1>
          <div className="sub">Check in and out, and review records across the month.</div>
        </div>
        <div className="page-head-actions">
          {can.managePeople && (
            <button className="btn" onClick={() => setMarking(true)}>Mark attendance</button>
          )}
        </div>
      </div>

      {toast.node}

      {/* ---- self service card ---- */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body">
          <div className="inline wrap" style={{ gap: 18 }}>
            <div>
              <div className="stat-label">Today</div>
              <div style={{ fontSize: 19, fontWeight: 700 }}>
                {fmtDate(todayISO())}
              </div>
              <div className="faint">
                {mine.data?.employee
                  ? `${mine.data.employee.full_name} · ${mine.data.employee.department || "no department"}`
                  : "No employee profile linked to your account"}
              </div>
            </div>

            <div style={{ marginLeft: "auto" }} className="inline wrap" >
              <div className="stack" style={{ gap: 2, minWidth: 120 }}>
                <span className="faint">Check in</span>
                <strong className="mono" style={{ fontSize: 17 }}>
                  {record?.check_in ? fmtTime(record.check_in) : "--:--"}
                </strong>
              </div>
              <div className="stack" style={{ gap: 2, minWidth: 120 }}>
                <span className="faint">Check out</span>
                <strong className="mono" style={{ fontSize: 17 }}>
                  {record?.check_out ? fmtTime(record.check_out) : "--:--"}
                </strong>
              </div>
              <div className="stack" style={{ gap: 2, minWidth: 100 }}>
                <span className="faint">Status</span>
                <span>
                  {record ? <Badge value={record.status} /> : <span className="badge grey">Not marked</span>}
                </span>
              </div>
              {record?.is_late && <Badge value="PENDING" label="Late" tone="amber" />}

              <div className="inline" style={{ gap: 8 }}>
                {!record?.check_in && (
                  <button className="btn primary" onClick={checkIn} disabled={busy || !mine.data?.employee}>
                    Check in
                  </button>
                )}
                {record?.check_in && !record?.check_out && (
                  <button className="btn success" onClick={checkOut} disabled={busy}>
                    Check out
                  </button>
                )}
                {record?.check_in && record?.check_out && (
                  <span className="live-pill">Day complete</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ---- records ---- */}
      <div className="card">
        <div className="card-head">
          <div className="inline" style={{ gap: 4 }}>
            <button className={`btn ghost sm ${tab === "mine" ? "primary" : ""}`} onClick={() => { setTab("mine"); setPage(1); }}>
              My records
            </button>
            {(can.managePeople || can.manager) && (
              <button className={`btn ghost sm ${tab === "team" ? "primary" : ""}`} onClick={() => { setTab("team"); setPage(1); }}>
                {can.managePeople ? "All employees" : "My team"}
              </button>
            )}
          </div>
          <div className="card-head-actions">
            {tab === "team" && can.managePeople && (
              <select value={department} onChange={(e) => { setDepartment(e.target.value); setPage(1); }} style={{ width: 170 }}>
                <option value="">All departments</option>
                {[...new Set(people.map((p) => p.department).filter(Boolean))].map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            )}
            <input type="month" value={month} onChange={(e) => { setMonth(e.target.value); setPage(1); }} style={{ width: 155 }} />
          </div>
        </div>

        {(myRecords.error || team.error) && (
          <div className="card-body"><Alert kind="error">{myRecords.error || team.error}</Alert></div>
        )}

        {(tab === "mine" ? myRecords.loading : team.loading) && !rows.length ? (
          <Spinner block />
        ) : rows.length === 0 ? (
          <Empty icon="clock" title="No attendance records">
            {tab === "mine" ? "Check in to create today's record." : "Nothing recorded for this month yet."}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {tab === "team" && <th>Employee</th>}
                    <th>Date</th>
                    <th>Status</th>
                    <th>In</th>
                    <th>Out</th>
                    <th className="num">Hours</th>
                    <th>Marked by</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      {tab === "team" && (
                        <td>
                          <div className="cell-main">{r.employee_name}</div>
                          <div className="cell-sub">{r.employee_code} · {r.department || "-"}</div>
                        </td>
                      )}
                      <td className="mono">
                        {fmtDate(r.date)}
                        {r.is_late && <span className="badge amber" style={{ marginLeft: 8 }}>Late</span>}
                      </td>
                      <td><Badge value={r.status} /></td>
                      <td className="mono">{r.check_in ? fmtTime(r.check_in) : "-"}</td>
                      <td className="mono">{r.check_out ? fmtTime(r.check_out) : "-"}</td>
                      <td className="num mono">
                        {r.worked_minutes != null ? (r.worked_minutes / 60).toFixed(1) : "-"}
                      </td>
                      <td className="faint">{r.marked_by_name || "System"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={count} onChange={setPage} />
          </>
        )}
      </div>

      {marking && (
        <Modal
          title="Mark attendance"
          onClose={() => setMarking(false)}
          footer={
            <>
              <button className="btn" onClick={() => setMarking(false)}>Cancel</button>
              <button
                className="btn primary"
                onClick={submitMark}
                disabled={busy || markForm.employee_ids.length === 0}
              >
                {busy ? "Saving..." : `Mark ${markForm.employee_ids.length} employee(s)`}
              </button>
            </>
          }
        >
          {markErr && <Alert kind="error">{markErr}</Alert>}
          <div className="grid two" style={{ gap: 0 }}>
            <Field label="Date">
              <input
                type="date"
                max={todayISO()}
                value={markForm.date}
                onChange={(e) => setMarkForm({ ...markForm, date: e.target.value })}
              />
            </Field>
            <Field label="Status">
              <select
                value={markForm.status}
                onChange={(e) => setMarkForm({ ...markForm, status: e.target.value })}
              >
                <option value="PRESENT">Present</option>
                <option value="WFH">Work from home</option>
                <option value="LEAVE">On leave</option>
                <option value="HALF_DAY">Half day</option>
                <option value="ABSENT">Absent</option>
              </select>
            </Field>
          </div>

          <Field label="Employees" hint="Existing records for that date are overwritten.">
            <div
              style={{
                border: "1px solid var(--border)", borderRadius: 8, maxHeight: 240,
                overflowY: "auto", padding: 6,
              }}
            >
              <label
                className="inline"
                style={{ padding: "6px 8px", fontWeight: 600, fontSize: 12.5, cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={markForm.employee_ids.length === people.length && people.length > 0}
                  onChange={(e) =>
                    setMarkForm({
                      ...markForm,
                      employee_ids: e.target.checked ? people.map((p) => p.id) : [],
                    })
                  }
                />
                Select all ({people.length})
              </label>
              {people.map((p) => (
                <label
                  key={p.id}
                  className="inline"
                  style={{ padding: "6px 8px", fontSize: 13, cursor: "pointer" }}
                >
                  <input
                    type="checkbox"
                    style={{ width: "auto" }}
                    checked={markForm.employee_ids.includes(p.id)}
                    onChange={(e) =>
                      setMarkForm({
                        ...markForm,
                        employee_ids: e.target.checked
                          ? [...markForm.employee_ids, p.id]
                          : markForm.employee_ids.filter((id) => id !== p.id),
                      })
                    }
                  />
                  {p.full_name} <span className="faint">· {p.department || "-"}</span>
                </label>
              ))}
            </div>
          </Field>
        </Modal>
      )}
    </div>
  );
}
