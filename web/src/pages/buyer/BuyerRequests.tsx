import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { RequestPill } from "../../components/RequestParts";
import { Empty, useApi } from "../../components/ui";
import { isClosed } from "../../lib/buyer";
import { ago, fmtDate, num } from "../../lib/format";
import type { RequestRow } from "../../lib/requests";
import BuyerFrame from "./BuyerFrame";

type Tab = "you" | "us" | "closed" | "all";
const TABS: { id: Tab; label: string; test: (r: RequestRow) => boolean }[] = [
  { id: "you", label: "Needs you", test: (r) => r.status === "query" || r.status === "countered" },
  { id: "us", label: "With the merchandiser", test: (r) => r.status === "submitted" },
  { id: "closed", label: "Closed", test: (r) => isClosed(r.status) },
  { id: "all", label: "All", test: () => true },
];

export default function BuyerRequests() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{() => <List token={token} />}</BuyerFrame>;
}

function List({ token }: { token: string }) {
  const { data, error } = useApi<{ requests: RequestRow[] }>(`/api/b/${token}/requests`);
  const all = data?.requests ?? [];
  const firstWithWork = TABS.find((t) => t.id !== "all" && all.some(t.test))?.id ?? "all";
  const [picked, setPicked] = useState<Tab | null>(null);
  const tab = picked ?? (data ? (all.some(TABS[0].test) ? "you" : firstWithWork) : "you");
  const shown = all.filter(TABS.find((t) => t.id === tab)!.test);

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h1>Requests</h1><p className="sub">Orders you have asked for, and changes to orders. Each one is a conversation with your merchandiser.</p></div>
        <Link className="btn btn-primary" to={`/b/${token}/requests/new`}>+ New request</Link>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((t) => {
          const n = all.filter(t.test).length;
          return <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setPicked(t.id)}>{t.label} <span className={t.id === "you" && n ? "badge" : "faint"}>{n}</span></button>;
        })}
      </div>
      {error && <div className="banner banner-error">{error}</div>}
      {data && shown.length === 0 && (
        <Empty>{tab === "you" ? "Nothing is waiting for your answer." : all.length === 0 ? "You have not sent a request yet." : "No requests here."}</Empty>
      )}
      {shown.length > 0 && (
        <section className="card">
          {shown.map((r) => (
            <Link key={r.id} to={`/b/${token}/requests/${r.id}`} className="order-row req4">
              <div style={{ minWidth: 0 }}>
                <div className="t">{r.poNo}{r.kind === "amendment" ? <span className="tag" style={{ marginLeft: 8 }}>Change to {r.orderNo}</span> : null} <span className="faint small">{r.requestNo}</span></div>
                <div className="muted small">{r.style}, {r.colour.toLowerCase()} · {num(r.totalQty)} pcs</div>
              </div>
              <div><div className="faint small">Ex-factory asked</div><b className="num">{fmtDate(r.exFactory, true)}</b></div>
              <div className="muted small">{ago(r.updatedAt)}</div>
              <div style={{ textAlign: "right" }}><RequestPill status={r.status} audience="buyer" /></div>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
