import { useState } from "react";
import api from "../api";
import { Alert, Empty, Spinner, fmtDateTime, timeAgo, useLive } from "../components/ui";

const ACTION_TONE = {
  CREATE: "green", UPDATE: "blue", DELETE: "red", APPROVE: "green",
  REJECT: "red", CHECK_IN: "violet", CHECK_OUT: "violet", LOGIN: "grey", LOGOUT: "grey",
};

export default function Activity() {
  const [action, setAction] = useState("");

  const { data, error, loading } = useLive(async () => {
    const params = { limit: 100 };
    if (action) params.action = action;
    const { data } = await api.get("/activity/", { params });
    return data.results || data;
  }, [action], 8000);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Activity</h1>
          <div className="sub">
            Every create, update, approval and sign-in, recorded for the whole organisation.
          </div>
        </div>
        <div className="page-head-actions">
          <select value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 170 }}>
            <option value="">All actions</option>
            {Object.keys(ACTION_TONE).map((a) => (
              <option key={a} value={a}>{a.replace("_", " ").toLowerCase()}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <div className="card">
        {loading && !data ? (
          <Spinner block />
        ) : !data?.length ? (
          <Empty icon="clock" title="Nothing recorded yet" />
        ) : (
          <div className="card-body">
            <div className="timeline">
              {data.map((row) => (
                <div className="tl-item" key={row.id}>
                  <div
                    className="tl-dot"
                    style={{
                      background: `var(--${ACTION_TONE[row.action] || "grey"}-soft)`,
                      color: `var(--${ACTION_TONE[row.action] || "grey"})`,
                    }}
                  >
                    {row.actor_name?.[0] || "?"}
                  </div>
                  <div className="tl-body">
                    <div className="tl-text">{row.summary}</div>
                    <div className="tl-meta">
                      {row.actor_name}
                      {row.actor_role ? ` (${row.actor_role.toLowerCase()})` : ""} ·{" "}
                      <strong style={{ fontWeight: 600 }}>{row.action_label}</strong> · {timeAgo(row.created_at)} ·{" "}
                      {fmtDateTime(row.created_at)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
