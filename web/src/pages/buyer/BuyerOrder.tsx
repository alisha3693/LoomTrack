import { Link, useParams, useSearchParams } from "react-router-dom";
import { FileList } from "../../components/Attachments";
import Activity from "../../components/Activity";
import { ApprovalCard, BuyerDecision, NoApprovals } from "../../components/Approvals";
import NoticeCard from "../../components/NoticeCard";
import { PageHeader, Progress, Swatch, useApi, useCanWrite } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import { BuyerOrder as Order, CancelledOrder, orderChip } from "../../lib/buyer";
import { fabricLine } from "../../lib/fabric";
import type { ActivityItem, Approval } from "../../lib/flow";
import { fmtDate, fmtDateTime, num } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

const FIELD: Record<string, string> = { ex_factory: "Ex-factory", planned_date: "Due date", planned_start: "Start date", actual_date: "Completed" };
type Tab = "progress" | "approvals" | "materials" | "files" | "history";

export default function BuyerOrder() {
  const { token = "", orderId } = useParams();
  return (
    <BuyerFrame token={token} wide>
      {(_n, _t, data, reload) => {
        const o = data.orders.find((x) => String(x.id) === orderId);
        const gone = o ? undefined : data.cancelledOrders.find((x) => String(x.id) === orderId);
        if (gone) return <CancelledCard token={token} o={gone} />;
        return o ? <Detail token={token} o={o} onChanged={reload} /> : (
          <div className="card card-pad stack" style={{ alignItems: "flex-start" }}>
            <b>We could not find that order.</b>
            <Link className="btn" to={`/b/${token}/orders`}>Back to your orders</Link>
          </div>
        );
      }}
    </BuyerFrame>
  );
}

export function CancelledCard({ token, o }: { token: string; o: CancelledOrder }) {
  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader crumbs={[{ label: "Orders", to: `/b/${token}/orders` }, { label: o.poNo }]} title={o.poNo} status={<span className="pill pill-red">Cancelled</span>}
        sub={`${o.style} · ${num(o.qty)} pcs`} />
      <section className="turn" aria-label="Cancelled">
        <div className="stack">
          <h2>This order was cancelled{o.cancelledAt ? ` on ${fmtDate(o.cancelledAt.slice(0, 10), true)}` : ""}</h2>
          {o.reason && <p style={{ whiteSpace: "pre-wrap" }}>Reason: {o.reason}</p>}
          <p className="muted">It will not be produced. If you still need these goods, send a new request.</p>
        </div>
      </section>
    </div>
  );
}

