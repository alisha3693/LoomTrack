import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import BuyerOrderRow from "../../components/BuyerOrderRow";
import { Empty } from "../../components/ui";
import type { BuyerData } from "../../lib/buyer";
import BuyerFrame from "./BuyerFrame";

type Tab = "active" | "shipped" | "all";

export default function BuyerOrders() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{(_n, _t, data) => <List token={token} data={data} />}</BuyerFrame>;
}

function List({ token, data }: { token: string; data: BuyerData }) {
  const [tab, setTab] = useState<Tab>("active");
  const [q, setQ] = useState("");
  const counts = { active: data.orders.filter((o) => o.state === "active").length, shipped: data.orders.filter((o) => o.state === "shipped").length, all: data.orders.length };
  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return data.orders.filter((o) => (tab === "all" || o.state === tab) && (!term || [o.poNo, o.style, o.colour].some((v) => v.toLowerCase().includes(term))));
  }, [data.orders, tab, q]);

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h1>Orders</h1><p className="sub">Every order you have with us. Open one for its progress, materials, files and messages.</p></div>
        <Link className="btn btn-primary" to={`/b/${token}/requests/new`}>+ New request</Link>
      </div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="tabs" role="tablist" style={{ borderBottom: 0 }}>
          {(["active", "shipped", "all"] as Tab[]).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
              {t === "active" ? "In progress" : t === "shipped" ? "Shipped" : "All"} <span className="faint">{counts[t]}</span>
            </button>
          ))}
        </div>
        <input className="input input-sm" style={{ width: 260, maxWidth: "100%" }} type="search" placeholder="Find by PO, style or colour" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find an order" />
      </div>
      {shown.length === 0 ? (
        <Empty>{q ? `No order matches “${q}”.` : tab === "shipped" ? "Nothing has shipped yet." : "No orders here."}</Empty>
      ) : (
        <section className="card">{shown.map((o) => <BuyerOrderRow key={o.id} token={token} o={o} />)}</section>
      )}
    </div>
  );
}
