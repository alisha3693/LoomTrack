import { Link, useParams } from "react-router-dom";
import Attention from "../../components/Attention";
import { RequestPill } from "../../components/RequestParts";
import { EmptyState, PageHeader, Progress, Skeleton, useApi } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import { attentionFor, BuyerData, isClosed, orderChip } from "../../lib/buyer";
import type { Approval } from "../../lib/flow";
import { ago, fmtDate, num, plural } from "../../lib/format";
import type { RequestRow } from "../../lib/requests";
import BuyerFrame from "./BuyerFrame";

const SHOWN = 5;

export default function BuyerHome() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{(name, today, data) => <Home token={token} name={name} today={today} data={data} />}</BuyerFrame>;
}

function Home({ token, name, today, data }: { token: string; name: string; today: string; data: BuyerData }) {
  const { data: reqs, reload: reloadReqs } = useApi<{ requests: RequestRow[] }>(`/api/b/${token}/requests`);
  const { data: apr, reload: reloadApr } = useApi<{ approvals: Approval[] }>(`/api/b/${token}/approvals`);
  useBadgeRefresh(() => { void reloadReqs(); void reloadApr(); });
  const requests = reqs?.requests ?? [];
  const active = data.orders.filter((o) => o.state === "active");
  const open = requests.filter((r) => !isClosed(r.status));
  const ready = !!reqs && !!apr;
  const items = ready ? attentionFor(token, data.orders, requests, apr!.approvals) : [];
  const coming = [...active].sort((a, b) => a.exFactory.localeCompare(b.exFactory)).slice(0, SHOWN);
  const pieces = active.reduce((a, o) => a + o.qty, 0);

  return (
    <div className="stack" style={{ gap: 28 }}>
      <PageHeader
        title={name}
        sub={`As of ${fmtDate(today, true)} · ${plural(active.length, "order")} in production${pieces ? `, ${num(pieces)} pieces` : ""}`}
        actions={<><a className="btn btn-sm" href={`/api/b/${token}/weekly.xlsx`}>Weekly status (Excel)</a><button className="btn btn-ghost btn-sm" onClick={() => window.print()}>Print / PDF</button></>}
      />

      <section aria-label="Needs your attention">
        <div className="section-title">Needs your attention</div>
        {ready ? <Attention items={items} clear="You are all caught up. Nothing is waiting for you right now." /> : <Skeleton rows={2} />}
      </section>

      <section aria-label="Coming up" className="stack" style={{ gap: 10 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="section-title" style={{ margin: 0 }}>Coming up</div>
          <Link className="small" to={`/b/${token}/orders`}>{data.orders.length > SHOWN ? `All ${data.orders.length} orders` : "All orders"} →</Link>
        </div>
        {coming.length === 0 ? (
          <EmptyState title="No orders in production" hint="Send a request and your merchandiser will confirm it." action={<Link className="btn btn-primary btn-sm" to={`/b/${token}/requests/new`}>Send your first request</Link>} />
        ) : (
          <div className="card">
            {coming.map((o) => {
              const chip = orderChip(o);
              return (
                <Link key={o.id} to={`/b/${token}/orders/${o.id}`} className="upcoming">
                  <div className="when num"><b>{fmtDate(o.exFactory)}</b><span className="faint small">{fmtDate(o.exFactory, true).slice(0, 3)}</span></div>
                  <div style={{ minWidth: 0 }}>
                    <div className="t">{o.poNo}</div>
                    <div className="muted small">{o.style}, {o.colour.toLowerCase()} · {num(o.qty)} pcs</div>
                  </div>
                  <div className="upcoming-bar"><div className="faint small num">Packed {o.overallPct}%</div><Progress pct={o.overallPct} tone={o.overallPct >= 100 ? "green" : ""} /></div>
                  <span className={`pill ${chip.tone ? `pill-${chip.tone}` : ""}`}>{chip.text}</span>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {open.length > 0 && (
        <section aria-label="Open requests" className="stack" style={{ gap: 10 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="section-title" style={{ margin: 0 }}>Open requests</div>
            <Link className="small" to={`/b/${token}/requests`}>All requests →</Link>
          </div>
          <div className="card">
            {open.slice(0, 4).map((r) => (
              <Link key={r.id} to={`/b/${token}/requests/${r.id}`} className="order-row req">
                <div style={{ minWidth: 0 }}>
                  <div className="t">{r.poNo}{r.kind === "amendment" ? <span className="tag" style={{ marginLeft: 8 }}>Change</span> : null}</div>
                  <div className="muted small">{r.style}, {r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div>
                </div>
                <div className="muted small">{ago(r.updatedAt)}</div>
                <div style={{ textAlign: "right" }}><RequestPill status={r.status} audience="buyer" /></div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
