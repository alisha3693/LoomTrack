import { useState } from "react";
import { Toast, useApi } from "../../components/ui";
import { api, download } from "../../lib/api";
import { fmtDateTime } from "../../lib/format";

interface BuyerRow { id: number; name: string; country: string | null; link_token: string; link_active: number; active_orders: number }
interface OutboxRow { id: number; buyer: string; subject: string; body: string; channel: string; created_at: string }

export default function Buyers() {
  const { data: buyers, reload } = useApi<BuyerRow[]>("/api/m/buyers");
  const { data: outbox } = useApi<OutboxRow[]>("/api/m/outbox");
  const [toast, setToast] = useState<string | null>(null);
  const link = (token: string) => `${window.location.origin}/b/${token}`;

  const copy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(link(token));
      setToast("Link copied");
    } catch {
      setToast(link(token));
    }
  };
  const rotate = async (b: BuyerRow) => {
    if (!confirm(`Make a new link for ${b.name}? The old link stops working immediately.`)) return;
    await api(`/api/m/buyers/${b.id}/rotate-link`, { method: "POST" });
    setToast("New link created. Send it to the buyer.");
    void reload();
  };
  const exportXlsx = (b: BuyerRow, audience: "buyer" | "internal") =>
    download(`/api/m/exports/weekly?buyerId=${b.id}&audience=${audience}`, `${b.name.replace(/\W+/g, "-")}-weekly-${audience}.xlsx`).catch((e) => setToast(e.message));

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>Buyers &amp; exports</h1>
          <p className="sub">Each buyer gets a private, read-only link showing only their own orders. Delays appear there only after you confirm them.</p>
        </div>
      </div>
      <div className="stack">
        {buyers?.map((b) => (
          <section key={b.id} className="card card-pad stack" style={{ gap: 12 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <h2>{b.name}</h2>
                <div className="faint small">{b.country} · {b.active_orders} active orders</div>
              </div>
              <a className="btn btn-sm" href={`/b/${b.link_token}`} target="_blank" rel="noreferrer">Open buyer view ↗</a>
            </div>
            <div className="row">
              <input className="input input-sm mono" readOnly value={link(b.link_token)} style={{ flex: 1, minWidth: 220 }} onFocus={(e) => e.target.select()} aria-label="Buyer link" />
              <button className="btn btn-sm" onClick={() => copy(b.link_token)}>Copy</button>
              <button className="btn btn-ghost btn-sm" onClick={() => rotate(b)}>New link</button>
            </div>
            <div className="row">
              <span className="small muted">Weekly status (Excel):</span>
              <button className="btn btn-sm" onClick={() => exportXlsx(b, "buyer")}>Buyer edition</button>
              <button className="btn btn-ghost btn-sm" onClick={() => exportXlsx(b, "internal")}>Internal edition</button>
            </div>
          </section>
        ))}

        <section className="card">
          <div className="card-head"><h2>Sent to buyers</h2><span className="faint small">Demo: messages are recorded here instead of emailed</span></div>
          <div className="card-body">
            {!outbox?.length ? <p className="faint">Nothing sent yet.</p> : (
              <ul className="reasons">
                {outbox.map((m) => (
                  <li key={m.id}>
                    <b style={{ fontWeight: 500 }}>{m.subject}</b> <span className="faint small">→ {m.buyer} · {fmtDateTime(m.created_at)}</span>
                    <div className="muted small">{m.body}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
