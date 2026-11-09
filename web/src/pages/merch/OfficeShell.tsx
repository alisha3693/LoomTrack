import { createContext, useContext, useEffect, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import Icon from "../../components/Icon";
import AppShell, { NavItem } from "../../components/AppShell";
import SearchPalette from "../../components/SearchPalette";
import { useApi } from "../../components/ui";
import { useAuth } from "../../lib/auth";
import { useBadgeRefresh } from "../../lib/badges";
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
  const [searching, setSearching] = useState(false);
  useBadgeRefresh(() => void reload());

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

  const items: NavItem[] = [
    { to: "/m", label: "Orders", icon: "orders", end: true },
    { to: "/m/requests", label: "Requests", icon: "requests", badge: meta?.openRequests },
    { to: "/m/buyers", label: "Buyers", icon: "buyers" },
    { to: "/m/reports", label: "Reports", icon: "overview" },
    { to: "/m/feed", label: "Notifications", icon: "bell", badge: meta?.unreadNotifications },
    { to: "/m/settings", label: "Settings", icon: "settings", also: ["/m/templates", "/m/units", "/m/notifications", "/m/reset"] },
  ];

  return (
    <MetaCtx.Provider value={meta}>
      <ReloadCtx.Provider value={() => void reload()}>
        <AppShell
          brand="LoomTrack"
          home="/m"
          items={items}
          action={{ to: "/m/orders/new", label: "New order" }}
          onSearch={() => setSearching(true)}
          account={{
            name: user?.name ?? "",
            detail: "Merchandiser",
            extras: (<>
              <Link className="menu-link" to="/m/details"><Icon name="user" size={16} />My details</Link>
              <Link className="menu-link" to="/account/password"><Icon name="key" size={16} />Change password</Link>
              {meta && <div className="menu-row" title={meta.ai.mode === "indictrans2" ? `Notes are translated by ${meta.ai.model} on this machine (${meta.ai.device === "cuda" ? "GPU" : "CPU"})` : meta.ai.reason}>
                <span>Note translation</span>
                <span className={`pill ${meta.ai.mode === "indictrans2" ? "pill-green" : "pill-amber"}`}>{meta.ai.mode === "indictrans2" ? "Translation on" : "Keywords only"}</span>
              </div>}
            </>),
            onSignOut: signOut,
          }}
        >
          <Outlet />
        </AppShell>
        {searching && <SearchPalette onClose={() => setSearching(false)} />}
      </ReloadCtx.Provider>
    </MetaCtx.Provider>
  );
}
