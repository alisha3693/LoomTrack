import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Empty, StatusPill, Swatch, useApi } from "../../components/ui";
import { fmtDate, fmtDateTime, num, plural, Status } from "../../lib/format";
import type { BoardOrder } from "../../lib/types";
import { useMeta } from "./OfficeShell";

const COUNT_LABEL: Record<Status, string> = { red: "will miss ex-factory", amber: "behind plan", green: "on track" };

function Pipeline({ stages }: { stages: BoardOrder["stages"] }) {
  return (
    <div className="pipeline" aria-label="Stage progress">
      {stages.map((s) => (
        <div key={s.code} className={`seg ${s.state}`} title={`${s.name}: ${s.pct}%`}>
          <i style={{ width: `${s.pct}%` }} />
        </div>
      ))}
    </div>
  );
}

/** One line of maths: what's needed vs what the floor is doing. */
function Maths({ o }: { o: BoardOrder }) {
  const k = o.keyStage;
  if (!k) return <span className="faint">All stages done</span>;
  if (k.rateBasis !== "actual") return <span className="muted">{k.name} not started · planned capacity</span>;
  const behind = k.requiredPerDay !== null && k.runRate < k.requiredPerDay;
  return (
    <span className="maths">
      <b>{k.name}</b> {k.pct}% ·{" "}
      {k.requiredPerDay === null ? (
        <span className="t-red">past planned end</span>
      ) : (
        <>
          need <b className={behind ? `t-${o.status === "green" ? "amber" : o.status}` : ""}>{num(k.requiredPerDay)}</b>/day, making{" "}
          <b>{num(k.runRate)}</b>/day
        </>
      )}
    </span>
  );
}

/** A late or at-risk material, beside the delay status (it does not change it). */
function MaterialsNote({ o }: { o: BoardOrder }) {
  const m = o.materials;
  if (!m || (m.late === 0 && m.atRisk === 0)) return null;
  return m.late > 0
    ? <div className="small t-red" style={{ marginTop: 6 }}>{plural(m.late, "material")} late</div>
    : <div className="small t-amber" style={{ marginTop: 6 }}>{plural(m.atRisk, "material")} at risk</div>;
}

export default function Board() {
  const meta = useMeta();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const buyer = params.get("buyer") ?? "";
  const unit = params.get("unit") ?? "";
  const week = params.get("week") ?? "";
  const [only, setOnly] = useState<Status | null>(null);

  const qs = new URLSearchParams(Object.entries({ buyer, unit, week }).filter(([, v]) => v)).toString();
  const { data, error, loading } = useApi<{ today: string; orders: BoardOrder[]; weeks: string[] }>(`/api/m/board${qs ? `?${qs}` : ""}`);

  const counts = useMemo(() => {
    const c = { red: 0, amber: 0, green: 0 } as Record<Status, number>;
    data?.orders.forEach((o) => c[o.status]++);
    return c;
  }, [data]);
  const orders = (data?.orders ?? []).filter((o) => !only || o.status === only);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Orders</h1>
          <p className="sub">
            Projected from the floor's daily numbers{data ? ` · ${fmtDate(data.today, true)}` : ""}. Trouble first.
          </p>
        </div>
        <Link to="/m/orders/new" className="btn btn-primary">New order</Link>
      </div>

      <div className="stack">
        <div className="summary">
          {(["red", "amber", "green"] as Status[]).map((s) => (
            <button key={s} aria-pressed={only === s} onClick={() => setOnly(only === s ? null : s)}>
              <span className={`dot dot-${s}`} style={{ alignSelf: "center" }} />
              <span className="count num">{counts[s]}</span>
              <span className="muted">{COUNT_LABEL[s]}</span>
            </button>
          ))}
        </div>

        <div className="filters">
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
          {(buyer || unit || week || only) && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setParams({}, { replace: true }); setOnly(null); }}>Clear</button>
          )}
          {loading && <span className="faint small">Updating…</span>}
        </div>

        {error && <div className="banner banner-error">{error}</div>}
        {data && orders.length === 0 && <Empty>No orders match these filters.</Empty>}

        {orders.length > 0 && (
          <>
            <div className="card board-wrap">
              <table className="board">
                <thead>
                  <tr>
                    <th className="status-cell" />
                    <th>Order</th>
                    <th>Status</th>
                    <th>Ex-factory</th>
                    <th>Where it stands</th>
                    <th>Stages</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id} onClick={() => nav(`/m/orders/${o.id}`)}>
                      <td className="status-cell"><div className={`status-bar bar-${o.status}`} /></td>
                      <td>
                        <Link to={`/m/orders/${o.id}`} className="po" onClick={(e) => e.stopPropagation()} style={{ textDecoration: "none" }}>
                          {o.poNo}
                        </Link>
                        <div className="muted">{o.style}, <Swatch hex={o.colourHex} />{o.colour.toLowerCase()} · {num(o.qty)} pcs</div>
                        <div className="faint small">{o.orderNo} · {o.buyer} · {o.unit}</div>
                      </td>
                      <td>
                        <StatusPill status={o.status} />
                        {o.pendingWarnings > 0 && <div className="small t-amber" style={{ marginTop: 6 }}>Warning to review</div>}
                        <MaterialsNote o={o} />
                      </td>
                      <td className="nowrap">
                        <div className="num">{fmtDate(o.exFactory, true)}</div>
                        {o.projectedExFactory !== o.exFactory && (
                          <div className={`small num t-${o.status === "red" ? "red" : "green"}`}>
                            → {fmtDate(o.projectedExFactory, true)}{o.slackDays < 0 ? ` (${plural(-o.slackDays, "day")} late)` : ""}
                          </div>
                        )}
                        <div className="faint small">Wk {o.shipWeek.split("-W")[1]}</div>
                      </td>
                      <td style={{ maxWidth: 360 }}>
                        <Maths o={o} />
                        {o.headline && o.status === "amber" && <div className="faint small" style={{ marginTop: 4 }}>{o.headline}</div>}
                      </td>
                      <td>
                        <Pipeline stages={o.stages} />
                        <div className="faint small" style={{ marginTop: 6 }}>
                          {o.lastUpdate ? `Updated ${fmtDateTime(o.lastUpdate)}` : "No floor updates yet"}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="board-mobile">
              {orders.map((o) => (
                <Link key={o.id} to={`/m/orders/${o.id}`} className="card order-tile">
                  <div className={`status-bar bar-${o.status}`} />
                  <div className="stack" style={{ gap: 6, flex: 1, minWidth: 0 }}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <b>{o.poNo}</b>
                      <StatusPill status={o.status} />
                    </div>
                    <div className="muted">{o.style} · {o.buyer}</div>
                    <Maths o={o} />
                    <MaterialsNote o={o} />
                    <div className="small faint">Ex-factory {fmtDate(o.exFactory, true)}{o.projectedExFactory !== o.exFactory ? ` → ${fmtDate(o.projectedExFactory)}` : ""}</div>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
