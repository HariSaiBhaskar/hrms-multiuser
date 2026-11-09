import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Badge, Empty, Icon, Spinner, Stat, timeAgo, useLive } from "../components/ui";

export default function Dashboard() {
  const { user, can } = useAuth();
  const { data, error, loading } = useLive(async () => {
    const { data } = await api.get("/dashboard/");
    return data;
  }, []);

  if (loading && !data) return <div className="page"><Spinner block /></div>;
  if (error) return <div className="page"><Alert kind="error">{error}</Alert></div>;
  if (!data) return null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Hello, {user?.full_name?.split(" ")[0]}</h1>
          <div className="sub">
            {data.role_label} · {data.scope === "org" ? "organisation view" : data.scope === "team" ? "team view" : "personal view"} ·{" "}
            {new Date(data.today).toLocaleDateString(undefined, { weekday: "long", day: "2-digit", month: "long" })}
          </div>
        </div>
        <div className="page-head-actions">
          {data.me && (
            <Link className="btn" to="/attendance">
              Go to attendance
            </Link>
          )}
          <Link className="btn primary" to="/leave">
            Request leave
          </Link>
        </div>
      </div>

      {/* ---- personal cards: shown to everyone ---- */}
      {data.me && (
        <div className="grid cards" style={{ marginBottom: 16 }}>
          <div className="card stat">
            <div className="stat-row">
              <div>
                <div className="stat-label">Today</div>
                <div className="stat-value" style={{ fontSize: 22 }}>
                  {data.me.checked_in ? `${data.me.check_in} - ${data.me.checked_out || "…"}` : data.me.today_status}
                </div>
                <div className="stat-hint">
                  {data.me.checked_in
                    ? data.me.checked_out
                      ? "Day complete"
                      : "Checked in"
                    : "Not checked in yet"}
                </div>
              </div>
              <div className="stat-icon" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><Icon name="clock" size={17} /></div>
            </div>
          </div>

          <Stat
            label="Present this month"
            value={data.me.present_this_month}
            hint={`of ${data.me.working_days_this_month} working days`}
            icon="check"
            tone="green"
          />

          <Stat
            label="Pending my requests"
            value={data.me.pending_my_requests}
            hint="awaiting a decision"
            icon="clock"
            tone="amber"
          />

          <div className="card stat">
            <div className="stat-label" style={{ marginBottom: 10 }}>Leave balance</div>
            <div className="stack" style={{ gap: 7 }}>
              {data.me.leave_balance.slice(0, 3).map((b) => (
                <div key={b.leave_type}>
                  <div className="inline" style={{ justifyContent: "space-between", fontSize: 12 }}>
                    <span className="muted">{b.name}</span>
                    <strong className="mono">
                      {b.unlimited ? "unlimited" : `${b.remaining}/${b.quota}`}
                    </strong>
                  </div>
                  {!b.unlimited && (
                    <div className="progress" style={{ marginTop: 3 }}>
                      <span style={{ width: `${Math.min(100, (b.used / Math.max(b.quota, 1)) * 100)}%` }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ---- organisation cards ---- */}
      {data.org && (
        <>
          <div className="grid cards" style={{ marginBottom: 16 }}>
            <Stat label="Active employees" value={data.org.active_employees} hint={`${data.org.total_employees} records in total`} icon="users" tone="blue" />
            <Stat label="Present today" value={data.org.present_today} hint={`${data.org.not_marked_today} not marked yet`} icon="check" tone="green" />
            <Stat label="On leave today" value={data.org.on_leave_today} hint={`${data.org.absent_today} absent`} icon="home" tone="violet" />
            <Stat label="Pending approvals" value={data.org.pending_leave_requests} hint={`${data.org.departments} departments`} icon="clock" tone="amber" />
          </div>

          {data.department_breakdown?.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head">
                <h2>Headcount by department</h2>
                <div className="card-head-actions">
                  <Link className="btn ghost sm" to="/departments">View departments</Link>
                </div>
              </div>
              <div className="card-body">
                <div className="stack">
                  {data.department_breakdown.map((d) => {
                    const max = Math.max(...data.department_breakdown.map((x) => x.headcount), 1);
                    return (
                      <div key={d.id}>
                        <div className="inline" style={{ justifyContent: "space-between", fontSize: 12.5 }}>
                          <span>
                            <strong>{d.name}</strong>{" "}
                            <span className="faint">{d.code}</span>
                          </span>
                          <span className="mono muted">{d.headcount}</span>
                        </div>
                        <div className="progress" style={{ marginTop: 4 }}>
                          <span style={{ width: `${(d.headcount / max) * 100}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ---- team cards for managers ---- */}
      {data.team && !data.org && (
        <div className="grid cards" style={{ marginBottom: 16 }}>
          <Stat label="Team size" value={data.team.team_size} icon="users" tone="blue" />
          <Stat label="Present today" value={data.team.present_today} icon="check" tone="green" />
          <Stat label="Pending approvals" value={data.team.pending_requests} hint="from your team" icon="clock" tone="amber" />
        </div>
      )}

      <div className="grid two">
        <div className="card">
          <div className="card-head">
            <h2>Recent activity</h2>
            <div className="card-head-actions">
              <Link className="btn ghost sm" to="/activity">See all</Link>
            </div>
          </div>
          <div className="card-body">
            {data.recent_activity.length === 0 ? (
              <Empty icon="clock" title="No activity yet">Changes made by anyone will appear here.</Empty>
            ) : (
              <div className="timeline">
                {data.recent_activity.map((a) => (
                  <div className="tl-item" key={a.id}>
                    <div className="tl-dot">{a.actor_name?.[0] || "?"}</div>
                    <div className="tl-body">
                      <div className="tl-text">{a.summary}</div>
                      <div className="tl-meta">
                        {a.actor_name} · {a.action_label} · {timeAgo(a.created_at)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <h2>Announcements</h2>
              <div className="card-head-actions">
                <Link className="btn ghost sm" to="/announcements">All</Link>
              </div>
            </div>
            <div className="card-body">
              {data.announcements.length === 0 ? (
                <Empty icon="megaphone" title="Nothing announced">
                  {can.managePeople ? "Post the first announcement." : "Company notices appear here."}
                </Empty>
              ) : (
                <div className="stack">
                  {data.announcements.map((a) => (
                    <div key={a.id}>
                      <div className="inline" style={{ gap: 8 }}>
                        {a.is_pinned && <Badge value="PENDING" label="Pinned" tone="amber" />}
                        <strong style={{ fontSize: 13.5 }}>{a.title}</strong>
                      </div>
                      <p className="muted" style={{ margin: "4px 0 2px", fontSize: 12.5 }}>
                        {a.body.length > 140 ? `${a.body.slice(0, 140)}…` : a.body}
                      </p>
                      <div className="faint">{a.author_name} · {timeAgo(a.created_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {data.upcoming_holidays?.length > 0 && (
            <div className="card">
              <div className="card-head"><h2>Upcoming holidays</h2></div>
              <div className="card-body stack" style={{ gap: 8 }}>
                {data.upcoming_holidays.map((h) => (
                  <div className="inline" key={h.id} style={{ justifyContent: "space-between", fontSize: 13 }}>
                    <span>{h.name}</span>
                    <span className="faint">
                      {new Date(h.date).toLocaleDateString(undefined, { day: "2-digit", month: "short" })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
