import { createContext, useContext } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { ThemeToggle } from "../../lib/theme";
import { useApi } from "../../components/ui";
import type { Meta } from "../../lib/types";

const MetaCtx = createContext<Meta | null>(null);
/** Buyers, units, templates, reason list and AI status — loaded once for all office screens. */
export const useMeta = () => useContext(MetaCtx);
const ReloadCtx = createContext<() => void>(() => {});
/** Call after saving something that appears in the shared lists (a new template, for example). */
export const useReloadMeta = () => useContext(ReloadCtx);

export default function OfficeShell() {
  const { user, signOut } = useAuth();
  const { data: meta, reload } = useApi<Meta>("/api/m/meta");

  return (
    <MetaCtx.Provider value={meta}>
      <ReloadCtx.Provider value={() => void reload()}>
      <div className="shell">
        <header className="topbar">
          <NavLink to="/m" className="brand">
            <img src="/icon.svg" alt="" />
            LoomTrack
          </NavLink>
          <nav className="nav">
            <NavLink to="/m" end>Orders</NavLink>
            <NavLink to="/m/requests">Requests{meta && meta.openRequests > 0 ? <span className="badge">{meta.openRequests}</span> : null}</NavLink>
            <NavLink to="/m/orders/new">New order</NavLink>
            <NavLink to="/m/templates">Templates</NavLink>
            <NavLink to="/m/buyers">Buyers &amp; exports</NavLink>
          </nav>
          <div className="spacer" />
          {meta && (
            <span
              className="pill"
              title={meta.ai.mode === "ollama" ? `Notes are translated by ${meta.ai.model}, running locally` : meta.ai.reason}
            >
              <span className={`dot ${meta.ai.mode === "ollama" ? "dot-green" : "dot-amber"}`} />
              {meta.ai.mode === "ollama" ? `AI · ${meta.ai.model}` : "AI off · keywords"}
            </span>
          )}
          <ThemeToggle />
          <span className="muted small nowrap">{user?.name}</span>
          <button className="btn btn-ghost btn-sm" onClick={signOut}>Sign out</button>
        </header>
        <Outlet />
      </div>
      </ReloadCtx.Provider>
    </MetaCtx.Provider>
  );
}
