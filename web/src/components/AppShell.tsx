import { ReactNode, useEffect, useRef } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import Icon, { IconName } from "./Icon";
import { ThemeToggle } from "../lib/theme";

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  /** A count that needs the person's attention. Shown only when above zero. */
  badge?: number;
  /** Other places that belong under this item, so it stays highlighted there (Settings covers its pages). */
  also?: string[];
}

export interface ShellAccount {
  name: string;
  detail?: string;
  /** Menu entries between the name and sign out (My details, change password, status lines). */
  extras?: ReactNode;
  onSignOut: () => void;
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
const isActive = (i: NavItem, path: string) =>
  (i.end ? path === i.to : path === i.to || path.startsWith(i.to + "/")) || !!i.also?.some((p) => path === p || path.startsWith(p + "/"));

/**
 * The frame every signed-in page lives in.
 *   Sidebar:  the product, the one primary action, and the main places.
 *   Top bar:  search, the theme, and the account.
 *   Phone:    the same top bar, and the main places as a tab bar.
 * It holds no data and fetches nothing.
 */
export default function AppShell({
  brand, home, items, action, onSearch, account, children,
}: {
  brand: string;
  home: string;
  items: NavItem[];
  action?: { to: string; label: string };
  onSearch?: () => void;
  account: ShellAccount;
  children: ReactNode;
}) {
  const { pathname } = useLocation();
  const tabs = items.length > 5 ? items.slice(0, 4) : items;
  const more = items.length > 5 ? items.slice(4) : [];

  return (
    <div className="app">
      <a className="skip-link" href="#content">Skip to the page</a>

      <aside className="rail no-print" aria-label="Main">
        <Link to={home} className="brand" title={brand}>
          <img src="/icon.svg" alt="" width="26" height="26" />
          {brand}
        </Link>
        {action && (
          <Link to={action.to} className="btn btn-primary rail-primary">
            <Icon name="plus" size={16} />{action.label}
          </Link>
        )}
        <nav className="rail-nav" aria-label="Sections">
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.end} className={`rail-link${isActive(i, pathname) ? " active" : ""}`}>
              <Icon name={i.icon} />
              <span>{i.label}</span>
              {!!i.badge && i.badge > 0 && <span className="badge" aria-label={`${i.badge} waiting`}>{i.badge}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="app-col">
        <header className="topbar no-print">
          <Link to={home} className="brand topbar-brand" aria-label={brand}>
            <img src="/icon.svg" alt="" width="24" height="24" />
          </Link>
          {onSearch ? (
            <button type="button" className="top-search" onClick={onSearch} aria-label="Search orders, requests and buyers">
              <Icon name="search" size={16} />
              <span>Search</span>
              <kbd>/</kbd>
            </button>
          ) : <span />}
          <div className="top-right">
            <ThemeToggle />
            <AccountMenu account={account} />
          </div>
        </header>
        <div className="app-main" id="content" tabIndex={-1}>{children}</div>
      </div>

      <nav className="tabbar no-print" aria-label="Main">
        {tabs.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className={`tab${isActive(i, pathname) ? " active" : ""}`}>
            <span className="tab-icon"><Icon name={i.icon} />{!!i.badge && i.badge > 0 && <span className="tab-dot" aria-label={`${i.badge} waiting`} />}</span>
            <span>{i.label}</span>
          </NavLink>
        ))}
        {more.length > 0 && <MoreMenu items={more} path={pathname} />}
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

function AccountMenu({ account }: { account: ShellAccount }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useOutsideClose(ref);
  return (
    <details className="menu account" ref={ref}>
      <summary aria-label={`Account: ${account.name}`}>
        <span className="avatar">{initials(account.name)}</span>
      </summary>
      <div className="menu-list account-list">
        <div className="account-who">
          <b>{account.name}</b>
          {account.detail && <small>{account.detail}</small>}
        </div>
        <hr />
        {account.extras}
        <hr />
        <button className="menu-link" onClick={account.onSignOut}><Icon name="logout" size={16} />Sign out</button>
      </div>
    </details>
  );
}

function MoreMenu({ items, path }: { items: NavItem[]; path: string }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useOutsideClose(ref);
  const active = items.some((i) => isActive(i, path));
  return (
    <details className={`tab more${active ? " active" : ""}`} ref={ref}>
      <summary><span className="tab-icon"><Icon name="more" /></span><span>More</span></summary>
      <div className="more-sheet">
        {items.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className={`rail-link${isActive(i, path) ? " active" : ""}`}>
            <Icon name={i.icon} /><span>{i.label}</span>{!!i.badge && i.badge > 0 && <span className="badge">{i.badge}</span>}
          </NavLink>
        ))}
      </div>
    </details>
  );
}
