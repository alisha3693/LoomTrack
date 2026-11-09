import { useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { ago, fmtDate } from "../../lib/format";
import { FileList, FileUpload } from "../../components/Attachments";
import { Toast, useApi } from "../../components/ui";
import { RequestPill, RequestSummary, RequestThread } from "../../components/RequestParts";
import type { RequestDetailData } from "../../lib/requests";
import BuyerFrame from "./BuyerFrame";

export default function BuyerRequest() {
  const { token = "", id } = useParams();
  return <BuyerFrame token={token}>{() => <Detail token={token} id={id!} />}</BuyerFrame>;
}

function Detail({ token, id }: { token: string; id: string }) {
  const { data: r, error, reload } = useApi<RequestDetailData & { orderId?: number }>(`/api/b/${token}/requests/${id}`);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState(false);
  const composer = useRef<HTMLTextAreaElement>(null);
  const uploadErrors: string[] = (useLocation().state as { uploadErrors?: string[] } | null)?.uploadErrors ?? [];

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!r) return <p className="faint">Loading…</p>;

  const proposed = [...r.messages].reverse().find((m) => m.event === "counter")?.proposedExFactory;
  const lastQuestion = [...r.messages].reverse().find((m) => m.event === "query" || m.event === "counter");

  async function act(path: string, body?: object, done?: string, method = "POST") {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/b/${token}/requests/${r!.id}/${path}`, { method, body: method === "POST" ? body ?? {} : undefined });
      setMessage("");
      if (done) setToast(done);
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const writeBack = () => { composer.current?.focus(); composer.current?.scrollIntoView({ behavior: "smooth", block: "center" }); };

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div>
        <div className="crumbs"><Link to={`/b/${token}/requests`}>Requests</Link><i>/</i><span>{r.poNo}</span></div>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <div>
            <div className="row"><h1>{r.poNo}</h1><RequestPill status={r.status} audience="buyer" /></div>
            <p className="sub">Request {r.requestNo}{r.orderNo ? ` · our order number ${r.orderNo}` : ""} · last activity {ago(r.updatedAt)}</p>
          </div>
          {r.orderId && <Link className="btn btn-primary" to={`/b/${token}/orders/${r.orderId}`}>Open your order</Link>}
          {r.canWithdraw && !sure && <button className="btn" onClick={() => setSure(true)}>Cancel request</button>}
        </div>
      </div>

      {/* Cancelling is one clear step with a way back, and it is found at the top, not inside the reply box. */}
      {r.canWithdraw && sure && (
        <section className="banner banner-warn stack" role="alertdialog" aria-label="Cancel this request?" style={{ gap: 10 }}>
          <b>Cancel request {r.requestNo}?</b>
          <span>Your merchandiser will see that you cancelled it, and no order will be made. To ask again later, send a new request.</span>
          <div className="row">
            <button className="btn btn-primary" disabled={busy} onClick={async () => { await act("withdraw", undefined, "Request cancelled"); setSure(false); }}>Yes, cancel request</button>
            <button className="btn" disabled={busy} onClick={() => setSure(false)}>Keep it</button>
          </div>
          {err && <span role="alert">{err}</span>}
        </section>
      )}

      {uploadErrors.length > 0 && (
        <div className="banner banner-error">Your request was sent, but some files could not be added: {uploadErrors.join("; ")}. You can add them again below.</div>
      )}

      {/* Whose turn it is, and the one thing to do about it, before anything else. */}
      {r.status === "countered" && proposed && (
        <section className="turn you" aria-label="Your turn">
          <span className="badge-turn" aria-hidden="true">!</span>
          <div className="stack">
            <h2>Your turn: your merchandiser proposes {fmtDate(proposed, true)}</h2>
            <p className="muted">You asked for {fmtDate(r.exFactory, true)}. Agreeing updates your request to the new date. If it does not work for you, write back and say why.</p>
            {lastQuestion?.body && <p style={{ whiteSpace: "pre-wrap" }}>“{lastQuestion.body}”</p>}
            <div className="row">
              <button className="btn btn-primary" disabled={busy} onClick={() => act("agree", undefined, "You agreed to the new date")}>Agree to {fmtDate(proposed)}</button>
              <button className="btn" onClick={writeBack}>Write back instead</button>
            </div>
          </div>
        </section>
      )}
      {r.status === "query" && (
        <section className="turn you" aria-label="Your turn">
          <span className="badge-turn" aria-hidden="true">?</span>
          <div className="stack">
            <h2>Your turn: your merchandiser has a question</h2>
            {lastQuestion?.body && <p style={{ whiteSpace: "pre-wrap" }}>“{lastQuestion.body}”</p>}
            <div className="row"><button className="btn btn-primary" onClick={writeBack}>Answer now</button></div>
          </div>
        </section>
      )}
      {r.status === "submitted" && (
        <section className="turn" aria-label="Waiting">
          <span className="badge-turn" aria-hidden="true">…</span>
          <div className="stack">
            <h2>With your merchandiser</h2>
            <p className="muted">They will confirm it, ask a question, or suggest another date. You will see the answer here and on your overview. Nothing else is needed from you.</p>
          </div>
        </section>
      )}
      {r.status === "accepted" && (
        <section className="turn done" aria-label="Accepted">
          <span className="badge-turn" aria-hidden="true">✓</span>
          <div className="stack">
            <h2>{r.kind === "amendment" ? "The change was applied" : "Accepted. It is now an order."}</h2>
            {r.orderId && <div className="row"><Link className="btn btn-primary" to={`/b/${token}/orders/${r.orderId}`}>See progress on your order</Link></div>}
          </div>
        </section>
      )}
      {r.status === "withdrawn" && (
        <section className="turn" aria-label="Cancelled">
          <span className="badge-turn" aria-hidden="true">×</span>
          <div className="stack">
            <h2>You cancelled this request</h2>
            <p className="muted">No order was made. To ask again, send a new request.</p>
            <div className="row"><Link className="btn" to={`/b/${token}/requests/new`}>Send a new request</Link></div>
          </div>
        </section>
      )}

      <section className="card card-pad"><RequestSummary r={r} /></section>

      <section className="stack" style={{ gap: 10 }}>
        <h2>Conversation</h2>
        <RequestThread r={r} audience="buyer" />
        {r.canReply && (
          <div className="card card-pad stack">
            <label className="field"><span>{r.status === "query" ? "Your answer" : "Write to your merchandiser"}</span>
              <textarea ref={composer} className="textarea" rows={3} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
            </label>
            {err && <div className="banner banner-error">{err}</div>}
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span />
              <button className="btn btn-primary" disabled={busy || !message.trim()} onClick={() => act("reply", { message: message.trim() }, "Message sent")}>Send</button>
            </div>
          </div>
        )}
        {!r.canReply && err && <div className="banner banner-error">{err}</div>}
      </section>

      <section className="card card-pad stack">
        <h2>Files</h2>
        <FileList
          files={r.attachments}
          hrefFor={(f) => `/api/b/${token}/attachments/${f.id}`}
          actions={(f) => r.canWithdraw && f.uploadedBy === "you"
            ? <button className="btn btn-ghost btn-sm" onClick={() => void act(`attachments/${f.id}`, undefined, "File removed", "DELETE")}>Remove</button>
            : null}
        />
        {r.canReply && (
          <FileUpload onUpload={async (kind, file) => {
            const form = new FormData();
            form.append("kind", kind);
            form.append("file", file);
            await api(`/api/b/${token}/requests/${r.id}/attachments`, { form });
            await reload();
          }} />
        )}
      </section>
      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}
