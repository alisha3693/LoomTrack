import { ReactNode, useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Status, STATUS_LABEL } from "../lib/format";

export function StatusPill({ status, label }: { status: Status; label?: string }) {
  return (
    <span className={`pill pill-${status}`}>
      <span className={`dot dot-${status}`} />
      {label ?? STATUS_LABEL[status]}
    </span>
  );
}

export function Progress({ pct, tone }: { pct: number; tone?: Status | "" }) {
  return (
    <div className={`progress ${tone ?? ""}`} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
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

/** Small colour chip. Hex on a screen is approximate; the Pantone reference is the real spec. */
export function Swatch({ hex }: { hex?: string | null }) {
  if (!hex) return null;
  return <span className="swatch" style={{ background: hex }} title={`${hex} (approximate on screen)`} />;
}
