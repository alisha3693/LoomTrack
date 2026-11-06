import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { EmptyState, PageHeader, Skeleton, useApi } from "../../components/ui";
import { fmtDateTime, plural } from "../../lib/format";

export interface LoginRow { id: number; name: string; login: string; pending: number; canWrite: number }
export interface BuyerRow { id: number; name: string; country: string | null; link_token: string; link_active: number; active_orders: number; logins: LoginRow[] }
export interface OutboxRow { id: number; buyer: string; subject: string; body: string; channel: string; created_at: string }

/** What was sent to buyers (mock email in this demo). Used on the buyers page and on each buyer's profile. */
export function SentLog({ rows }: { rows: OutboxRow[] | null }) {
  if (!rows) return <Skeleton rows={3} />;
  if (rows.length === 0) return <EmptyState title="Nothing sent yet" hint="Replies, approval requests and confirmed delay notices that go to a buyer are recorded here." />;
  return (
    <div className="card">
      {rows.map((m) => (
        <div key={m.id} className="sent-row">
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
            <b style={{ fontWeight: 500 }}>{m.subject}</b>
            <span className="faint small nowrap">{m.buyer} · {fmtDateTime(m.created_at)}</span>
          </div>
          <div className="muted small">{m.body}</div>
        </div>
      ))}
    </div>
  );
}

export default function Buyers() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "sent" ? "sent" : "buyers";
  const { data: buyers } = useApi<BuyerRow[]>("/api/m/buyers");
  const { data: outbox } = useApi<OutboxRow[]>("/api/m/outbox");

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
            <p className="faint small" style={{ margin: 0 }}>Demo: messages are recorded here instead of emailed.</p>
            <SentLog rows={outbox} />
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
