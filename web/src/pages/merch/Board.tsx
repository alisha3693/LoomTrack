import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Attention, { AttentionItem } from "../../components/Attention";
import { EmptyState, PageHeader, Progress, Skeleton, StatusPill, Swatch, useApi } from "../../components/ui";
import { addDaysIso, fmtDate, num, plural, Status } from "../../lib/format";
import type { BoardOrder } from "../../lib/types";
import { useMeta } from "./OfficeShell";

const COUNT_LABEL: Record<Status, string> = { red: "Will miss ex-factory", amber: "Behind plan", green: "On track" };

/** What the order is doing now: the stage that decides the date, how far along it is, and the rate it needs. */
function StageCell({ o }: { o: BoardOrder }) {
  const k = o.keyStage;
  if (!k) return <span className="faint">All stages done</span>;
  const tone = o.status === "green" ? "" : o.status;
  let line: JSX.Element | string;
  if (k.rateBasis !== "actual") line = "Not started";
  else if (k.requiredPerDay === null) line = <span className="t-red">Past planned end</span>;
  else line = <>needs {num(k.requiredPerDay)}/day, making {num(k.runRate)}</>;
  return (
    <div className="stage">
      <div className="row" style={{ gap: 8, justifyContent: "space-between" }}><span>{k.name}</span><span className="num muted">{k.pct}%</span></div>
      <Progress pct={k.pct} tone={tone} />
      <div className="faint small num" style={{ marginTop: 4 }}>{line}</div>
    </div>
  );
}

/** Everything that wants the merchandiser's attention on one order, in one place, most urgent first. */
function flagsFor(o: BoardOrder): { tone: "red" | "amber"; text: string }[] {
  const out: { tone: "red" | "amber"; text: string }[] = [];
  if (o.awaitingReply) out.push({ tone: "amber", text: "Buyer waiting for your reply" });
  if (o.approvals.sentBack > 0) out.push({ tone: "amber", text: "Buyer asked for changes" });
  if (o.pendingWarnings > 0) out.push({ tone: "amber", text: "Delay warning to review" });
  if (o.noticeUnacknowledged) out.push({ tone: "amber", text: "Delay notice not acknowledged" });
  const m = o.materials;
  if (m && m.late > 0) out.push({ tone: "red", text: `${plural(m.late, "material")} late` });
  else if (m && m.atRisk > 0) out.push({ tone: "amber", text: `${plural(m.atRisk, "material")} at risk` });
  return out;
}

function Flags({ o }: { o: BoardOrder }) {
  return <>{flagsFor(o).map((f) => <div key={f.text} className={`flag t-${f.tone}`}>{f.text}</div>)}</>;
}

function ExFactory({ o }: { o: BoardOrder }) {
  const moved = o.projectedExFactory !== o.exFactory;
  return (
    <>
      <div className="num">{fmtDate(o.exFactory, true)}</div>
      {moved && (
        <div className={`small num t-${o.status === "red" ? "red" : "amber"}`}>
          {o.slackDays < 0 ? `${plural(-o.slackDays, "day")} late` : "ahead"} · {fmtDate(o.projectedExFactory, true)}
        </div>
      )}
    </>
  );
}

function ExFactoryInline({ o }: { o: BoardOrder }) {
  return <>{fmtDate(o.exFactory, true)}{o.projectedExFactory !== o.exFactory ? ` → ${fmtDate(o.projectedExFactory, true)}` : ""}</>;
}

