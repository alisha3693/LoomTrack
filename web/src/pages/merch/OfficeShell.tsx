import { createContext, useContext, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import AppShell, { NavGroup } from "../../components/AppShell";
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

  const groups: NavGroup[] = [
    {
      items: [
        { to: "/m", label: "Orders", icon: "orders", end: true },
        { to: "/m/requests", label: "Requests", icon: "requests", badge: meta?.openRequests },
        { to: "/m/approvals", label: "Approvals", icon: "approvals", badge: meta?.approvalsToAnswer },
        { to: "/m/messages", label: "Messages", icon: "messages", badge: meta?.unreadMessages },
        { to: "/m/buyers", label: "Buyers", icon: "buyers" },
      ],
    },
    {
      label: "Set up",
      items: [
        { to: "/m/templates", label: "Plan templates", icon: "templates" },
        { to: "/m/units", label: "Units and capacity", icon: "units" },
      ],
    },
  ];

  return (
    <MetaCtx.Provider value={meta}>
      <ReloadCtx.Provider value={() => void reload()}>
        <AppShell
          brand="LoomTrack"
          home="/m"
          groups={groups}
          action={{ to: "/m/orders/new", label: "New order" }}
          onSearch={() => setSearching(true)}
          account={{
            name: user?.name ?? "",
            detail: "Merchandiser",
            extras: meta ? (
              <div className="menu-row" title={meta.ai.mode === "ollama" ? `Notes are translated by ${meta.ai.model}, running locally` : meta.ai.reason}>
                <span>Note translation</span>
                <span className={`pill ${meta.ai.mode === "ollama" ? "pill-green" : "pill-amber"}`}>{meta.ai.mode === "ollama" ? "AI on" : "Keywords only"}</span>
              </div>
            ) : null,
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
