import { Link } from "react-router-dom";
import { EmptyState, PageHeader, Skeleton, useApi } from "../../components/ui";
import { fmtDate, plural } from "../../lib/format";

interface Delivery {
  shipped: number; late: number; onTime: number; latePct: number | null; averageDaysLate: number; targetPct: number; baselinePct: number;
  orders: { id: number; poNo: string; style: string; buyer: string; exFactory: string; shippedDate: string; daysLate: number; verdict: string }[];
}
interface Warnings {
  warned: number; earlyEnough: number; averageLeadDays: number | null; targetDays: number;
  orders: { id: number; poNo: string; buyer: string; level: string; warnedOn: string; exFactory: string; leadDays: number; state: string }[];
}
interface Floor { today: string; sentToday: number; total: number; supervisors: { name: string; unit: string | null; updatesToday: number; daysThisWeek: number; lastUpdate: string | null }[] }
interface Views { week: number; month: number; buyers: { buyer: string; week: number; month: number; lastSeen: string | null }[] }
interface Reports { today: string; delivery: Delivery; warnings: Warnings; floor: Floor; buyers: Views }

/** The numbers that show whether LoomTrack is doing what the client bought it for. */
export default function ReportsPage() {
  const { data, error } = useApi<Reports>("/api/m/reports");
  if (error) return <main className="page"><div className="banner banner-error">{error}</div></main>;
  if (!data) return <main className="page"><Skeleton rows={6} /></main>;
  const { delivery: d, warnings: w, floor: f, buyers: v } = data;

  return (
    <main className="page">
      <div className="stack" style={{ gap: 24 }}>
        <PageHeader title="Reports" sub="Are orders shipping on time, are warnings early enough, are supervisors sending numbers, are buyers looking for themselves." />

        <section className="card">
          <div className="card-head"><div><h2>Shipped on time</h2><div className="faint small">Shipped orders against their ex-factory date. The goal is {d.targetPct}% late or fewer; the client is at {d.baselinePct}% today.</div></div></div>
          <div className="card-body stack">
            {d.shipped === 0 ? (
              <EmptyState title="No shipped orders yet" hint="When an order leaves the factory, open it and press Mark shipped with the date. It counts here from then on." />
            ) : (
              <>
                <div className="kv">
                  <div><span>Late</span><b className={`num ${d.latePct !== null && d.latePct > d.targetPct ? "t-red" : "t-green"}`}>{d.latePct}%</b></div>
                  <div><span>Shipped</span><b className="num">{d.shipped}</b></div>
                  <div><span>On time or early</span><b className="num">{d.onTime}</b></div>
                  <div><span>Late, on average</span><b className="num">{d.late ? plural(Math.round(d.averageDaysLate), "day") : "none late"}</b></div>
                </div>
                <div className="table-scroll"><table className="table rows-link">
                  <thead><tr><th>Order</th><th>Buyer</th><th>Due</th><th>Shipped</th><th>Result</th></tr></thead>
                  <tbody>{d.orders.map((o) => (
                    <tr key={o.id}>
                      <td><Link to={`/m/orders/${o.id}`} className="po">{o.poNo}</Link><div className="muted small">{o.style}</div></td>
                      <td>{o.buyer}</td><td className="nowrap num">{fmtDate(o.exFactory, true)}</td><td className="nowrap num">{fmtDate(o.shippedDate, true)}</td>
                      <td><span className={`pill ${o.daysLate > 0 ? "pill-red" : "pill-green"}`}>{o.verdict}</span></td>
                    </tr>
                  ))}</tbody>
                </table></div>
              </>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head"><div><h2>How early the warning came</h2><div className="faint small">Days between the first delay warning on an order and its ex-factory date. The goal is {w.targetDays} days or more, not two days.</div></div></div>
          <div className="card-body stack">
            {w.warned === 0 ? (
              <EmptyState title="No delay warnings yet" hint="A warning appears when an order is running behind plan." />
            ) : (
              <>
                <div className="kv">
                  <div><span>Average notice</span><b className={`num ${w.averageLeadDays !== null && w.averageLeadDays >= w.targetDays ? "t-green" : "t-amber"}`}>{plural(Math.round(w.averageLeadDays ?? 0), "day")}</b></div>
                  <div><span>{w.targetDays}+ days ahead</span><b className="num">{w.earlyEnough} of {w.warned} orders</b></div>
                </div>
                <div className="table-scroll"><table className="table rows-link">
                  <thead><tr><th>Order</th><th>Buyer</th><th>First warned</th><th>Ex-factory</th><th>Notice</th></tr></thead>
                  <tbody>{w.orders.map((o) => (
                    <tr key={o.id}>
                      <td><Link to={`/m/orders/${o.id}`} className="po">{o.poNo}</Link></td><td>{o.buyer}</td>
                      <td className="nowrap num">{fmtDate(o.warnedOn, true)}</td><td className="nowrap num">{fmtDate(o.exFactory, true)}</td>
                      <td><span className={`pill ${o.leadDays >= w.targetDays ? "pill-green" : o.leadDays >= 7 ? "pill-amber" : "pill-red"}`}>{plural(Math.max(o.leadDays, 0), "day")}</span></td>
                    </tr>
                  ))}</tbody>
                </table></div>
              </>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head"><div><h2>Supervisors sending numbers</h2><div className="faint small">{f.sentToday} of {f.total} supervisors have sent an update on {fmtDate(f.today, true)}.</div></div></div>
          <div className="card-body">
            <div className="table-scroll"><table className="table">
              <thead><tr><th>Supervisor</th><th>Unit</th><th>Today</th><th>Days with an update, last 7</th><th>Last update</th></tr></thead>
              <tbody>{f.supervisors.map((s) => (
                <tr key={s.name}>
                  <td>{s.name}</td><td className="muted">{s.unit ?? "—"}</td>
                  <td>{s.updatesToday ? <span className="pill pill-green">{plural(s.updatesToday, "update")}</span> : <span className="pill pill-amber">None yet</span>}</td>
                  <td className="num">{s.daysThisWeek} of 7</td><td className="nowrap num">{s.lastUpdate ? fmtDate(s.lastUpdate, true) : "Never"}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </div>
        </section>

        <section className="card">
          <div className="card-head"><div><h2>Buyers looking for themselves</h2><div className="faint small">How often each buyer opened their own page: {plural(v.week, "visit")} in the last 7 days, {plural(v.month, "visit")} in 30. Every visit is a status email they did not need to send.</div></div></div>
          <div className="card-body">
            <div className="table-scroll"><table className="table">
              <thead><tr><th>Buyer</th><th>Last 7 days</th><th>Last 30 days</th><th>Last seen</th></tr></thead>
              <tbody>{v.buyers.map((b) => (
                <tr key={b.buyer}><td>{b.buyer}</td><td className="num">{b.week}</td><td className="num">{b.month}</td><td className="nowrap num">{b.lastSeen ? fmtDate(b.lastSeen, true) : "Never"}</td></tr>
              ))}</tbody>
            </table></div>
          </div>
        </section>
      </div>
    </main>
  );
}
