import { useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
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
  const { data: r, error, reload } = useApi<RequestDetailData>(`/api/b/${token}/requests/${id}`);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const uploadErrors: string[] = (useLocation().state as { uploadErrors?: string[] } | null)?.uploadErrors ?? [];

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!r) return <p className="faint">Loading…</p>;

  const proposed = [...r.messages].reverse().find((m) => m.event === "counter")?.proposedExFactory;

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

  return (
    <div className="stack">
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <div className="row"><h2 style={{ fontSize: 22 }}>{r.poNo}</h2><RequestPill status={r.status} audience="buyer" /></div>
          <p className="sub">Request {r.requestNo}{r.orderNo ? ` · our order number ${r.orderNo}` : ""}</p>
        </div>
      </div>

      {uploadErrors.length > 0 && (
        <div className="banner banner-error">Your request was sent, but some files could not be added: {uploadErrors.join("; ")}. You can add them again below.</div>
      )}
      <section className="card card-pad"><RequestSummary r={r} /></section>

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

      {r.status === "countered" && proposed && (
        <section className="card card-pad stack" style={{ borderColor: "var(--amber)" }}>
          <b>The merchandiser proposes ex-factory {fmtDate(proposed, true)}</b>
          <p className="muted" style={{ margin: 0 }}>Agreeing updates your request to this date. Or reply below if it does not work.</p>
          <div className="row"><button className="btn btn-primary" disabled={busy} onClick={() => act("agree", undefined, "You agreed to the new date")}>Agree to {fmtDate(proposed)}</button></div>
        </section>
      )}

      {r.canReply && (
        <section className="card card-pad stack">
          <label className="field"><span>{r.status === "query" ? "Your answer" : "Write to the merchandiser"}</span>
            <textarea className="textarea" rows={3} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
          </label>
          {err && <div className="banner banner-error">{err}</div>}
          <div className="row" style={{ justifyContent: "space-between" }}>
            {r.canWithdraw ? <button className="btn btn-ghost" disabled={busy} onClick={() => window.confirm("Withdraw this request?") && void act("withdraw", undefined, "Request withdrawn")}>Withdraw request</button> : <span />}
            <button className="btn btn-primary" disabled={busy || !message.trim()} onClick={() => act("reply", { message: message.trim() }, "Message sent")}>Send</button>
          </div>
        </section>
      )}
      {!r.canReply && err && <div className="banner banner-error">{err}</div>}

      <h2>History</h2>
      <RequestThread r={r} audience="buyer" />
      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}
