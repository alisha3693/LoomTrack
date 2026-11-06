import { Link, useParams, useSearchParams } from "react-router-dom";
import { FileList } from "../../components/Attachments";
import Conversation from "../../components/Conversation";
import { Progress, Swatch } from "../../components/ui";
import { BuyerOrder as Order, orderChip, seenKey } from "../../lib/buyer";
import { fabricLine } from "../../lib/fabric";
import { fmtDate, fmtDateTime, num } from "../../lib/format";
import { markSeen, unseen } from "../../lib/seen";
import BuyerFrame from "./BuyerFrame";

const FIELD: Record<string, string> = { ex_factory: "Ex-factory", planned_date: "Due date", planned_start: "Start date", actual_date: "Completed" };
type Tab = "progress" | "messages" | "materials" | "files" | "history";

export default function BuyerOrder() {
  const { token = "", orderId } = useParams();
  return (
    <BuyerFrame token={token} wide>
      {(_n, _t, data) => {
        const o = data.orders.find((x) => String(x.id) === orderId);
        return o ? <Detail token={token} o={o} /> : (
          <div className="card card-pad stack" style={{ alignItems: "flex-start" }}>
            <b>We could not find that order.</b>
            <Link className="btn" to={`/b/${token}/orders`}>Back to your orders</Link>
          </div>
        );
      }}
    </BuyerFrame>
  );
}

function Detail({ token, o }: { token: string; o: Order }) {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "progress";
  const setTab = (t: Tab) => setParams(t === "progress" ? {} : { tab: t }, { replace: true });
  const chip = orderChip(o);
  const fabric = fabricLine(o.fabric);
  const newReply = o.lastMessage?.author === "merchandiser" && unseen(seenKey(token, o.id), o.lastMessage.at);
  const received = o.materials.filter((m) => m.received).length;
  const owed = o.materials.filter((m) => m.suppliedBy === "buyer" && !m.received);

  const TABS: { id: Tab; label: string; extra?: React.ReactNode }[] = [
    { id: "progress", label: "Progress" },
    { id: "messages", label: "Conversation", extra: newReply ? <span className="dot-new" title="New reply" /> : o.lastMessage ? <span className="faint small"> {o.lastMessage.count}</span> : null },
    { id: "materials", label: "Materials", extra: o.materials.length ? <span className="faint small"> {received}/{o.materials.length}</span> : null },
    { id: "files", label: "Files and photos", extra: o.attachments.length + o.photos.length ? <span className="faint small"> {o.attachments.length + o.photos.length}</span> : null },
    { id: "history", label: "Date history", extra: o.dateChanges.length ? <span className="faint small"> {o.dateChanges.length}</span> : null },
  ];

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div>
        <div className="crumbs no-print"><Link to={`/b/${token}/orders`}>Orders</Link><i>/</i><span>{o.poNo}</span></div>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <div>
            <div className="row"><h1>{o.poNo}</h1><span className={`pill ${chip.tone ? `pill-${chip.tone}` : ""}`}>{chip.text}</span></div>
            <p className="sub">{o.style}, <Swatch hex={o.colourHex} />{o.colour.toLowerCase()}{o.colourPantone ? ` (Pantone ${o.colourPantone})` : ""}</p>
            {fabric && <p className="faint small">Fabric: {fabric}</p>}
          </div>
          <div className="row no-print">
            {o.state === "active" && <Link className="btn btn-sm" to={`/b/${token}/orders/${o.id}/change`} title="A new date or different quantities">Ask for a change</Link>}
            <button className="btn btn-ghost btn-sm" onClick={() => window.print()}>Print / PDF</button>
          </div>
        </div>
      </div>

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

      {o.notice && (
        <div className="banner banner-warn">
          <b>Update from your merchandiser</b> · {fmtDateTime(o.notice.at)}
          <div style={{ marginTop: 4, color: "var(--ink)" }}>{o.notice.message}</div>
          <button className="btn btn-sm" style={{ marginTop: 8 }} onClick={() => setTab("messages")}>Reply about this</button>
        </div>
      )}
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

      {tab === "messages" && (
        <section className="card card-pad stack">
          <div>
            <h2>Conversation with your merchandiser</h2>
            <p className="faint small" style={{ marginTop: 2 }}>Ask about a sample, a delivery or a detail. To change the date or the quantities, use “Ask for a change” instead.</p>
          </div>
          <Conversation
            path={`/api/b/${token}/orders/${o.id}/messages`} me="buyer" otherName="your merchandiser"
            onRead={(at) => markSeen(seenKey(token, o.id), at)} hint="Your merchandiser will answer here."
          />
        </section>
      )}

      {tab === "materials" && (
        <section className="card card-pad">
          <div className="section-title">What your order needs · {received} of {o.materials.length} received</div>
          {o.materials.length === 0 ? <p className="muted">Nothing is being tracked for this order yet.</p> : (
            <ul className="timeline">
              {o.materials.map((m) => (
                <li key={m.name} style={{ padding: "8px 0" }}>
                  <span className={`check ${m.received ? "done" : ""}`}>{m.received ? "✓" : ""}</span>
                  <span>{m.name}{m.suppliedBy === "buyer" ? <span className="tag" style={{ marginLeft: 8 }}>You supply</span> : null}</span>
                  <span className={`small num ${!m.received && m.suppliedBy === "buyer" ? "t-amber" : "muted"}`}>
                    {m.received ? `Received ${fmtDate(m.receivedDate)}` : m.suppliedBy === "buyer" ? "We are waiting for this from you" : "Not yet received"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "files" && (
        <div className="stack">
          <section className="card card-pad stack">
            <div className="section-title" style={{ margin: 0 }}>Files</div>
            {o.attachments.length === 0 ? <p className="muted" style={{ margin: 0 }}>No files on this order.</p> : <FileList files={o.attachments} hrefFor={(f) => `/api/b/${token}/attachments/${f.id}`} />}
          </section>
          <section className="card card-pad stack">
            <div className="section-title" style={{ margin: 0 }}>From the floor</div>
            {o.photos.length === 0 ? <p className="muted" style={{ margin: 0 }}>No photos shared yet. Your merchandiser chooses which floor photos you see.</p> : (
              <div className="photo-grid">
                {o.photos.map((ph) => (
                  <figure key={ph.id}>
                    <a href={`/api/b/${token}/photos/${ph.id}`} target="_blank" rel="noreferrer"><img src={`/api/b/${token}/photos/${ph.id}`} alt={`${ph.stage}, ${ph.date}`} loading="lazy" /></a>
                    <figcaption>{ph.stage} · {fmtDate(ph.date)}</figcaption>
                  </figure>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {tab === "history" && (
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
      )}
    </div>
  );
}
