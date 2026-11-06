import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, PageHeader, Skeleton, Swatch, useApi } from "../../components/ui";
import { RequestPill } from "../../components/RequestParts";
import { ago, fmtDate, num } from "../../lib/format";
import type { RequestRow, RequestStatus } from "../../lib/requests";

const TABS = [
  { key: "mine", label: "Needs you" },
  { key: "waiting", label: "Waiting for buyer" },
  { key: "closed", label: "Closed" },
  { key: "all", label: "All" },
];

/** What happens next on a request, in a line, so nobody has to open it to find out. */
const NEXT: Record<RequestStatus, string> = {
  submitted: "Accept it, ask a question, or propose a date",
  query: "The buyer has to answer your question",
  countered: "The buyer has to agree to your date",
  accepted: "Became an order",
  declined: "Declined",
  withdrawn: "The buyer withdrew it",
};

export default function Requests() {
  const nav = useNavigate();
  const [tab, setTab] = useState("mine");
  const { data, error } = useApi<{ requests: RequestRow[]; openCount: number }>(`/api/m/requests?filter=${tab}`);

  return (
    <main className="page">
      <PageHeader title="Requests" sub="Requests buyers send from their page. Ask a question, propose a different date, accept it into an order, or decline." />
      <div className="stack" style={{ gap: 14 }}>
        <div className="filter-tabs" role="group" aria-label="Show requests">
          {TABS.map((t) => (
            <button key={t.key} aria-pressed={tab === t.key} onClick={() => setTab(t.key)}>
              {t.label}{t.key === "mine" && data && data.openCount > 0 ? <span className="n num"> {data.openCount}</span> : null}
            </button>
          ))}
        </div>

        {error && <div className="banner banner-error">{error}</div>}
        {!data && !error && <Skeleton rows={3} />}
        {data && data.requests.length === 0 && (
          <EmptyState title={tab === "mine" ? "Nothing needs an answer" : "No requests here"} hint={tab === "mine" ? "New buyer requests and replies to your questions appear here." : "Try another tab."} />
        )}
        {data && data.requests.length > 0 && (
          <div className="card table-scroll">
            <table className="table board rows-link">
              <thead><tr><th>Request</th><th>Buyer</th><th>Ex-factory asked</th><th>Status and next step</th><th>Last activity</th></tr></thead>
              <tbody>
                {data.requests.map((r) => (
                  <tr key={r.id} onClick={() => nav(`/m/requests/${r.id}`)}>
                    <td>
                      <b>{r.poNo}</b> <span className="faint small">{r.requestNo}</span>
                      {r.kind === "amendment" && <span className="tag" style={{ marginLeft: 8 }}>Change to {r.orderNo}</span>}
                      <div className="muted">{r.style}, <Swatch hex={r.colourHex} />{r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div>
                    </td>
                    <td>{r.buyer}</td>
                    <td className="nowrap">{fmtDate(r.exFactory, true)}</td>
                    <td><RequestPill status={r.status} audience="office" /><div className="faint small" style={{ marginTop: 3 }}>{NEXT[r.status]}</div></td>
                    <td className="muted small nowrap">{ago(r.updatedAt)}</td>
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
