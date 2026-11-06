import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState, PageHeader, Progress, Swatch, useCanWrite } from "../../components/ui";
import { BuyerData, BuyerOrder, orderChip } from "../../lib/buyer";
import { fmtDate, num } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

type Tab = "active" | "shipped" | "all";
type SortKey = "po" | "exFactory" | "progress";

export default function BuyerOrders() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{(_n, _t, data) => <List token={token} data={data} />}</BuyerFrame>;
}

function List({ token, data }: { token: string; data: BuyerData }) {
  const nav = useNavigate();
  const canWrite = useCanWrite();
  const [tab, setTab] = useState<Tab>("active");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "exFactory", dir: 1 });
  const counts = { active: data.orders.filter((o) => o.state === "active").length, shipped: data.orders.filter((o) => o.state === "shipped").length, all: data.orders.length };

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    const pick: Record<SortKey, (o: BuyerOrder) => string | number> = { po: (o) => o.poNo, exFactory: (o) => o.exFactory, progress: (o) => o.overallPct };
    return data.orders
      .filter((o) => (tab === "all" || o.state === tab) && (!term || [o.poNo, o.style, o.colour].some((v) => v.toLowerCase().includes(term))))
      .sort((a, b) => (pick[sort.key](a) < pick[sort.key](b) ? -sort.dir : pick[sort.key](a) > pick[sort.key](b) ? sort.dir : 0));
  }, [data.orders, tab, q, sort]);

  const th = (key: SortKey, label: string) => (
    <th aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button className="th-sort" onClick={() => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }))}>
        {label}{sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader title="Orders" sub="Every order you have with us. Open one for its progress, approvals, materials, files and messages."
        actions={canWrite ? <Link className="btn btn-primary" to={`/b/${token}/requests/new`}>New request</Link> : undefined} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="filter-tabs" role="group" aria-label="Show orders" style={{ borderBottom: 0 }}>
          {(["active", "shipped", "all"] as Tab[]).map((t) => (
            <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
              {t === "active" ? "In progress" : t === "shipped" ? "Shipped" : "All"} <span className="n num">{counts[t]}</span>
            </button>
          ))}
        </div>
        <input className="input input-sm" style={{ width: 260, maxWidth: "100%" }} type="search" placeholder="Find by PO, style or colour" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find an order" />
      </div>
      {shown.length === 0 ? (
        <EmptyState title={q ? `No order matches “${q}”` : tab === "shipped" ? "Nothing has shipped yet" : "No orders here"} hint={q ? "Try the PO number, the style or the colour." : "Send a request and your merchandiser will confirm it."} />
      ) : (
        <div className="card table-scroll">
          <table className="table rows-link">
            <thead><tr>{th("po", "Order")}<th>Style</th>{th("exFactory", "Ex-factory")}{th("progress", "Packed")}<th>Status</th></tr></thead>
            <tbody>
              {shown.map((o) => {
                const chip = orderChip(o);
                return (
                  <tr key={o.id} onClick={() => nav(`/b/${token}/orders/${o.id}`)}>
                    <td><Link to={`/b/${token}/orders/${o.id}`} className="po" onClick={(e) => e.stopPropagation()}>{o.poNo}</Link><div className="faint small num">{num(o.qty)} pcs</div></td>
                    <td><div>{o.style}</div><div className="faint small"><Swatch hex={o.colourHex} />{o.colour.toLowerCase()}</div></td>
                    <td className="nowrap"><div className="num">{fmtDate(o.exFactory, true)}</div>{o.notice && <div className="small t-red num">Expected {fmtDate(o.notice.expectedExFactory)}</div>}</td>
                    <td style={{ minWidth: 150 }}><div className="row small" style={{ justifyContent: "space-between" }}><span className="num">{o.overallPct}%</span></div><Progress pct={o.overallPct} tone={o.overallPct >= 100 ? "green" : ""} /></td>
                    <td>
                      <span className={`pill ${chip.tone ? `pill-${chip.tone}` : ""}`}>{chip.text}</span>
                      {o.lastMessage?.unread && <div className="flag t-amber">New reply</div>}
                      {o.notice && !o.notice.acknowledgedAt && <div className="flag t-red">Acknowledge the notice</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
