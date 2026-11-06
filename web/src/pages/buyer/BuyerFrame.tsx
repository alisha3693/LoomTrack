import { ReactNode, useEffect } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../../components/ui";
import BuyerAccount from "../../components/BuyerAccount";
import { ThemeToggle } from "../../lib/theme";

/** Header and "not a valid link" handling for the buyer's pages other than the order list. */
export default function BuyerFrame({ token, children }: { token: string; children: (buyerName: string, today: string) => ReactNode }) {
  const { data, error } = useApi<{ buyer: { name: string }; today: string }>(`/api/b/${token}`);
  useEffect(() => {
    document.documentElement.lang = "en";
  }, []);
  if (error) return <div className="login-wrap"><div className="card card-pad" style={{ maxWidth: 420 }}>{error}</div></div>;
  if (!data) return <div className="login-wrap faint">Loading…</div>;
  return (
    <div className="shell">
      <header className="buyer-head">
        <div className="inner">
          <div>
            <div className="faint small"><Link to={`/b/${token}`}>← Your orders</Link></div>
            <h1>{data.buyer.name}</h1>
          </div>
          <div className="row no-print"><BuyerAccount /><ThemeToggle /></div>
        </div>
      </header>
      <main className="page page-narrow">{children(data.buyer.name, data.today)}</main>
    </div>
  );
}
