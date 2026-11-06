import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { ThemeToggle } from "../../lib/theme";
import { useApi } from "../../components/ui";
import SearchPalette from "../../components/SearchPalette";
import type { Meta } from "../../lib/types";

const MetaCtx = createContext<Meta | null>(null);
/** Buyers, units, templates, reason list and AI status — loaded once for all office screens. */
export const useMeta = () => useContext(MetaCtx);
const ReloadCtx = createContext<() => void>(() => {});
/** Call after saving something that appears in the shared lists (a new template, for example). */
export const useReloadMeta = () => useContext(ReloadCtx);

/** A "Set up" dropdown for the things you change rarely, so the bar keeps to the daily work. */
function SetupMenu() {
  const ref = useRef<HTMLDetailsElement>(null);
  const { pathname } = useLocation();
  useEffect(() => ref.current?.removeAttribute("open"), [pathname]);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && ref.current.removeAttribute("open");
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const here = ["/m/templates", "/m/units"].some((p) => pathname.startsWith(p));
  return (
    <details className="menu" ref={ref}>
      <summary style={here ? { color: "var(--ink)", fontWeight: 500 } : undefined}>Set up</summary>
      <div className="menu-list">
        <NavLink to="/m/templates">Plan templates<small>Stages and timings for each kind of garment</small></NavLink>
        <NavLink to="/m/units">Units and capacity<small>How many pieces each unit can stitch</small></NavLink>
      </div>
    </details>
  );
}

export default function OfficeShell() {
  const { user, signOut } = useAuth();
  const { data: meta, reload } = useApi<Meta>("/api/m/meta");
  const [searching, setSearching] = useState(false);

  // "/" or Ctrl/Cmd+K opens search from anywhere, unless you are typing in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setSearching(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <MetaCtx.Provider value={meta}>
      <ReloadCtx.Provider value={() => void reload()}>
      <div className="shell">
        <header className="topbar">
          <NavLink to="/m" className="brand">
            <img src="/icon.svg" alt="" />
            LoomTrack
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/m" end>Orders</NavLink>
            <NavLink to="/m/requests">Requests{meta && meta.openRequests > 0 ? <span className="badge" title="Waiting for your answer">{meta.openRequests}</span> : null}</NavLink>
            <NavLink to="/m/buyers">Buyers</NavLink>
            <SetupMenu />
          </nav>
          <div className="spacer" />
          <button className="searchbtn no-print" onClick={() => setSearching(true)} aria-label="Search orders, requests and buyers">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="7" cy="7" r="5" /><path d="m11 11 3.5 3.5" strokeLinecap="round" /></svg>
            <span>Search</span>
            <kbd>/</kbd>
          </button>
          <Link to="/m/orders/new" className="btn btn-primary btn-sm">+ New order</Link>
          {meta && (
            <span
              className="pill"
              title={meta.ai.mode === "ollama" ? `Notes are translated by ${meta.ai.model}, running locally` : meta.ai.reason}
            >
              <span className={`dot ${meta.ai.mode === "ollama" ? "dot-green" : "dot-amber"}`} />
              {meta.ai.mode === "ollama" ? "AI on" : "AI off"}
            </span>
          )}
          <ThemeToggle />
          <span className="muted small nowrap who-user">{user?.name}</span>
          <button className="btn btn-ghost btn-sm" onClick={signOut}>Sign out</button>
        </header>
        <Outlet />
        {searching && <SearchPalette onClose={() => setSearching(false)} />}
      </div>
      </ReloadCtx.Provider>
    </MetaCtx.Provider>
  );
}
