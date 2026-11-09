import { useState } from "react";
import api, { errorMessage } from "../api";
import { Alert, Empty, Spinner, monthISO, useLive, useToast } from "../components/ui";

export default function Reports() {
  const toast = useToast();
  const [month, setMonth] = useState(monthISO());
  const [department, setDepartment] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [departments, setDepartments] = useState([]);

  const { data, error, loading } = useLive(async () => {
    const params = { month };
    if (department) params.department = department;
    const { data } = await api.get("/attendance/summary/", { params });
    const deps = await api.get("/departments/");
    setDepartments(deps.data.results || deps.data);
    return data;
  }, [month, department]);

  const download = async () => {
    setDownloading(true);
    try {
      const res = await api.get("/reports/attendance.csv", {
        params: { month },
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `attendance-${month}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      toast.show("CSV downloaded - open it in Excel.");
    } catch (err) {
      toast.show(errorMessage(err), "error");
    } finally {
      setDownloading(false);
    }
  };

  const rows = data?.rows || [];
  const totalPresent = rows.reduce((sum, r) => sum + r.present + r.wfh, 0);
  const totalRecorded = rows.reduce((sum, r) => sum + r.total, 0);
  const overall = totalRecorded ? Math.round((totalPresent / totalRecorded) * 1000) / 10 : 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <div className="sub">Monthly attendance summary, computed with SQL aggregates.</div>
        </div>
        <div className="page-head-actions">
          <select value={department} onChange={(e) => setDepartment(e.target.value)} style={{ width: 170 }}>
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 155 }} />
          <button className="btn primary" onClick={download} disabled={downloading}>
            {downloading ? "Preparing..." : "Export CSV"}
          </button>
        </div>
      </div>

      {toast.node}
      {error && <Alert kind="error">{error}</Alert>}

      <div className="grid cards" style={{ marginBottom: 16 }}>
        <div className="card stat">
          <div className="stat-label">Employees tracked</div>
          <div className="stat-value">{rows.length}</div>
        </div>
        <div className="card stat">
          <div className="stat-label">Overall attendance</div>
          <div className="stat-value">{overall}<small>%</small></div>
        </div>
        <div className="card stat">
          <div className="stat-label">Present days recorded</div>
          <div className="stat-value">{totalPresent}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Attendance by employee · {data?.month}</h2>
        </div>
        {loading && !data ? (
          <Spinner block />
        ) : rows.length === 0 ? (
          <Empty icon="chart" title="No data for this month">Mark some attendance first.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th className="num">Present</th>
                  <th className="num">WFH</th>
                  <th className="num">Leave</th>
                  <th className="num">Absent</th>
                  <th className="num">Recorded</th>
                  <th style={{ width: 180 }}>Attendance rate</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.employee_id}>
                    <td>
                      <div className="cell-main">{r.employee_name}</div>
                      <div className="cell-sub">{r.employee_code}</div>
                    </td>
                    <td className="num mono">{r.present}</td>
                    <td className="num mono">{r.wfh}</td>
                    <td className="num mono">{r.leave}</td>
                    <td className="num mono">{r.absent}</td>
                    <td className="num mono">{r.total}</td>
                    <td>
                      <div className="inline" style={{ gap: 8 }}>
                        <div className="progress" style={{ flex: 1 }}>
                          <span
                            style={{
                              width: `${Math.min(100, r.attendance_rate)}%`,
                              background:
                                r.attendance_rate >= 90 ? "var(--green)" :
                                r.attendance_rate >= 75 ? "var(--amber)" : "var(--red)",
                            }}
                          />
                        </div>
                        <span className="mono faint" style={{ width: 42, textAlign: "right" }}>
                          {r.attendance_rate}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
