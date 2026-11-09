import { useEffect, useRef, useState } from "react";

/* Inline SVG icon set - no emoji, no icon-font, no network request. */
const ICON_PATHS = {
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  chart: "M3 3v18h18M7 16v-5M12 16V8M17 16v-9",
  building: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6",
  megaphone: "M3 11l18-7v16L3 13v-2zM3 11v4a2 2 0 0 0 2 2h1",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  check: "M20 6L9 17l-5-5",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
  home: "M3 10l9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
};

export function Icon({ name, size = 16 }) {
  const path = ICON_PATHS[name];
  if (!path) return <span>{name}</span>;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

export function Spinner({ block = false }) {
  const el = <div className="spinner" />;
  return block ? <div className="loading-block">{el}</div> : el;
}

export function Alert({ kind = "error", children, onClose }) {
  if (!children) return null;
  return (
    <div className={`alert ${kind}`}>
      <span style={{ flex: 1 }}>{children}</span>
      {onClose && (
        <button className="btn ghost sm" onClick={onClose} aria-label="Dismiss">
          x
        </button>
      )}
    </div>
  );
}

const BADGE_MAP = {
  PRESENT: "green",
  WFH: "blue",
  LEAVE: "violet",
  HALF_DAY: "amber",
  ABSENT: "red",
  APPROVED: "green",
  PENDING: "amber",
  REJECTED: "red",
  CANCELLED: "grey",
  ACTIVE: "green",
  ON_LEAVE: "violet",
  RESIGNED: "grey",
  ADMIN: "violet",
  HR: "blue",
  MANAGER: "amber",
  EMPLOYEE: "grey",
};

export function Badge({ value, label, tone }) {
  const cls = tone || BADGE_MAP[value] || "grey";
  return <span className={`badge ${cls} dot`}>{label || prettify(value)}</span>;
}

export function prettify(value) {
  if (!value) return "";
  return String(value)
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function Modal({ title, children, onClose, footer, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn ghost sm close" onClick={onClose} aria-label="Close">
            x
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({ label, hint, error, children }) {
  return (
    <div className="field">
      {label && <label>{label}</label>}
      {children}
      {hint && !error && <span className="hint">{hint}</span>}
      {error && <span className="err">{error}</span>}
    </div>
  );
}

export function Empty({ icon = "inbox", title, children }) {
  return (
    <div className="empty">
      <div className="big">
        <Icon name={icon} size={30} />
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Stat({ label, value, hint, icon, tone = "blue" }) {
  return (
    <div className="card stat">
      <div className="stat-row">
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value">{value}</div>
          {hint && <div className="stat-hint">{hint}</div>}
        </div>
        {icon && (
          <div className="stat-icon" style={{ background: `var(--${tone}-soft)`, color: `var(--${tone})` }}>
            <Icon name={icon} size={17} />
          </div>
        )}
      </div>
    </div>
  );
}

export function Pagination({ page, count, pageSize = 25, onChange }) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count === 0) return null;
  return (
    <div className="inline" style={{ padding: "12px 16px", borderTop: "1px solid var(--border)" }}>
      <span className="faint">
        {count} record{count === 1 ? "" : "s"} · page {page} of {pages}
      </span>
      <span style={{ flex: 1 }} />
      <button className="btn sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      <button className="btn sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next
      </button>
    </div>
  );
}

/** Auto-dismissing toast. */
export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  const show = (message, kind = "success") => {
    clearTimeout(timer.current);
    setToast({ message, kind });
    timer.current = setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  const node = toast ? <Alert kind={toast.kind}>{toast.message}</Alert> : null;
  return { show, node };
}

/**
 * Re-fetch on an interval and when the tab regains focus.
 * This is what makes one user's change show up for everyone else.
 */
export function useLive(fetcher, deps = [], intervalMs = 10000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;

    const run = async (silent) => {
      if (!silent) setLoading(true);
      try {
        const result = await fetcherRef.current();
        if (!cancelled) {
          setData(result);
          setError("");
          setLastUpdated(new Date());
        }
      } catch (err) {
        if (!cancelled) setError(err?.userMessage || "Could not load data.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run(false);
    const id = setInterval(() => {
      if (document.visibilityState === "visible") run(true);
    }, intervalMs);
    const onFocus = () => run(true);
    window.addEventListener("focus", onFocus);

    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, lastUpdated, reload: () => setLastUpdated(new Date()) };
}

export const fmtDate = (value) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
};

export const fmtTime = (value) => {
  if (!value) return "-";
  const [h, m] = String(value).split(":");
  const d = new Date();
  d.setHours(Number(h), Number(m), 0, 0);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
};

export const fmtDateTime = (value) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const timeAgo = (value) => {
  if (!value) return "";
  const seconds = Math.floor((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(value);
};

export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
};

export const monthISO = () => todayISO().slice(0, 7);
