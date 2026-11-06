import { ReactNode, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Status, STATUS_LABEL } from "../lib/format";

export function StatusPill({ status, label }: { status: Status; label?: string }) {
  return (
    <span className={`pill pill-${status}`}>{label ?? STATUS_LABEL[status]}</span>
  );
}

export function Progress({ pct, tone, label = "Progress" }: { pct: number; tone?: Status | ""; label?: string }) {
  return (
    <div className={`progress ${tone ?? ""}`} role="progressbar" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </div>
  );
}

export function Modal({ title, children, onClose, wide }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? " modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <h2 style={{ marginBottom: 14 }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Toast({ message, onDone }: { message: string | null; onDone: () => void }) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onDone, 3200);
    return () => clearTimeout(t);
  }, [message, onDone]);
  return message ? (
    <div className="toast" role="status">
      {message}
    </div>
  ) : null;
}

/** GET a resource; `reload` refetches without clearing what's on screen. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    if (!path) return Promise.resolve();
    setLoading(true);
    return api<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card card-pad muted" style={{ textAlign: "center", padding: 40 }}>{children}</div>;
}

/** An empty list that says what it is for and what to do about it. */
export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <b>{title}</b>
      {hint && <p className="muted">{hint}</p>}
      {action}
    </div>
  );
}

/** Grey bars where a list will be, so the page does not jump when it arrives. */
export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <span key={i} style={{ width: `${92 - (i % 3) * 14}%` }} />)}
    </div>
  );
}

export interface Crumb { label: string; to?: string }

/** The top of every page: where you are, what this is, and its one or two actions. */
export function PageHeader({ title, sub, crumbs, status, actions }: { title: ReactNode; sub?: ReactNode; crumbs?: Crumb[]; status?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-top">
      {crumbs && crumbs.length > 0 && (
        <nav className="crumbs no-print" aria-label="Breadcrumb">
          {crumbs.map((c, i) => (
            <span key={c.label} className="crumb">
              {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
              {i < crumbs.length - 1 && <i>/</i>}
            </span>
          ))}
        </nav>
      )}
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <div className="row"><h1>{title}</h1>{status}</div>
          {sub && <p className="sub">{sub}</p>}
        </div>
        {actions && <div className="row no-print">{actions}</div>}
      </div>
    </header>
  );
}

/** False for a view-only buyer account, so the page can hide what it would refuse. */
export function useCanWrite(): boolean {
  const { user } = useAuth();
  return user?.can_write !== 0;
}

/** Small colour chip. Hex on a screen is approximate; the Pantone reference is the real spec. */
export function Swatch({ hex }: { hex?: string | null }) {
  if (!hex) return null;
  return <span className="swatch" style={{ background: hex }} title={`${hex} (approximate on screen)`} />;
}
