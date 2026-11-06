import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { OfficeFiles } from "../../components/Attachments";
import ChangeForm from "../../components/ChangeForm";
import AnchorNav from "../../components/AnchorNav";
import Conversation from "../../components/Conversation";
import Materials from "../../components/Materials";
import { RequestPill } from "../../components/RequestParts";
import { fabricLine } from "../../lib/fabric";
import { Modal, Progress, StatusPill, Swatch, Toast, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDate, fmtDateTime, num, plural, Status } from "../../lib/format";
import type { MilestoneRow, OrderDetail as Detail, StageProjection, UpdateRow, WarningRow } from "../../lib/types";
import { useMeta } from "./OfficeShell";

type DateEdit = { kind: "exf"; current: string } | { kind: "ms"; m: MilestoneRow; field: "plannedDate" | "plannedStart"; current: string };

export default function OrderDetail() {
  const { id } = useParams();
  const { data, error, reload } = useApi<Detail>(`/api/m/orders/${id}`);
  const [edit, setEdit] = useState<DateEdit | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);

  if (error) return <main className="page"><div className="banner banner-error">{error}</div></main>;
  if (!data) return <main className="page faint">Loading…</main>;
  const { order, projection: p } = data;
  const pending = data.warnings.find((w) => w.state === "pending");
  const lastMessage = data.messages[data.messages.length - 1];
  const awaiting = lastMessage?.author === "buyer";
  const lateMaterials = data.materials.filter((m) => m.risk.state === "late").length;
  const confirmed = data.warnings.find((w) => w.state === "confirmed");

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      setToast(msg);
      await reload();
    } catch (e) {
      setToast((e as Error).message);
    }
  };

  return (
    <main className="page">
      <div className="stack" style={{ gap: 20 }}>
        <div>
          <div className="crumbs"><Link to="/m">Orders</Link><i>/</i><span>{order.po_no}</span></div>
          <div className="page-head" style={{ marginTop: 6, marginBottom: 0 }}>
            <div>
              <div className="row"><h1>{order.po_no}</h1><StatusPill status={p.status} /></div>
              <p className="sub">{order.order_no} · {order.style}, <Swatch hex={order.colour_hex} />{order.colour.toLowerCase()}{order.colour_pantone ? ` (Pantone ${order.colour_pantone})` : ""} · <Link to={`/m?buyer=${order.buyer_id}`} title="All orders for this buyer">{order.buyer_name}</Link> · {order.unit_name}</p>
            </div>
            <div className="row no-print">
              {data.buyerPath && <a className="btn btn-sm" href={data.buyerPath} target="_blank" rel="noreferrer" title="Opens the page your buyer sees, in a new tab">What the buyer sees ↗</a>}
              <button className="btn btn-sm" onClick={() => setRecording(true)}>Record a change</button>
              <button className="btn btn-sm" onClick={() => setEdit({ kind: "exf", current: order.ex_factory })}>Change ex-factory</button>
            </div>
          </div>
        </div>

        <AnchorNav items={[
          { id: "overview", label: "Overview" },
          { id: "messages", label: "Conversation", badge: awaiting ? <span className="badge" title="The buyer is waiting for your reply">1</span> : data.messages.length ? <span className="faint small"> {data.messages.length}</span> : null },
          { id: "delay", label: "Delay" },
          { id: "materials", label: "Materials", badge: lateMaterials ? <span className="badge" style={{ background: "var(--red-bg)", color: "var(--red)" }}>{lateMaterials}</span> : null },
          { id: "plan", label: "Plan" },
          { id: "files", label: "Files" },
          { id: "history", label: "Date history" },
          { id: "updates", label: "Floor updates" },
        ]} />

        <section id="overview" data-anchor className="card card-pad">
          <div className="kv">
            <div><span>Ex-factory</span><b className="num">{fmtDate(order.ex_factory, true)}</b></div>
            <div><span>Projected at current output</span><b className={`num t-${p.status === "red" ? "red" : p.status === "amber" ? "amber" : "green"}`}>{fmtDate(p.projectedExFactory, true)}</b></div>
            <div><span>Slack</span><b className="num">{p.slackDays < 0 ? `${plural(-p.slackDays, "working day")} late` : p.slackDays === 0 ? "On plan" : `${plural(p.slackDays, "working day")} early`}</b></div>
            <div><span>Quantity</span><b className="num">{num(order.qty_total)} pcs</b></div>
          </div>
          <div className="faint small" style={{ marginTop: 12 }}>{data.sizes.map((s) => `${s.size} ${num(s.qty)}`).join(" · ")}</div>
          {fabricLine({ type: order.fabric_type, composition: order.fabric_composition, gsm: order.fabric_gsm }) && (
            <div className="small muted" style={{ marginTop: 6 }}>
              Fabric: {fabricLine({ type: order.fabric_type, composition: order.fabric_composition, gsm: order.fabric_gsm })}{order.fabric_note ? ` · ${order.fabric_note}` : ""}
            </div>
          )}
        </section>

        {pending && <PendingWarning w={pending} onDone={(msg) => { setToast(msg); void reload(); }} />}
        {confirmed && !pending && (
          <div className="banner">
            <b>Buyer informed</b> {fmtDateTime(confirmed.decided_at)}: “{confirmed.buyer_message}”
          </div>
        )}

        <section id="messages" data-anchor className="card" style={awaiting ? { borderColor: "var(--amber)" } : undefined}>
          <div className="card-head">
            <div>
              <h2>Conversation with {order.buyer_name}</h2>
              <div className="faint small">The buyer sees this on their order page. For changing a date or quantity, use Record a change.</div>
            </div>
            {awaiting && <span className="pill pill-amber">Waiting for your reply</span>}
          </div>
          <div className="card-body">
            <Conversation path={`/api/m/orders/${order.id}/messages`} me="merchandiser" otherName={order.buyer_name} onSent={() => void reload()} hint="Ask about a sample, share an update, answer a question." />
          </div>
        </section>

        <div id="delay" data-anchor><Projection stages={p.stages} reasons={p.reasons} keyStage={p.keyStage} status={p.status} /></div>

        <div id="materials" data-anchor><Materials orderId={order.id} items={data.materials} steps={data.milestones} today={data.today} active={order.state === "active"} onChanged={reload} notify={setToast} /></div>

        <div className="grid-2" style={{ alignItems: "start" }}>
          <div id="plan" data-anchor><Milestones data={data} onEdit={setEdit} onMarkDone={(m, date) =>
            act(() => api(`/api/m/milestones/${m.id}`, { method: "PATCH", body: date ? { actualDate: date } : { clearActual: true } }), date ? `${m.name_en} marked done` : "Marked not done")
          } /></div>
          {data.changeRequests.length > 0 && (
            <section className="card">
              <div className="card-head"><h2>Requests and changes</h2><span className="faint small">What the buyer asked for and how it was answered</span></div>
              <div className="card-body">
                <ul className="reasons">
                  {data.changeRequests.map((c) => (
                    <li key={c.id}>
                      <Link to={`/m/requests/${c.id}`}><b style={{ fontWeight: 500 }}>{c.requestNo}</b></Link> · {c.kind === "amendment" ? "change" : "original request"} · <RequestPill status={c.status} audience="office" />
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          <section id="files" data-anchor className="card">
            <div className="card-head"><h2>Files</h2><span className="faint small">Designs, patterns, prints, fabric. You choose who sees each one.</span></div>
            <div className="card-body">
              <OfficeFiles files={data.attachments} uploadPath={`/api/m/orders/${order.id}/attachments`} onChanged={() => void reload()} />
            </div>
          </section>
          <div id="history" data-anchor><DateHistory data={data} /></div>
        </div>

        <div id="updates" data-anchor><Updates updates={data.updates} onChanged={reload} toast={setToast} /></div>
      </div>

      {recording && (
        <Modal title="Record a change the buyer asked for" onClose={() => setRecording(false)}>
          <p className="muted small" style={{ marginTop: 0 }}>
            Use this when the buyer asked by email or phone. It is applied now and the buyer sees it under their requests. The planned dates of the steps are not moved, so review them afterwards.
          </p>
          <ChangeForm
            currentDate={order.ex_factory}
            currentSizes={data.sizes}
            today={data.today}
            reasonLabel="What did the buyer ask for, and how?"
            submitLabel="Record and apply"
            onCancel={() => setRecording(false)}
            onSubmit={async (body) => {
              await api(`/api/m/orders/${order.id}/amend`, { body });
              setRecording(false);
              setToast("Change recorded and applied");
              await reload();
            }}
          />
        </Modal>
      )}
      {edit && <DateModal edit={edit} orderId={order.id} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); setToast("Date changed and recorded"); void reload(); }} />}
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}

function PendingWarning({ w, onDone }: { w: WarningRow; onDone: (msg: string) => void }) {
  const [message, setMessage] = useState(w.buyer_message ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = async (path: string, body?: unknown) => {
    setBusy(true);
    setErr(null);
    try {
      await api(path, { method: "POST", body });
      onDone(path.endsWith("confirm") ? "Warning confirmed and sent to the buyer" : "Warning dismissed");
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <section className={`warning-card ${w.level}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{w.level === "red" ? "Delay warning: ex-factory at risk" : "Early warning: behind plan"}</h2>
        <span className="small muted">Not visible to the buyer until you confirm</span>
      </div>
      <p className="muted" style={{ marginTop: 6 }}>{w.summary}</p>
      <label className="field" style={{ marginTop: 12 }}>
        <span>Message to the buyer</span>
        <textarea className="textarea" value={message} onChange={(e) => setMessage(e.target.value)} />
      </label>
      {err && <p className="error-text" style={{ marginTop: 6 }}>{err}</p>}
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary" disabled={busy || message.trim().length < 10} onClick={() => go(`/api/m/warnings/${w.id}/confirm`, { message })}>Confirm &amp; send to buyer</button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => go(`/api/m/warnings/${w.id}/dismiss`)}>Dismiss</button>
      </div>
    </section>
  );
}

function Projection({ stages, reasons, keyStage, status }: { stages: StageProjection[]; reasons: string[]; keyStage: string | null; status: Status }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Delay projection</h2>
        <span className="faint small">Run rate = average of the last 7 working days</span>
      </div>
      {reasons.length > 0 && (
        <div className="card-body" style={{ borderBottom: "1px solid var(--line)" }}>
          <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th style={{ paddingLeft: 20 }}>Stage</th><th style={{ width: 200 }}>Done</th><th>Plan ends</th><th className="r">Need / day</th><th className="r">Making / day</th><th>Projected finish</th><th className="r" style={{ paddingRight: 20 }}>Slip</th></tr>
          </thead>
          <tbody>
            {stages.map((s) => {
              const tone = s.state === "done" ? "green" : s.slipDays > 0 ? (s.code === keyStage && status !== "green" ? status : "amber") : "";
              return (
                <tr key={s.code}>
                  <td style={{ paddingLeft: 20 }}><b style={{ fontWeight: s.code === keyStage ? 600 : 500 }}>{s.name}</b></td>
                  <td>
                    <div className="small num" style={{ marginBottom: 4 }}>{num(s.done)} <span className="faint">· {s.pct}%</span></div>
                    <Progress pct={s.pct} tone={tone as "green" | "amber" | "red" | ""} />
                  </td>
                  <td className="num nowrap">{fmtDate(s.plannedEnd, true)}</td>
                  <td className="r num">{s.state === "done" ? "—" : s.requiredPerDay === null ? <span className="t-red">overdue</span> : num(s.requiredPerDay)}</td>
                  <td className="r num">
                    {s.state === "done" ? "—" : (
                      <>
                        {num(s.runRate)}
                        <div className="faint small">{s.rateBasis === "planned" ? "planned capacity" : s.constrainedByUpstream ? "waiting on upstream" : `${s.rateWindowDays}-day avg`}</div>
                      </>
                    )}
                  </td>
                  <td className="num nowrap">{s.state === "done" ? <span className="t-green">Done</span> : s.projectedFinish.startsWith("9999") ? <span className="t-red">stalled</span> : fmtDate(s.projectedFinish, true)}</td>
                  <td className={`r num ${s.slipDays > 0 && s.state !== "done" ? "t-red" : "faint"}`} style={{ paddingRight: 20 }}>
                    {s.state === "done" ? "" : s.slipDays >= 999 ? "—" : s.slipDays > 0 ? `+${s.slipDays}d` : s.slipDays < 0 ? `${s.slipDays}d` : "0"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Milestones({ data, onEdit, onMarkDone }: { data: Detail; onEdit: (e: DateEdit) => void; onMarkDone: (m: MilestoneRow, date: string | null) => void }) {
  const stageByCode = new Map(data.projection.stages.map((s) => [s.code, s]));
  return (
    <section className="card">
      <div className="card-head"><h2>Time-and-action plan</h2></div>
      <div className="card-body" style={{ paddingTop: 4, paddingBottom: 4 }}>
        <ul className="timeline">
          {data.milestones.map((m) => {
            const s = stageByCode.get(m.code);
            const done = m.actual_date || (s && s.state === "done");
            const late = !done && m.planned_date < data.today;
            return (
              <li key={m.id}>
                <span className={`check ${done ? "done" : late ? "late" : ""}`}>{done ? "✓" : ""}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 500 }}>{m.name_en}</div>
                  <div className="faint small">
                    {m.kind === "stage" ? `${m.unit_name ?? ""} · ${s ? `${s.pct}%` : ""}` : m.actual_date ? `Done ${fmtDate(m.actual_date)}` : late ? <span className="t-red">Overdue</span> : "Milestone"}
                  </div>
                </div>
                <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                  <button className="btn btn-ghost btn-sm num" title="Change planned date" disabled={m.code === "EXF"}
                    onClick={() => onEdit({ kind: "ms", m, field: "plannedDate", current: m.planned_date })}>
                    {fmtDate(m.planned_date, true)}
                  </button>
                  {m.kind === "milestone" && m.code !== "EXF" && (
                    m.actual_date
                      ? <button className="btn btn-ghost btn-sm" onClick={() => onMarkDone(m, null)}>Undo</button>
                      : <button className="btn btn-sm" onClick={() => onMarkDone(m, data.today)}>Mark done</button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

const FEED_LIMIT = 12;
const FIELD_LABEL: Record<string, string> = { ex_factory: "Ex-factory", planned_date: "Due date", planned_start: "Start date", actual_date: "Done date" };

function DateHistory({ data }: { data: Detail }) {
  return (
    <section className="card">
      <div className="card-head"><h2>Date change history</h2><span className="faint small">Visible to the buyer</span></div>
      <div className="card-body">
        {data.dateChanges.length === 0 ? (
          <p className="faint">No date changes yet. Every change is recorded here with its reason and cannot be edited.</p>
        ) : (
          <ul className="reasons">
            {data.dateChanges.map((d) => (
              <li key={d.id}>
                <b style={{ fontWeight: 500 }}>{d.milestone ?? "Order"} · {FIELD_LABEL[d.field] ?? d.field}</b>: {fmtDate(d.old_value)} → {fmtDate(d.new_value)}
                <div className="faint small">“{d.reason}” · {d.changed_by_name ?? "—"} · {fmtDateTime(d.changed_at)}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function Updates({ updates, onChanged, toast }: { updates: UpdateRow[]; onChanged: () => void; toast: (m: string) => void }) {
  const meta = useMeta();
  const [showAll, setShowAll] = useState(false);
  const reasonLabel = (code: string | null) => meta?.reasons.find((r) => r.code === code)?.en ?? code ?? "";

  const setCategory = async (u: UpdateRow, category: string) => {
    try {
      await api(`/api/m/reasons/${u.id}`, { method: "PATCH", body: { category } });
      toast(`Reason set to “${reasonLabel(category)}”`);
      onChanged();
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const setVisible = async (photoId: number, buyerVisible: boolean) => {
    await api(`/api/m/photos/${photoId}`, { method: "PATCH", body: { buyerVisible } }).catch(() => {});
    onChanged();
  };

  return (
    <section className="card">
      <div className="card-head"><h2>Floor updates</h2><span className="faint small">Latest first</span></div>
      <div className="card-body" style={{ paddingTop: 0, paddingBottom: 0 }}>
        {updates.length === 0 && <p className="faint" style={{ padding: "16px 0" }}>No updates from the floor yet.</p>}
        {updates.slice(0, showAll ? undefined : FEED_LIMIT).map((u) => !u.has_reason && u.photos.length === 0 ? (
          <div key={u.id} className="update update-compact">
            <div className="num">{fmtDate(u.work_date, true)}</div>
            <div><b className="num">+{num(u.qty)}</b> <span className="muted">{u.stage}</span> <span className="faint small">· {u.supervisor}</span></div>
          </div>
        ) : (
          <div key={u.id} className="update">
            <div>
              <div style={{ fontWeight: 500 }} className="num">{fmtDate(u.work_date, true)}</div>
              <div className="faint small">{u.supervisor}</div>
            </div>
            <div style={{ minWidth: 0 }}>
              <div><b className="num">+{num(u.qty)}</b> <span className="muted">{u.stage}</span></div>
              {u.has_reason ? (
                <>
                  <div className="note-pair">
                    <div>
                      <div className="section-title" style={{ marginBottom: 4 }}>Supervisor wrote{u.note_source === "voice" ? " (voice)" : ""}</div>
                      <div className="ta">{u.note_text ?? <span className="faint">Voice note only</span>}</div>
                      {u.audio_url && <audio controls preload="none" src={u.audio_url} style={{ width: "100%", marginTop: 8, height: 32 }} />}
                    </div>
                    <div>
                      <div className="section-title" style={{ marginBottom: 4 }}>
                        {u.ai_source === "ollama" ? "AI translation" : u.ai_source === "keywords" ? "Keyword match (no translation)" : "Not classified yet"}
                      </div>
                      <div>{u.ai_translation ?? <span className="faint">{u.note_text ? "No translation available" : "Listen and set the reason"}</span>}</div>
                      <div className="row" style={{ marginTop: 8, gap: 8 }}>
                        <select className="select select-sm" style={{ width: "auto", maxWidth: "100%" }} value={u.final_category ?? ""} onChange={(e) => setCategory(u, e.target.value)} aria-label="Reason">
                          <option value="" disabled>Set reason…</option>
                          {meta?.reasons.map((r) => <option key={r.code} value={r.code}>{r.en}</option>)}
                        </select>
                        {u.changed_at ? (
                          <span className="small faint">Set by merchandiser{u.ai_category && u.ai_category !== u.final_category ? ` · AI said “${reasonLabel(u.ai_category)}”` : ""}</span>
                        ) : u.ai_source ? (
                          <span className="small faint">{u.ai_source === "ollama" ? "AI guess, check it" : "Keyword guess, check it"}</span>
                        ) : null}
                      </div>
                      {u.ai_error && <div className="small t-amber" style={{ marginTop: 4 }} title={u.ai_error}>Local AI unavailable, used keywords</div>}
                    </div>
                  </div>
                </>
              ) : null}
              {u.photos.length > 0 && (
                <div className="thumbs">
                  {u.photos.map((ph) => (
                    <div key={ph.id} className="thumb">
                      <a href={ph.url} target="_blank" rel="noreferrer"><img src={ph.url} alt={`${u.stage} photo`} loading="lazy" /></a>
                      <label title="Show this photo on the buyer link">
                        <input type="checkbox" checked={ph.buyerVisible} onChange={(e) => setVisible(ph.id, e.target.checked)} /> buyer
                      </label>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {!showAll && updates.length > FEED_LIMIT && (
          <div style={{ padding: "12px 0" }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowAll(true)}>Show all {updates.length} updates</button>
          </div>
        )}
      </div>
    </section>
  );
}

function DateModal({ edit, orderId, onClose, onSaved }: { edit: DateEdit; orderId: number; onClose: () => void; onSaved: () => void }) {
  const [date, setDate] = useState(edit.current);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const title = edit.kind === "exf" ? "Change ex-factory date" : `Change due date · ${edit.m.name_en}`;

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      if (edit.kind === "exf") await api(`/api/m/orders/${orderId}/ex-factory`, { method: "PATCH", body: { date, reason } });
      else await api(`/api/m/milestones/${edit.m.id}`, { method: "PATCH", body: { [edit.field]: date, reason } });
      onSaved();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form className="stack" onSubmit={save}>
        <label className="field"><span>New date</span><input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} required /></label>
        <label className="field"><span>Reason (buyers' compliance teams see this)</span><textarea className="textarea" value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} required placeholder="e.g. Buyer approved new ship window, email 4 Nov" /></label>
        {err && <p className="error-text">{err}</p>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={date === edit.current}>Save change</button>
        </div>
      </form>
    </Modal>
  );
}
