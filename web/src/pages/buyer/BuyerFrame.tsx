import { ReactNode, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell, { NavGroup } from "../../components/AppShell";
import Icon from "../../components/Icon";
import { useApi } from "../../components/ui";
import { useAuth } from "../../lib/auth";
import { useBadgeRefresh } from "../../lib/badges";
import type { BuyerData } from "../../lib/buyer";

export interface Badges { requests: number; messages: number; approvals: number }

/**
 * The buyer's pages: a sidebar with real navigation, the way to start a new request, and the
 * "not a valid link" handling. The children get the buyer's name, today's date and all their data.
 */
export default function BuyerFrame({
  token, children, wide,
}: {
  token: string;
  children: (buyerName: string, today: string, data: BuyerData, reload: () => void) => ReactNode;
  /** Pages with lists and tables use the full width; forms and conversations stay narrow to read well. */
  wide?: boolean;
}) {
  const { user, signOut } = useAuth();
  const nav = useNavigate();
  const { data, error, reload } = useApi<BuyerData>(`/api/b/${token}`);
  const { data: badges, reload: reloadBadges } = useApi<Badges>(`/api/b/${token}/badges`);
  useBadgeRefresh(() => { void reloadBadges(); void reload(); });
  useEffect(() => {
    document.documentElement.lang = "en";
    if (data) document.title = `${data.buyer.name} · LoomTrack`;
  }, [data]);

  if (error) return <div className="login-wrap"><div className="card card-pad stack" style={{ maxWidth: 420 }}><b>We could not open this page.</b><span className="muted">{error}</span><Link to="/">Back to the start</Link></div></div>;
  if (!data) return <div className="login-wrap faint">Loading…</div>;

  const base = `/b/${token}`;
  const groups: NavGroup[] = [{
    items: [
      { to: base, label: "Overview", icon: "overview", end: true },
      { to: `${base}/orders`, label: "Orders", icon: "orders" },
      { to: `${base}/requests`, label: "Requests", icon: "requests", badge: badges?.requests },
      { to: `${base}/messages`, label: "Messages", icon: "messages", badge: badges?.messages },
      { to: `${base}/approvals`, label: "Approvals", icon: "approvals", badge: badges?.approvals },
      { to: `${base}/documents`, label: "Documents", icon: "documents" },
    ],
  }];
  const isAccount = user?.role === "buyer";

  return (
    <AppShell
      brand="LoomTrack"
      home={base}
      groups={groups}
      action={user?.can_write === 0 ? undefined : { to: `${base}/requests/new`, label: "New request" }}
      account={{
        name: data.buyer.name,
        detail: isAccount ? user?.name : "Private link",
        extras: isAccount ? <Link className="menu-link" to="/account/password"><Icon name="key" size={16} />Change password</Link> : null,
        onSignOut: () => { if (isAccount) signOut(); nav("/", { replace: true }); },
      }}
    >
      <main className="page" style={{ maxWidth: 1080 }}>
        <div style={{ maxWidth: wide ? undefined : 780 }}>{children(data.buyer.name, data.today, data, () => void reload())}</div>
      </main>
    </AppShell>
  );
}
