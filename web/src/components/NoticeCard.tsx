import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtDate, fmtDateTime } from "../lib/format";
import { useCanWrite } from "./ui";

export interface Notice { message: string; expectedExFactory: string; at: string; seenAt: string | null; acknowledgedAt: string | null }

/**
 * The buyer's view of a confirmed delay notice. Opening it tells the merchandiser it was seen; the buyer can
 * acknowledge it (optionally with a note, which also goes into the conversation) so nobody has to guess.
 */
export default function NoticeCard({ token, orderId, exFactory, notice, onChanged }: { token: string; orderId: number; exFactory: string; notice: Notice; onChanged: () => void }) {
  const canWrite = useCanWrite();
  const [note, setNote] = useState("");
  const [writing, setWriting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!notice.seenAt) api(`/api/b/${token}/orders/${orderId}/notice/seen`, { method: "POST" }).catch(() => {});
  }, [token, orderId, notice.seenAt]);

  async function acknowledge() {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/b/${token}/orders/${orderId}/notice/acknowledge`, { body: { note: note.trim() || null } });
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <section className="notice" aria-label="Delay notice">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="section-title" style={{ marginBottom: 2 }}>Delay notice · {fmtDateTime(notice.at)}</div>
          <b>Now expected {fmtDate(notice.expectedExFactory, true)}, instead of {fmtDate(exFactory, true)}</b>
        </div>
        {notice.acknowledgedAt ? <span className="pill pill-green">You acknowledged this {fmtDate(notice.acknowledgedAt)}</span> : <span className="pill pill-red">Needs your acknowledgement</span>}
      </div>
      <p style={{ margin: 0 }}>{notice.message}</p>
      {!notice.acknowledgedAt && canWrite && (
        <div className="stack" style={{ gap: 8 }}>
          {writing && (
            <label className="field"><span>Anything you want your merchandiser to know? (optional)</span>
              <textarea className="textarea" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: please ship the last 500 pieces by air." />
            </label>
          )}
          {err && <div className="banner banner-error">{err}</div>}
          <div className="row">
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void acknowledge()}>{writing ? "Acknowledge and send note" : "Acknowledge"}</button>
            {!writing && <button className="btn btn-sm" onClick={() => setWriting(true)}>Acknowledge with a note</button>}
          </div>
        </div>
      )}
    </section>
  );
}