function Detail({ token, o, onChanged }: { token: string; o: Order; onChanged: () => void }) {
  const canWrite = useCanWrite();
  const { data: apr, reload: reloadApr } = useApi<{ approvals: Approval[] }>(`/api/b/${token}/approvals`);
  const { data: act } = useApi<{ activity: ActivityItem[] }>(`/api/b/${token}/orders/${o.id}/activity`);
  useBadgeRefresh(() => void reloadApr());
  const approvals = (apr?.approvals ?? []).filter((a) => a.orderId === o.id);
  const toDecide = approvals.filter((a) => a.status === "requested").length;
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get("tab") === "history" ? "history" : "progress";  // approvals, materials and files are not used
  const setTab = (t: Tab) => setParams(t === "progress" ? {} : { tab: t }, { replace: true });
  const chip = orderChip(o);
  const fabric = fabricLine(o.fabric);
  const received = o.materials.filter((m) => m.received).length;
  const owed = o.materials.filter((m) => m.suppliedBy === "buyer" && !m.received);

  const TABS: { id: Tab; label: string; extra?: React.ReactNode }[] = [
    { id: "progress", label: "Progress" },
    { id: "history", label: "History" },
  ];

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader
        crumbs={[{ label: "Orders", to: `/b/${token}/orders` }, { label: o.poNo }]}
        title={o.poNo}
        status={<span className={`pill ${chip.tone ? `pill-${chip.tone}` : ""}`}>{chip.text}</span>}
        sub={<>{o.style}, <Swatch hex={o.colourHex} />{o.colour.toLowerCase()}{o.colourPantone ? ` (Pantone ${o.colourPantone})` : ""}{fabric ? ` · ${fabric}` : ""}</>}
        actions={<>
          {o.state === "active" && canWrite && <Link className="btn btn-sm" to={`/b/${token}/orders/${o.id}/change`} title="A new date or different quantities">Ask for a change</Link>}
          <button className="btn btn-ghost btn-sm" onClick={() => window.print()}>Print / PDF</button>
        </>}
      />

      <section className="card card-pad">
        <div className="kv">
          <div><span>Ex-factory (ready to ship)</span><b className="num">{fmtDate(o.exFactory, true)}</b></div>
          <div><span>Now expected</span><b className={`num ${o.notice ? "t-red" : ""}`}>{o.notice ? fmtDate(o.notice.expectedExFactory, true) : "As planned"}</b></div>
          <div><span>Quantity</span><b className="num">{num(o.qty)} pcs</b></div>
          <div><span>Packed</span><b className="num">{o.overallPct}%</b></div>
        </div>
        <div style={{ marginTop: 12 }}><Progress pct={o.overallPct} tone={o.overallPct >= 100 ? "green" : ""} /></div>
        <div className="faint small" style={{ marginTop: 10 }}>{o.sizes.map((s) => `${s.size} ${num(s.qty)}`).join(" · ")}</div>
      </section>

      {o.notice && <NoticeCard token={token} orderId={o.id} exFactory={o.exFactory} notice={o.notice} onChanged={onChanged} />}
      {owed.length > 0 && (
        <div className="banner banner-warn">
          <b>We are waiting for {owed.map((m) => m.name.toLowerCase()).join(", ")} from you.</b> Production cannot use it until it arrives.
        </div>
      )}

      <div className="tabs no-print" role="tablist" aria-label="About this order">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}{t.extra}</button>
        ))}
      </div>

      {tab === "progress" && (
        <div className="grid-2" style={{ alignItems: "start" }}>
          <section className="card card-pad">
            <div className="section-title">Production</div>
            <div className="stack" style={{ gap: 12 }}>
              {o.milestones.filter((m) => m.kind === "stage").map((m) => (
                <div key={m.code}>
                  <div className="row small" style={{ justifyContent: "space-between" }}>
                    <span>{m.name}</span>
                    <span className="num muted">{m.done !== null ? `${num(m.done)} · ` : ""}{m.pct}%</span>
                  </div>
                  <Progress pct={m.pct} tone={m.pct >= 100 ? "green" : ""} />
                </div>
              ))}
            </div>
          </section>
          <section className="card card-pad">
            <div className="section-title">Milestones</div>
            <ul className="timeline">
              {o.milestones.filter((m) => m.kind === "milestone").map((m) => (
                <li key={m.code} style={{ padding: "7px 0" }}>
                  <span className={`check ${m.actualDate ? "done" : ""}`}>{m.actualDate ? "✓" : ""}</span>
                  <span>{m.name}</span>
                  <span className="small num muted">{m.actualDate ? `Done ${fmtDate(m.actualDate)}` : `Due ${fmtDate(m.plannedDate)}`}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {tab === "history" && (
        <div className="stack">
          <section className="card card-pad stack">
            <div className="section-title" style={{ margin: 0 }}>What happened on this order</div>
            <Activity items={act?.activity ?? null} />
          </section>
          <section className="card card-pad">
            <div className="section-title">Every date that moved, and why</div>
            {o.dateChanges.length === 0 ? <p className="muted" style={{ margin: 0 }}>No planned dates have changed on this order.</p> : (
              <ul className="reasons small">
                {o.dateChanges.map((d, i) => (
                  <li key={i}>
                    {d.milestone ?? "Order"} · {FIELD[d.field] ?? d.field}: {fmtDate(d.oldValue)} → {fmtDate(d.newValue)}
                    <span className="faint"> · “{d.reason}” · {fmtDateTime(d.changedAt)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
