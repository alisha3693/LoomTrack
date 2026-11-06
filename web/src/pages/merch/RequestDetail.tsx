import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { addDaysIso } from "../../lib/format";
import { OfficeFiles } from "../../components/Attachments";
import { Modal, Toast, useApi } from "../../components/ui";
import { RequestPill, RequestSummary, RequestThread } from "../../components/RequestParts";
import type { RequestDetailData } from "../../lib/requests";
import { useMeta, useReloadMeta } from "./OfficeShell";

type Dialog = "query" | "counter" | "accept" | "decline" | null;

export default function RequestDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const meta = useMeta();
  const reloadMeta = useReloadMeta();
  const { data: r, error, reload } = useApi<RequestDetailData>(`/api/m/requests/${id}`);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [message, setMessage] = useState("");
  const [date, setDate] = useState("");
  const [unitId, setUnitId] = useState("");
  const [templateKey, setTemplateKey] = useState("basic");
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  return (
    <main className="page page-narrow">
      <Link to="/m/requests" className="small muted">← All requests</Link>
      <div className="page-head" style={{ marginTop: 6 }}>
        <div>
          <div className="row"><h1>{r.poNo}</h1><RequestPill status={r.status} audience="office" /></div>
          <p className="sub">{r.buyer} · {r.requestNo}{r.orderNo ? ` · became order ${r.orderNo}` : ""}</p>
        </div>
        {r.orderId && <Link className="btn" to={`/m/orders/${r.orderId}`}>Open the order</Link>}
      </div>

      <div className="stack">
        <section className="card card-pad"><RequestSummary r={r} /></section>

        <section className="card card-pad stack">
          <h2>Files</h2>
          <OfficeFiles files={r.attachments} uploadPath={`/api/m/requests/${r.id}/attachments`} onChanged={() => void reload()} />
        </section>

        {open && (
          <section className="card card-pad row">
            <button className="btn btn-primary" onClick={() => openDialog("accept")}>{r.kind === "amendment" ? "Apply the change" : "Accept into an order"}</button>
            <button className="btn" onClick={() => openDialog("query")}>Ask a question</button>
            <button className="btn" onClick={() => openDialog("counter")}>Propose another date</button>
            <button className="btn btn-ghost" onClick={() => openDialog("decline")}>Decline</button>
            {r.status !== "submitted" && <span className="faint small">The buyer has not answered yet. You can still act.</span>}
          </section>
        )}

        <h2>History</h2>
        <RequestThread r={r} audience="office" />
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
        <Modal title="Accept into an order" onClose={() => setDialog(null)}>
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
            <label className="field"><span>Note to the buyer (optional)</span>
              <textarea className="textarea" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Leave empty to send the standard confirmation" />
            </label>
            {formError && <div className="banner banner-error">{formError}</div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !unitId} onClick={() => send("accept", { unitId: Number(unitId), templateKey, message: message.trim() || null }, "")}>Create order</button>
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
