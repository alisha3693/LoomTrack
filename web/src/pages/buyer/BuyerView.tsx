import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { Progress, Swatch, useApi } from "../../components/ui";
import { FileList } from "../../components/Attachments";
import { RequestPill } from "../../components/RequestParts";
import type { FileItem } from "../../lib/types";
import type { RequestRow } from "../../lib/requests";
import { fmtDate, fmtDateTime, num } from "../../lib/format";
import { ThemeToggle } from "../../lib/theme";

interface BuyerOrder {
  id: number;
  poNo: string;
  style: string;
  colour: string;
  colourHex: string | null;
  colourPantone: string | null;
  qty: number;
  sizes: { size: string; qty: number }[];
  exFactory: string;
  state: string;
  notice: { message: string; expectedExFactory: string; at: string } | null;
  overallPct: number;
  milestones: { code: string; name: string; kind: "milestone" | "stage"; plannedDate: string; actualDate: string | null; pct: number; done: number | null }[];
  attachments: FileItem[];
  photos: { id: number; date: string; stage: string }[];
  dateChanges: { field: string; oldValue: string | null; newValue: string | null; reason: string; changedAt: string; milestone: string | null }[];
}

interface View {
  buyer: { name: string; country: string | null };
  today: string;
  orders: BuyerOrder[];
}

/** Requests this buyer has sent, with a way to send a new one. */
function MyRequests({ token }: { token: string }) {
  const { data } = useApi<{ requests: RequestRow[] }>(`/api/b/${token}/requests`);
  return (
    <section className="card no-print" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <div>
          <h2>Order requests</h2>
          <div className="faint small">Need something made? Send a request and we will confirm it.</div>
        </div>
        <Link className="btn btn-primary" to={`/b/${token}/requests/new`}>New order request</Link>
      </div>
      {data && data.requests.length > 0 && (
        <div className="table-scroll">
          <table className="table">
            <tbody>
              {data.requests.map((r) => (
                <tr key={r.id}>
                  <td><Link to={`/b/${token}/requests/${r.id}`}><b>{r.poNo}</b></Link>{r.kind === "amendment" ? <span className="pill" style={{ marginLeft: 8 }}>Change</span> : null} <span className="faint small">{r.requestNo}</span><div className="muted">{r.style}, {r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div></td>
                  <td className="muted">Ex-factory {fmtDate(r.exFactory, true)}</td>
                  <td><RequestPill status={r.status} audience="buyer" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const FIELD: Record<string, string> = { ex_factory: "Ex-factory", planned_date: "Due date", planned_start: "Start date", actual_date: "Completed" };

export default function BuyerView() {
  const { token } = useParams();
  const { data, error } = useApi<View>(`/api/b/${token}`);

  useEffect(() => {
    document.documentElement.lang = "en";
    if (data) document.title = `${data.buyer.name} · Order status`;
  }, [data]);

  if (error) return <div className="login-wrap"><div className="card card-pad" style={{ maxWidth: 420 }}>{error}</div></div>;
  if (!data) return <div className="login-wrap faint">Loading…</div>;

  return (
    <div className="shell">
      <header className="buyer-head">
        <div className="inner">
          <div>
            <div className="faint small">Production status · updated daily from the factory floor</div>
            <h1>{data.buyer.name}</h1>
          </div>
          <div className="row no-print">
            <a className="btn" href={`/api/b/${token}/weekly.xlsx`}>Weekly status (Excel)</a>
            <button className="btn btn-ghost" onClick={() => window.print()}>Print / PDF</button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="page" style={{ maxWidth: 980 }}>
        <MyRequests token={token!} />
        <p className="faint small" style={{ marginBottom: 16 }}>As of {fmtDate(data.today, true)} · {data.orders.length} orders</p>
        <div className="stack" style={{ gap: 20 }}>
          {data.orders.map((o) => (
            <article key={o.id} className="card">
              <div className="card-head" style={{ alignItems: "flex-start" }}>
                <div>
                  <h2>{o.poNo}</h2>
                  <div className="muted">{o.style}, <Swatch hex={o.colourHex} />{o.colour.toLowerCase()}{o.colourPantone ? ` (Pantone ${o.colourPantone})` : ""} · {num(o.qty)} pcs</div>
                  <div className="faint small">{o.sizes.map((s) => `${s.size} ${num(s.qty)}`).join(" · ")}</div>
                  {o.state === "active" && <div className="no-print" style={{ marginTop: 6 }}><Link className="small" to={`/b/${token}/orders/${o.id}/change`}>Ask for a change</Link></div>}
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="faint small">Ex-factory</div>
                  <b className="num">{fmtDate(o.exFactory, true)}</b>
                  {o.notice && <div className="small t-red num">Expected {fmtDate(o.notice.expectedExFactory, true)}</div>}
                </div>
              </div>

              <div className="card-body stack">
                {o.notice && (
                  <div className="banner banner-warn">
                    <b>Update from your merchandiser</b> · {fmtDateTime(o.notice.at)}
                    <div style={{ marginTop: 4, color: "var(--ink)" }}>{o.notice.message}</div>
                  </div>
                )}

                <div>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                    <span className="section-title" style={{ margin: 0 }}>Packed</span>
                    <b className="num">{o.overallPct}%</b>
                  </div>
                  <Progress pct={o.overallPct} />
                </div>

                <div className="grid-2" style={{ alignItems: "start" }}>
                  <div>
                    <div className="section-title">Production</div>
                    <div className="stack" style={{ gap: 10 }}>
                      {o.milestones.filter((m) => m.kind === "stage").map((m) => (
                        <div key={m.code}>
                          <div className="row small" style={{ justifyContent: "space-between" }}>
                            <span>{m.name}</span>
                            <span className="num muted">{m.done !== null ? num(m.done) : ""} · {m.pct}%</span>
                          </div>
                          <Progress pct={m.pct} tone={m.pct >= 100 ? "green" : ""} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
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
                  </div>
                </div>

                {o.attachments.length > 0 && (
                  <div>
                    <div className="section-title">Files</div>
                    <FileList files={o.attachments} hrefFor={(f) => `/api/b/${token}/attachments/${f.id}`} />
                  </div>
                )}

                {o.photos.length > 0 && (
                  <div>
                    <div className="section-title">From the floor</div>
                    <div className="photo-grid">
                      {o.photos.map((ph) => (
                        <figure key={ph.id}>
                          <a href={`/api/b/${token}/photos/${ph.id}`} target="_blank" rel="noreferrer">
                            <img src={`/api/b/${token}/photos/${ph.id}`} alt={`${ph.stage}, ${ph.date}`} loading="lazy" />
                          </a>
                          <figcaption>{ph.stage} · {fmtDate(ph.date)}</figcaption>
                        </figure>
                      ))}
                    </div>
                  </div>
                )}

                <details>
                  <summary className="small">Date change history ({o.dateChanges.length})</summary>
                  {o.dateChanges.length === 0 ? (
                    <p className="faint small" style={{ marginTop: 8 }}>No planned dates have changed on this order.</p>
                  ) : (
                    <ul className="reasons small" style={{ marginTop: 8 }}>
                      {o.dateChanges.map((d, i) => (
                        <li key={i}>
                          {d.milestone ?? "Order"} · {FIELD[d.field] ?? d.field}: {fmtDate(d.oldValue)} → {fmtDate(d.newValue)}
                          <span className="faint"> · “{d.reason}” · {fmtDateTime(d.changedAt)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </details>
              </div>
            </article>
          ))}
        </div>
      </main>
    </div>
  );
}
