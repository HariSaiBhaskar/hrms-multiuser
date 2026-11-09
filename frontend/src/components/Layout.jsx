import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../auth";

const ICONS = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  chart: "M3 3v18h18M7 16v-5M12 16V8M17 16v-9",
  building: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6",
  megaphone: "M3 11l18-7v16L3 13v-2zM3 11v4a2 2 0 0 0 2 2h1",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
};

function Icon({ name, size = 17 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICONS[name]} />
    </svg>
  );
}

const initials = (name = "") =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("") || "?";

export default function Layout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [clock, setClock] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const nav = [
    { to: "/", label: "Dashboard", icon: "grid", end: true },
    { to: "/employees", label: can.managePeople ? "Employees" : "People", icon: "users" },
    { to: "/attendance", label: "Attendance", icon: "clock" },
    { to: "/leave", label: "Leave", icon: "calendar" },
    { to: "/reports", label: "Reports", icon: "chart", show: can.managePeople || can.manager },
    { to: "/departments", label: "Departments", icon: "building" },
    { to: "/announcements", label: "Announcements", icon: "megaphone" },
    { to: "/activity", label: "Activity", icon: "activity" },
    { to: "/users", label: "User accounts", icon: "shield", show: can.admin },
  ].filter((item) => item.show !== false);

  const title =
    nav.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))
      ?.label || "Workspace";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">H</div>
          <div>
            <div className="brand-name">HRMS</div>
            <div className="brand-sub">Team workspace</div>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-label">Workspace</div>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            >
              <span className="ico">
                <Icon name={item.icon} />
              </span>
              <span className="label">{item.label}</span>
            </NavLink>
          ))}

          <div className="nav-label">Account</div>
          <NavLink to="/profile" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <span className="ico">
              <Icon name="user" />
            </span>
            <span className="label">My profile</span>
          </NavLink>
          <button className="nav-item" onClick={onLogout}>
            <span className="ico">
              <Icon name="logout" />
            </span>
            <span className="label">Sign out</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="avatar">{initials(user?.full_name)}</div>
            <div style={{ minWidth: 0 }}>
              <div className="user-chip-name">{user?.full_name}</div>
              <div className="user-chip-role">{user?.role_label}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <span className="topbar-title">{title}</span>
          <span className="topbar-spacer" />
          <span className="live-pill" title="Data refreshes automatically every 10 seconds">
            <span className="live-dot" /> Live
          </span>
          <span className="faint mono" style={{ minWidth: 62, textAlign: "right" }}>
            {clock.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
          </span>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
