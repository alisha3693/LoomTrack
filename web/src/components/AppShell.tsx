import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import Icon, { IconName } from "./Icon";
import { useTheme } from "../lib/theme";

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  /** A count that needs the person's attention. Shown only when above zero. */
  badge?: number;
}
export interface NavGroup { label?: string; items: NavItem[] }

export interface ShellAccount {
  name: string;
  detail?: string;
  /** Menu entries beyond theme (change password, status lines) and sign out. */
  extras?: ReactNode;
  onSignOut: () => void;
}

const COLLAPSE_KEY = "lt.rail";
const collapsedAtStart = () => {
  try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
};
const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";

/**
 * The frame every signed-in page lives in: a sidebar with the main places (line icons, labels, counts),
 * the one primary action, search and the account at the bottom; on a phone the same items become a tab bar.
 * It holds no data and fetches nothing.
 */
export default function AppShell({
  brand, home, groups, action, onSearch, account, children,
}: {
  brand: string;
  home: string;
  groups: NavGroup[];
  action?: { to: string; label: string };
  onSearch?: () => void;
  account: ShellAccount;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(collapsedAtStart);
  const { pathname } = useLocation();
  const flat = groups.flatMap((g) => g.items);
  const primary = flat.slice(0, 4);
  const rest = flat.slice(4);

  const toggle = () => setCollapsed((c) => {
    try { localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1"); } catch { /* the choice lasts for this visit only */ }
    return !c;
  });

  const link = (i: NavItem) => (
    <NavLink key={i.to} to={i.to} end={i.end} className="rail-link" title={collapsed ? i.label : undefined}>
      <Icon name={i.icon} />
      <span className="rail-text">{i.label}</span>
      {!!i.badge && i.badge > 0 && <span className="badge" aria-label={`${i.badge} waiting`}>{i.badge}</span>}
    </NavLink>
  );

  return (
    <div className={`app${collapsed ? " rail-collapsed" : ""}`}>
      <a className="skip-link" href="#content">Skip to the page</a>
      <aside className="rail no-print" aria-label="Main">
        <div className="rail-top">
          <Link to={home} className="brand" title={brand}>
            <img src="/icon.svg" alt="" width="26" height="26" />
            <span className="rail-text">{brand}</span>
          </Link>
        </div>

        <div className="rail-actions">
          {action && (
            <Link to={action.to} className="btn btn-primary rail-primary" title={collapsed ? action.label : undefined}>
              <Icon name="plus" size={18} /><span className="rail-text">{action.label}</span>
            </Link>
          )}
          {onSearch && (
            <button type="button" className="rail-search" onClick={onSearch} aria-label="Search" title="Search">
              <Icon name="search" size={18} /><span className="rail-text">Search</span><kbd className="rail-text">/</kbd>
            </button>
          )}
        </div>

        <nav className="rail-nav" aria-label="Sections">
          {groups.map((g, n) => (
            <div key={g.label ?? n} className="rail-group">
              {g.label && <div className="rail-label rail-text">{g.label}</div>}
              {g.items.map(link)}
            </div>
          ))}
        </nav>

        <div className="rail-foot">
          <AccountMenu account={account} collapsed={collapsed} />
          <button type="button" className="rail-collapse" onClick={toggle} aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"} title={collapsed ? "Expand" : "Collapse"}>
            <Icon name="panel" size={18} />
          </button>
        </div>
      </aside>

      <div className="app-main" id="content" tabIndex={-1}>{children}</div>

      <nav className="tabbar no-print" aria-label="Main">
        {primary.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className="tab">
            <span className="tab-icon"><Icon name={i.icon} />{!!i.badge && i.badge > 0 && <span className="tab-dot" aria-label={`${i.badge} waiting`} />}</span>
            <span>{i.label}</span>
          </NavLink>
        ))}
        <MoreMenu items={rest} account={account} path={pathname} />
      </nav>
    </div>
  );
}

function useOutsideClose(ref: React.RefObject<HTMLDetailsElement>) {
  const { pathname } = useLocation();
  useEffect(() => ref.current?.removeAttribute("open"), [pathname, ref]);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && ref.current.removeAttribute("open");
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [ref]);
}

function AccountMenu({ account, collapsed }: { account: ShellAccount; collapsed: boolean }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const { choice, cycle } = useTheme();
  useOutsideClose(ref);
  return (
    <details className="menu account" ref={ref}>
      <summary aria-label={`Account: ${account.name}`} title={collapsed ? account.name : undefined}>
        <span className="avatar">{initials(account.name)}</span>
        <span className="rail-text account-who"><b>{account.name}</b>{account.detail && <small>{account.detail}</small>}</span>
      </summary>
      <div className="menu-list account-list">
        {account.extras}
        <button className="menu-link" onClick={cycle}>
          <Icon name={choice === "dark" ? "moon" : "sun"} size={16} />
          Theme: {choice === "system" ? "follows device" : choice}
        </button>
        <hr />
        <button className="menu-link" onClick={account.onSignOut}><Icon name="logout" size={16} />Sign out</button>
      </div>
    </details>
  );
}

function MoreMenu({ items, account, path }: { items: NavItem[]; account: ShellAccount; path: string }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const { choice, cycle } = useTheme();
  useOutsideClose(ref);
  const active = items.some((i) => path.startsWith(i.to));
  return (
    <details className={`tab more${active ? " active" : ""}`} ref={ref}>
      <summary><span className="tab-icon"><Icon name="more" /></span><span>More</span></summary>
      <div className="more-sheet">
        {items.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className="rail-link">
            <Icon name={i.icon} /><span>{i.label}</span>{!!i.badge && i.badge > 0 && <span className="badge">{i.badge}</span>}
          </NavLink>
        ))}
        <hr />
        <div className="more-who faint small">{account.name}</div>
        {account.extras}
        <button className="menu-link" onClick={cycle}><Icon name={choice === "dark" ? "moon" : "sun"} size={16} />Theme: {choice === "system" ? "follows device" : choice}</button>
        <button className="menu-link" onClick={account.onSignOut}><Icon name="logout" size={16} />Sign out</button>
      </div>
    </details>
  );
}
