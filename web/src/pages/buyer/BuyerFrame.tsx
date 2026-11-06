import { ReactNode, useEffect } from "react";
import { Link, NavLink } from "react-router-dom";
import BuyerAccount from "../../components/BuyerAccount";
import { useApi } from "../../components/ui";
import type { BuyerData } from "../../lib/buyer";
import type { RequestRow } from "../../lib/requests";
import { ThemeToggle } from "../../lib/theme";

/**
 * The buyer's pages: a header with real navigation (overview, orders, requests), the way to start a new request,
 * and the "not a valid link" handling. The children get the buyer's name, today's date and all their data.
 */
export default function BuyerFrame({
  token, children, wide,
}: {
  token: string;
  children: (buyerName: string, today: string, data: BuyerData) => ReactNode;
  /** Pages with lists and tables use the full width; forms and conversations stay narrow to read well. */
  wide?: boolean;
}) {
  const { data, error } = useApi<BuyerData>(`/api/b/${token}`);
  const { data: requests } = useApi<{ requests: RequestRow[] }>(`/api/b/${token}/requests`);
  useEffect(() => {
    document.documentElement.lang = "en";
    if (data) document.title = `${data.buyer.name} · LoomTrack`;
  }, [data]);

  if (error) return <div className="login-wrap"><div className="card card-pad stack" style={{ maxWidth: 420 }}><b>We could not open this page.</b><span className="muted">{error}</span><Link to="/">Back to the start</Link></div></div>;
  if (!data) return <div className="login-wrap faint">Loading…</div>;

  const needYou = (requests?.requests ?? []).filter((r) => r.status === "query" || r.status === "countered").length;

  return (
    <div className="shell">
      <header className="buyer-top no-print">
        <div className="inner">
          <Link to={`/b/${token}`} className="brand" style={{ color: "inherit" }}>
            <img src="/icon.svg" alt="" />
            <span className="who">{data.buyer.name}<small>Order status, updated daily</small></span>
          </Link>
          <nav className="buyer-nav" aria-label="Main">
            <NavLink to={`/b/${token}`} end>Overview</NavLink>
            <NavLink to={`/b/${token}/orders`}>Orders</NavLink>
            <NavLink to={`/b/${token}/requests`}>Requests{needYou > 0 ? <span className="badge" title="Waiting for your answer">{needYou}</span> : null}</NavLink>
          </nav>
          <div className="actions row" style={{ marginLeft: "auto", gap: 8 }}>
            <Link className="btn btn-primary btn-sm" to={`/b/${token}/requests/new`}>+ New request</Link>
            <BuyerAccount />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="page" style={{ maxWidth: wide ? 1080 : 780 }}>{children(data.buyer.name, data.today, data)}</main>
    </div>
  );
}
