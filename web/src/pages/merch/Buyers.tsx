import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { EmptyState, PageHeader, Skeleton, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDateTime, plural } from "../../lib/format";

export interface LoginRow { id: number; name: string; login: string; pending: number; canWrite: number }
export interface BuyerRow {
  id: number; name: string; country: string | null; link_token: string; link_active: number; active_orders: number; logins: LoginRow[];
  notifyEmail: number; whatsappNumber: string | null; whatsappOptIn: number; whatsappOptInAt: string | null;
}
export interface OutboxRow {
  id: number; buyer: string; subject: string; body: string; channel: "email" | "whatsapp"; created_at: string;
  audience: "buyer" | "office"; recipient: string | null; status: string; error: string | null; sent_at: string | null;
}

/** How far a message got. Words first, colour second. */
const STATUS: Record<string, { label: string; tone: "green" | "amber" | "red" | "" }> = {
  logged: { label: "Recorded only", tone: "" },
  queued: { label: "Waiting to send", tone: "amber" },
  sent: { label: "Sent", tone: "green" },
  delivered: { label: "Delivered", tone: "green" },
  read: { label: "Read", tone: "green" },
  failed: { label: "Failed", tone: "red" },
  skipped: { label: "Not sent", tone: "" },
};

/** Every email and WhatsApp message to or about a buyer, and how far each got. Used on the buyers page and on each buyer's profile. */
export function SentLog({ rows, onChanged }: { rows: OutboxRow[] | null; onChanged?: () => void }) {
  const [problem, setProblem] = useState<string | null>(null);
  if (!rows) return <Skeleton rows={3} />;
  if (rows.length === 0) return <EmptyState title="Nothing sent yet" hint="Replies, approval requests and confirmed delay notices are recorded here, with how far each one got." />;
  const retry = async (id: number) => {
    setProblem(null);
    try { await api(`/api/m/outbox/${id}/retry`, { method: "POST" }); onChanged?.(); } catch (e) { setProblem((e as Error).message); }
  };
  return (
    <div className="card">
      {problem && <p className="error-text" role="alert" style={{ padding: "10px 20px", margin: 0 }}>{problem}</p>}
      {rows.map((m) => {
        const s = STATUS[m.status] ?? { label: m.status, tone: "" as const };
        return (
          <div key={m.id} className="sent-row">
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap", alignItems: "baseline" }}>
              <b style={{ fontWeight: 500 }}>{m.subject}</b>
              <span className="faint small nowrap">{m.buyer} · {fmtDateTime(m.created_at)}</span>
            </div>
            <div className="muted small sent-body">{m.body}</div>
            <div className="row small" style={{ marginTop: 6, gap: 14 }}>
              <span className={`pill ${s.tone ? `pill-${s.tone}` : ""}`}>{s.label}</span>
              <span className="faint">{m.channel === "whatsapp" ? "WhatsApp" : "Email"}{m.recipient ? ` to ${m.recipient}` : ""}{m.audience === "office" ? " (office)" : ""}</span>
              {m.error && <span className={m.status === "failed" ? "error-text" : "faint"}>{m.error}</span>}
              {m.status === "failed" && onChanged && <button className="btn btn-ghost btn-sm" onClick={() => void retry(m.id)}>Send again</button>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Buyers() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "sent" ? "sent" : "buyers";
  const { data: buyers } = useApi<BuyerRow[]>("/api/m/buyers");
  const { data: outbox, reload: reloadOutbox } = useApi<OutboxRow[]>("/api/m/outbox");

  return (
    <main className="page">
      <PageHeader title="Buyers" sub="Each buyer has a private link and can have their own people sign in. They see only their own orders, and delays appear only after you confirm them." />
      <div className="stack" style={{ gap: 14 }}>
        <div className="filter-tabs" role="group" aria-label="Show">
          <button aria-pressed={tab === "buyers"} onClick={() => setParams({}, { replace: true })}>Buyers <span className="n num">{buyers?.length ?? 0}</span></button>
          <button aria-pressed={tab === "sent"} onClick={() => setParams({ tab: "sent" }, { replace: true })}>Sent messages <span className="n num">{outbox?.length ?? 0}</span></button>
        </div>
        {tab === "sent" ? (
          <>
            <p className="faint small" style={{ margin: 0 }}>Everything sent by email or WhatsApp, with how far it got. <Link to="/m/notifications">Set up sending</Link></p>
            <SentLog rows={outbox} onChanged={reloadOutbox} />
          </>
        ) : !buyers ? <Skeleton rows={3} /> : (
          <div className="card table-scroll">
            <table className="table rows-link">
              <thead><tr><th style={{ paddingLeft: 20 }}>Buyer</th><th>Country</th><th className="r">Active orders</th><th>People</th><th /></tr></thead>
              <tbody>
                {buyers.map((b) => (
                  <tr key={b.id} onClick={() => nav(`/m/buyers/${b.id}`)}>
                    <td style={{ paddingLeft: 20 }}><Link to={`/m/buyers/${b.id}`} className="po" onClick={(e) => e.stopPropagation()}>{b.name}</Link></td>
                    <td>{b.country ?? "—"}</td>
                    <td className="r num">{b.active_orders}</td>
                    <td className="muted">{b.logins.length ? plural(b.logins.length, "sign-in") : "Link only"}</td>
                    <td className="r" style={{ paddingRight: 20 }}><span className="faint small">Open →</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
