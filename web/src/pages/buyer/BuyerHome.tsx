import { Link, useParams } from "react-router-dom";
import Attention from "../../components/Attention";
import BuyerOrderRow from "../../components/BuyerOrderRow";
import { RequestPill } from "../../components/RequestParts";
import { useApi } from "../../components/ui";
import { attentionFor, BuyerData, isClosed } from "../../lib/buyer";
import { ago, fmtDate, num } from "../../lib/format";
import type { RequestRow } from "../../lib/requests";
import BuyerFrame from "./BuyerFrame";

const SHOWN = 6;

export default function BuyerHome() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{(name, today, data) => <Home token={token} name={name} today={today} data={data} />}</BuyerFrame>;
}

function Home({ token, name, today, data }: { token: string; name: string; today: string; data: BuyerData }) {
  const { data: reqs } = useApi<{ requests: RequestRow[] }>(`/api/b/${token}/requests`);
  const requests = reqs?.requests ?? [];
  const active = data.orders.filter((o) => o.state === "active");
  const notices = active.filter((o) => o.notice).length;
  const open = requests.filter((r) => !isClosed(r.status));
  const items = reqs ? attentionFor(token, data.orders, requests) : [];

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Hello, {name}</h1>
          <p className="sub">As of {fmtDate(today, true)}. Here is what needs you and where your orders stand.</p>
        </div>
        <div className="row no-print">
          <a className="btn btn-sm" href={`/api/b/${token}/weekly.xlsx`}>Weekly status (Excel)</a>
          <button className="btn btn-ghost btn-sm" onClick={() => window.print()}>Print / PDF</button>
        </div>
      </div>

      <section aria-label="Needs your attention">
        <div className="section-title">Needs your attention</div>
        {reqs ? <Attention items={items} clear="You are all caught up. Nothing is waiting for you right now." /> : <p className="faint">Loading…</p>}
      </section>

      <div className="tiles">
        <Link className="tile" to={`/b/${token}/orders`} style={{ textDecoration: "none" }}><b className="num">{active.length}</b><span>Active orders</span></Link>
        <Link className="tile" to={`/b/${token}/orders`} style={{ textDecoration: "none" }}><b className={`num ${notices ? "t-red" : ""}`}>{notices}</b><span>With a delay notice</span></Link>
        <Link className="tile" to={`/b/${token}/requests`} style={{ textDecoration: "none" }}><b className="num">{open.length}</b><span>Open requests</span></Link>
        <div className="tile"><b className="num">{num(active.reduce((a, o) => a + o.qty, 0))}</b><span>Pieces in production</span></div>
      </div>

      <section className="card" aria-label="Your orders">
        <div className="card-head">
          <h2>Your orders</h2>
          <Link className="small" to={`/b/${token}/orders`}>{data.orders.length > SHOWN ? `See all ${data.orders.length} orders →` : "Open the orders list →"}</Link>
        </div>
        {data.orders.length === 0 ? (
          <div className="card-body stack" style={{ alignItems: "flex-start" }}>
            <p className="muted" style={{ margin: 0 }}>You have no orders with us yet. Send a request and your merchandiser will confirm it.</p>
            <Link className="btn btn-primary" to={`/b/${token}/requests/new`}>Send your first request</Link>
          </div>
        ) : data.orders.slice(0, SHOWN).map((o) => <BuyerOrderRow key={o.id} token={token} o={o} />)}
      </section>

      {requests.length > 0 && (
        <section className="card" aria-label="Your requests">
          <div className="card-head"><h2>Your requests</h2><Link className="small" to={`/b/${token}/requests`}>All requests →</Link></div>
          {requests.slice(0, 4).map((r) => (
            <Link key={r.id} to={`/b/${token}/requests/${r.id}`} className="order-row req">
              <div style={{ minWidth: 0 }}>
                <div className="t">{r.poNo}{r.kind === "amendment" ? <span className="pill" style={{ marginLeft: 8 }}>Change</span> : null}</div>
                <div className="muted small">{r.style}, {r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div>
              </div>
              <div className="muted small">{ago(r.updatedAt)}</div>
              <div style={{ textAlign: "right" }}><RequestPill status={r.status} audience="buyer" /></div>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