export default function Board() {
  const meta = useMeta();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const buyer = params.get("buyer") ?? "";
  const unit = params.get("unit") ?? "";
  const week = params.get("week") ?? "";
  const focus = params.get("focus") ?? "";
  const [only, setOnly] = useState<Status | null>(null);

  const qs = new URLSearchParams(Object.entries({ buyer, unit, week }).filter(([, v]) => v)).toString();
  const { data, error, loading } = useApi<{ today: string; orders: BoardOrder[]; weeks: string[] }>(`/api/m/board${qs ? `?${qs}` : ""}`);

  const counts = useMemo(() => {
    const c = { red: 0, amber: 0, green: 0 } as Record<Status, number>;
    data?.orders.forEach((o) => c[o.status]++);
    return c;
  }, [data]);
  const FOCUS: Record<string, { label: string; test: (o: BoardOrder) => boolean }> = {
    messages: { label: "orders where the buyer is waiting for your reply", test: (o) => o.awaitingReply },
    warnings: { label: "orders with a delay warning to review", test: (o) => o.pendingWarnings > 0 },
    materials: { label: "orders with late materials", test: (o) => !!o.materials && o.materials.late > 0 },
    approvals: { label: "orders where the buyer sent an approval back", test: (o) => o.approvals.sentBack > 0 },
    notices: { label: "orders whose delay notice the buyer has not acknowledged", test: (o) => o.noticeUnacknowledged },
    soon: { label: "orders shipping in the next 7 days", test: (o) => !!data && o.exFactory <= addDaysIso(data.today, 7) },
  };
  const [sort, setSort] = useState<{ key: "order" | "exFactory" | "progress"; dir: 1 | -1 } | null>(null);
  const filtered0 = (data?.orders ?? []).filter((o) => (!only || o.status === only) && (!FOCUS[focus] || FOCUS[focus].test(o)));
  const orders = !sort ? filtered0 : [...filtered0].sort((a, b) => {
    const va = sort.key === "order" ? a.poNo : sort.key === "exFactory" ? a.exFactory : a.keyStage?.pct ?? 101;
    const vb = sort.key === "order" ? b.poNo : sort.key === "exFactory" ? b.exFactory : b.keyStage?.pct ?? 101;
    return va < vb ? -sort.dir : va > vb ? sort.dir : 0;
  });
  const sortable = (key: "order" | "exFactory" | "progress", label: string) => (
    <th aria-sort={sort?.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button className="th-sort" onClick={() => setSort((s) => (s?.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }))}>
        {label}{sort?.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  // What needs you, in the order you would act on it. Each card goes straight to the thing.
  const needs: AttentionItem[] = [];
  const all = data?.orders ?? [];
  const named = (list: BoardOrder[]) => list.slice(0, 3).map((o) => o.poNo).join(", ") + (list.length > 3 ? ` and ${list.length - 3} more` : "");
  const waiting = all.filter(FOCUS.messages.test);
  const warned = all.filter(FOCUS.warnings.test);
  const short = all.filter(FOCUS.materials.test);
  const sentBack = all.filter(FOCUS.approvals.test);
  const unacked = all.filter(FOCUS.notices.test);
  if (meta && meta.openRequests > 0) needs.push({ key: "req", tone: "amber", title: `${plural(meta.openRequests, "buyer request")} waiting for your answer`, detail: "New orders and replies to your questions", cta: "Open requests", to: "/m/requests" });
  if (waiting.length) needs.push({ key: "msg", tone: "amber", title: `${plural(waiting.length, "buyer message")} to answer`, detail: named(waiting), cta: "Show these orders", onSelect: () => setFilter("focus", "messages") });
  if (sentBack.length) needs.push({ key: "apr", tone: "amber", title: `${plural(sentBack.length, "approval")} sent back by the buyer`, detail: named(sentBack), cta: "Answer them", to: "/m/approvals" });
  if (warned.length) needs.push({ key: "warn", tone: "red", title: `${plural(warned.length, "delay warning")} to review`, detail: `${named(warned)}. The buyer is told nothing until you confirm.`, cta: "Show these orders", onSelect: () => setFilter("focus", "warnings") });
  if (unacked.length) needs.push({ key: "ack", tone: "amber", title: `${plural(unacked.length, "delay notice")} the buyer has not acknowledged`, detail: named(unacked), cta: "Show these orders", onSelect: () => setFilter("focus", "notices") });
  if (short.length) needs.push({ key: "mat", tone: "red", title: `${plural(short.length, "order")} with late materials`, detail: named(short), cta: "Show these orders", onSelect: () => setFilter("focus", "materials") });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const filtered = !!(buyer || unit || week || only || focus);
  const total = data?.orders.length ?? 0;

  return (
    <main className="page">
      <PageHeader title="Orders" sub={data ? `${plural(total, "live order")} · as of ${fmtDate(data.today, true)}` : " "} actions={<Link className="btn btn-primary phone-only" to="/m/orders/new">New order</Link>} />

      <div className="stack" style={{ gap: 24 }}>
        {data && (
          <section aria-label="Needs you">
            <div className="section-title">Needs you</div>
            <Attention items={needs} clear="Nothing is waiting for you. No buyer needs an answer and no warning needs a decision." />
          </section>
        )}

        <section aria-label="All orders" className="stack" style={{ gap: 12 }}>
          <div className="filter-tabs" role="group" aria-label="Show orders">
            <button aria-pressed={only === null} onClick={() => setOnly(null)}>All <span className="n num">{total}</span></button>
            {(["red", "amber", "green"] as Status[]).map((st) => (
              <button key={st} aria-pressed={only === st} onClick={() => setOnly(only === st ? null : st)}>
                {COUNT_LABEL[st]} <span className="n num">{counts[st]}</span>
              </button>
            ))}
          </div>

          <div className="toolbar">
            <select className="select select-sm" value={buyer} onChange={(e) => setFilter("buyer", e.target.value)} aria-label="Buyer">
              <option value="">All buyers</option>
              {meta?.buyers.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <select className="select select-sm" value={unit} onChange={(e) => setFilter("unit", e.target.value)} aria-label="Unit">
              <option value="">All units</option>
              {meta?.units.filter((u) => u.kind === "own").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
            <select className="select select-sm" value={week} onChange={(e) => setFilter("week", e.target.value)} aria-label="Ship week">
              <option value="">All ship weeks</option>
              {data?.weeks.map((w) => <option key={w} value={w}>Ship week {w.split("-W")[1]} · {w.slice(0, 4)}</option>)}
            </select>
            <span className="toolbar-sep" aria-hidden="true" />
            {([["soon", "Ships in 7 days"], ["messages", "Needs a reply"], ["materials", "Late materials"]] as [string, string][]).map(([k, label]) => (
              <button key={k} className={`chip${focus === k ? " on" : ""}`} aria-pressed={focus === k} onClick={() => setFilter("focus", focus === k ? "" : k)}>{label}</button>
            ))}
            {FOCUS[focus] && !["soon", "messages", "materials"].includes(focus) && (
              <span className="chip-filter">{FOCUS[focus].label}<button aria-label="Show all orders" onClick={() => setFilter("focus", "")}>×</button></span>
            )}
            {filtered && <button className="btn btn-ghost btn-sm" onClick={() => { setParams({}, { replace: true }); setOnly(null); }}>Clear filters</button>}
            {loading && <span className="faint small">Updating…</span>}
          </div>

          {error && <div className="banner banner-error">{error}</div>}
          {!data && !error && <Skeleton rows={5} />}
          {data && orders.length === 0 && <EmptyState title="No orders match" hint="Clear a filter to see more." action={<button className="btn btn-sm" onClick={() => { setParams({}, { replace: true }); setOnly(null); }}>Clear filters</button>} />}

          {orders.length > 0 && (
            <>
              <div className="card board-wrap">
                <table className="board">
                  <thead>
                    <tr>{sortable("order", "Order")}<th>Buyer</th>{sortable("exFactory", "Ex-factory")}{sortable("progress", "Now")}<th>Status</th></tr>
                  </thead>
                  <tbody>
                    {orders.map((o) => (
                      <tr key={o.id} onClick={() => nav(`/m/orders/${o.id}`)}>
                        <td>
                          <Link to={`/m/orders/${o.id}`} className="po" onClick={(e) => e.stopPropagation()}>{o.poNo}</Link>
                          <div className="muted">{o.style} · <Swatch hex={o.colourHex} />{o.colour.toLowerCase()}</div>
                          <div className="faint small num">{num(o.qty)} pcs · {o.unit}</div>
                        </td>
                        <td>{o.buyer}</td>
                        <td className="nowrap"><ExFactory o={o} /></td>
                        <td><StageCell o={o} /></td>
                        <td>
                          <StatusPill status={o.status} />
                          <Flags o={o} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="card board-mobile">
                {orders.map((o) => (
                  <Link key={o.id} to={`/m/orders/${o.id}`} className="order-tile">
                    <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
                      <b>{o.poNo}</b>
                      <StatusPill status={o.status} />
                    </div>
                    <div className="muted">{o.style} · {o.buyer}</div>
                    <div className="small faint num">Ex-factory <ExFactoryInline o={o} /></div>
                    <Flags o={o} />
                  </Link>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
