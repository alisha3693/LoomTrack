import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Empty, Swatch, useApi } from "../../components/ui";
import { RequestPill } from "../../components/RequestParts";
import { ago, fmtDate, num } from "../../lib/format";
import type { RequestRow } from "../../lib/requests";

const TABS = [
  { key: "mine", label: "Needs you" },
  { key: "waiting", label: "Waiting for buyer" },
  { key: "closed", label: "Closed" },
  { key: "all", label: "All" },
];

export default function Requests() {
  const nav = useNavigate();
  const [tab, setTab] = useState("mine");
  const { data, error } = useApi<{ requests: RequestRow[]; openCount: number }>(`/api/m/requests?filter=${tab}`);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Order requests</h1>
          <p className="sub">Requests buyers send from their link. Ask a question, propose a different date, accept it into an order, or decline.</p>
        </div>
      </div>

      <div className="row" style={{ marginBottom: 14 }} role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={`btn btn-sm ${tab === t.key ? "btn-primary" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}{t.key === "mine" && data && data.openCount > 0 ? ` (${data.openCount})` : ""}
          </button>
        ))}
      </div>

      {error && <div className="banner banner-error">{error}</div>}
      {data && data.requests.length === 0 && <Empty>{tab === "mine" ? "Nothing needs an answer right now. New buyer requests and replies to your questions appear here." : "No requests here."}</Empty>}
      {data && data.requests.length > 0 && (
        <div className="card table-scroll">
          <table className="table board">
            <thead><tr><th>Request</th><th>Buyer</th><th>Ex-factory asked</th><th>Status</th><th>Last activity</th></tr></thead>
            <tbody>
              {data.requests.map((r) => (
                <tr key={r.id} onClick={() => nav(`/m/requests/${r.id}`)} style={{ cursor: "pointer" }}>
                  <td>
                    <b>{r.poNo}</b> <span className="faint small">{r.requestNo}</span>
                    {r.kind === "amendment" && <span className="tag" style={{ marginLeft: 8 }}>Change to {r.orderNo}</span>}
                    <div className="muted">{r.style}, <Swatch hex={r.colourHex} />{r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div>
                  </td>
                  <td>{r.buyer}</td>
                  <td>{fmtDate(r.exFactory, true)}</td>
                  <td><RequestPill status={r.status} audience="office" /></td>
                  <td className="muted small nowrap">{ago(r.updatedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
