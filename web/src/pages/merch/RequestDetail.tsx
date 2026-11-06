import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { refreshBadges } from "../../lib/badges";
import { addDaysIso, fmtDate, plural } from "../../lib/format";
import { OfficeFiles } from "../../components/Attachments";
import CapacityCheck, { blocks } from "../../components/CapacityCheck";
import type { UnitFit } from "../../lib/fabric";
import { Modal, Toast, useApi } from "../../components/ui";
import { RequestPill, RequestSummary, RequestThread } from "../../components/RequestParts";
import type { RequestDetailData } from "../../lib/requests";
import type { BoardOrder } from "../../lib/types";
import { useMeta, useReloadMeta } from "./OfficeShell";

/** What the merchandiser should know about this buyer before deciding: their live orders and how they are going. */
function BuyerContext({ buyerId, buyer }: { buyerId: number; buyer: string }) {
  const { data } = useApi<{ orders: BoardOrder[] }>(`/api/m/board?buyer=${buyerId}`);
  const orders = data?.orders ?? [];
  const count = (s: string) => orders.filter((o) => o.status === s).length;
  const waiting = orders.filter((o) => o.awaitingReply).length;
  return (
    <section className="card card-pad stack" style={{ gap: 10 }}>
      <h2>About {buyer}</h2>
      {!data ? <p className="faint small">Loading…</p> : orders.length === 0 ? <p className="faint small">No live orders with us yet. This would be their first.</p> : (
        <>
          <p className="muted small" style={{ margin: 0 }}>
            {plural(orders.length, "live order")}
            {count("red") ? <> · <span className="t-red">{count("red")} will miss ex-factory</span></> : null}
            {count("amber") ? <> · <span className="t-amber">{count("amber")} behind plan</span></> : null}
            {waiting ? <> · <span className="t-amber">{plural(waiting, "message")} to answer</span></> : null}
          </p>
          <div>
            {orders.slice(0, 5).map((o) => (
              <Link key={o.id} to={`/m/orders/${o.id}`} className="linkrow">
                <span><span className={`dot dot-${o.status}`} style={{ marginRight: 8 }} /><b style={{ fontWeight: 500 }}>{o.poNo}</b> <span className="faint small">{o.style}</span></span>
                <span className="faint small nowrap">{fmtDate(o.exFactory)}</span>
              </Link>
            ))}
          </div>
          <Link className="small" to={`/m?buyer=${buyerId}`}>All of {buyer}'s orders →</Link>
        </>
      )}
    </section>
  );
}

type Dialog = "query" | "counter" | "accept" | "decline" | null;

export default function RequestDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const meta = useMeta();
  const reloadMeta = useReloadMeta();
  const { data: r, error, reload } = useApi<RequestDetailData>(`/api/m/requests/${id}`);
  useEffect(() => {
    if (r) api(`/api/m/requests/${id}/read`, { method: "POST" }).then(refreshBadges).catch(() => {});
  }, [id, !!r]); // eslint-disable-line react-hooks/exhaustive-deps
  const [dialog, setDialog] = useState<Dialog>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [message, setMessage] = useState("");
  const [date, setDate] = useState("");
  const [unitId, setUnitId] = useState("");
  const [templateKey, setTemplateKey] = useState("basic");
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fit, setFit] = useState<UnitFit | null>(null);
  const [overOk, setOverOk] = useState(false);

  if (error) return <main className="page"><div className="banner banner-error">{error}</div></main>;
  if (!r) return <main className="page faint">Loading…</main>;

  const open = r.status === "submitted" || r.status === "query" || r.status === "countered";

  function openDialog(d: Dialog) {
    setDialog(d);
    setMessage("");
    setFormError(null);
    setDate(r ? addDaysIso(r.exFactory, 7) : "");
  }

  async function send(action: string, body: object, done: string) {
    setBusy(true);
    setFormError(null);
    try {
      const res = await api<{ orderId?: number }>(`/api/m/requests/${r!.id}/${action}`, { method: "POST", body });
      reloadMeta();
      if (res.orderId) return nav(`/m/orders/${res.orderId}`);
      setDialog(null);
      setToast(done);
      void reload();
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const outcome = {
    accepted: r.orderNo ? `Accepted. It became order ${r.orderNo}.` : "Accepted.",
    declined: "Declined. The buyer has the reason.",
    withdrawn: "The buyer withdrew this request.",
  }[r.status as "accepted" | "declined" | "withdrawn"];
  const hint = {
    submitted: "Accept it into an order, ask a question, or propose another date. The buyer sees your answer on their page.",
    query: "You asked a question and the buyer has not answered yet. You can still act.",
    countered: "You proposed another date and the buyer has not agreed yet. You can still act.",
  }[r.status as "submitted" | "query" | "countered"];

  return (
    <main className="page">
      <div className="crumbs"><Link to="/m/requests">Requests</Link><i>/</i><span>{r.poNo}</span></div>
      <div className="page-head" style={{ marginBottom: 14 }}>
        <div>
          <div className="row">
            <h1>{r.poNo}</h1>
            <RequestPill status={r.status} audience="office" />
            {r.kind === "amendment" && <span className="tag">Change to {r.orderNo}</span>}
          </div>
          <p className="sub">
            {r.buyerId ? <Link to={`/m?buyer=${r.buyerId}`} title="All orders for this buyer">{r.buyer}</Link> : r.buyer} · {r.requestNo}
            {r.kind !== "amendment" && r.orderNo ? ` · became order ${r.orderNo}` : ""}
          </p>
        </div>
        {r.orderId && <Link className="btn btn-primary" to={`/m/orders/${r.orderId}`}>Open the order</Link>}
      </div>

      <section className="card decision" style={open && r.status === "submitted" ? { borderColor: "var(--amber)" } : undefined} aria-label="What to do with this request">
        {open ? (
          <>
            <div className="grow">
              <b>{r.status === "submitted" ? "The buyer is waiting for your answer" : "You are waiting for the buyer"}</b>
              <div className="muted small">{hint}</div>
            </div>
            <button className="btn btn-primary" onClick={() => openDialog("accept")}>{r.kind === "amendment" ? "Apply the change" : "Accept into an order"}</button>
            <button className="btn" onClick={() => openDialog("query")}>Ask a question</button>
            <button className="btn" onClick={() => openDialog("counter")}>Propose another date</button>
            <button className="btn btn-ghost" onClick={() => openDialog("decline")}>Decline</button>
          </>
        ) : (
          <div className="grow"><b>{outcome}</b></div>
        )}
      </section>

      <div className="stack" style={{ marginTop: 20, gap: 24 }}>
        <section className="card card-pad"><RequestSummary r={r} /></section>
        <section className="stack" style={{ gap: 10 }}>
          <h2>Conversation</h2>
          <RequestThread r={r} audience="office" />
        </section>
        {r.buyerId ? <BuyerContext buyerId={r.buyerId} buyer={r.buyer ?? ""} /> : null}
        <section className="card card-pad stack">
          <h2>Files</h2>
          <OfficeFiles files={r.attachments} uploadPath={`/api/m/requests/${r.id}/attachments`} onChanged={() => void reload()} />
        </section>
      </div>

      {dialog === "accept" && r.kind === "amendment" && (
        <Modal title="Apply the change to the order" onClose={() => setDialog(null)}>
          <div className="stack">
            <p className="muted" style={{ margin: 0 }}>
              The order's ex-factory date and quantities change as shown above, and the date change goes into the order's history with this request as the reason.
              <b style={{ fontWeight: 500 }}> The planned dates of the individual steps are not moved.</b> Review them on the order afterwards.
            </p>
            <label className="field"><span>Note to the buyer (optional)</span>
              <textarea className="textarea" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Leave empty to send the standard confirmation" />
            </label>
            {formError && <div className="banner banner-error">{formError}</div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy} onClick={() => send("accept", { message: message.trim() || null }, "")}>Apply the change</button>
            </div>
          </div>
        </Modal>
      )}

      {dialog === "accept" && r.kind !== "amendment" && (
        <Modal title="Accept into an order" onClose={() => setDialog(null)} wide>
          <div className="stack">
            <p className="muted" style={{ margin: 0 }}>
              The order gets exactly what the buyer asked for: {r.totalQty.toLocaleString()} pcs, ex-factory {r.exFactory}. Pick where it is made and which plan to start from.
              You can adjust any date afterwards, with a reason.
            </p>
            <label className="field"><span>Production unit</span>
              <select className="select" value={unitId} onChange={(e) => setUnitId(e.target.value)}>
                <option value="">Choose…</option>
                {meta?.units.filter((u) => u.kind === "own").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Plan template</span>
              <select className="select" value={templateKey} onChange={(e) => setTemplateKey(e.target.value)}>
                {meta?.templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
              </select>
            </label>
            <CapacityCheck qty={r.totalQty} exFactory={r.exFactory} templateKey={templateKey} unitId={unitId}
              onPickUnit={setUnitId} onSelected={(u) => { setFit(u); setOverOk(false); }}
              onUseDate={(d) => { openDialog("counter"); setDate(d); }} />
            {blocks(fit?.verdict) && (
              <label className="row small" style={{ gap: 8, flexWrap: "nowrap", alignItems: "flex-start" }}>
                <input type="checkbox" checked={overOk} onChange={(e) => setOverOk(e.target.checked)} style={{ marginTop: 3 }} />
                <span>I have seen that {fit?.name} would be over capacity for this order, and I want to accept it anyway.</span>
              </label>
            )}
            <label className="field"><span>Note to the buyer (optional)</span>
              <textarea className="textarea" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Leave empty to send the standard confirmation" />
            </label>
            {formError && <div className="banner banner-error">{formError}</div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !unitId || (blocks(fit?.verdict) && !overOk)}
                onClick={() => send("accept", { unitId: Number(unitId), templateKey, message: message.trim() || null, overCapacityOk: blocks(fit?.verdict) && overOk }, "")}>Create order</button>
            </div>
          </div>
        </Modal>
      )}

      {(dialog === "query" || dialog === "decline" || dialog === "counter") && (
        <Modal title={dialog === "query" ? "Ask the buyer a question" : dialog === "counter" ? "Propose another ex-factory date" : "Decline this request"} onClose={() => setDialog(null)}>
          <div className="stack">
            {dialog === "counter" && (
              <label className="field"><span>Proposed ex-factory date</span>
                <input type="date" className="input" min={meta ? addDaysIso(meta.today, 1) : undefined} value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
            )}
            <label className="field"><span>{dialog === "query" ? "Your question" : dialog === "counter" ? "Reason for the new date" : "Reason"}</span>
              <textarea className="textarea" rows={4} value={message} onChange={(e) => setMessage(e.target.value)} autoFocus />
            </label>
            <p className="faint small" style={{ margin: 0 }}>The buyer sees this on their link, and a copy goes to the sent-messages list.</p>
            {formError && <div className="banner banner-error">{formError}</div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !message.trim() || (dialog === "counter" && !date)}
                onClick={() => send(dialog, dialog === "counter" ? { exFactory: date, message: message.trim() } : { message: message.trim() },
                  dialog === "query" ? "Question sent" : dialog === "counter" ? "New date proposed" : "Request declined")}>
                {dialog === "query" ? "Send question" : dialog === "counter" ? "Propose date" : "Decline request"}
              </button>
            </div>
          </div>
        </Modal>
      )}
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
