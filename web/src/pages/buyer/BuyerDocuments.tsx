import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EmptyState, PageHeader, Skeleton, useApi } from "../../components/ui";
import { fmtDate } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

interface Doc {
  id: number; kind: string; filename: string; mime: string; size: number; at: string; uploadedBy: "you" | "merchandiser";
  orderId: number | null; orderPo: string | null; requestId: number | null; requestPo: string | null; url: string;
}

const KIND: Record<string, string> = { design: "Design", pattern: "Pattern", print: "Print artwork", fabric: "Fabric", other: "Other" };
const size = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

export default function BuyerDocuments() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{() => <List token={token} />}</BuyerFrame>;
}

function List({ token }: { token: string }) {
  const { data } = useApi<{ documents: Doc[] }>(`/api/b/${token}/documents`);
  const [q, setQ] = useState("");
  const docs = data?.documents ?? null;
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (docs ?? []).filter((d) => !needle || [d.filename, d.orderPo, d.requestPo, KIND[d.kind]].some((t) => t?.toLowerCase().includes(needle)));
  }, [docs, q]);

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader title="Documents" sub="Every file shared on your orders and requests, in one place." />
      <label className="field" style={{ maxWidth: 360 }}>
        <span className="sr-only">Search documents</span>
        <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by file name or PO" />
      </label>
      {!docs ? <Skeleton rows={4} /> : shown.length === 0 ? (
        <EmptyState title={docs.length === 0 ? "No documents yet" : "No match"} hint={docs.length === 0 ? "Files your merchandiser shares, and files you attach to a request, appear here." : "Try another word."} />
      ) : (
        <div className="card table-scroll">
          <table className="table">
            <thead><tr><th style={{ paddingLeft: 20 }}>File</th><th>Type</th><th>For</th><th>From</th><th>Added</th><th className="r" style={{ paddingRight: 20 }}>Size</th></tr></thead>
            <tbody>
              {shown.map((d) => (
                <tr key={d.id}>
                  <td style={{ paddingLeft: 20 }}><a href={d.url} target="_blank" rel="noreferrer">{d.filename}</a></td>
                  <td>{KIND[d.kind] ?? d.kind}</td>
                  <td>{d.orderId ? <Link to={`/b/${token}/orders/${d.orderId}`}>{d.orderPo}</Link> : d.requestId ? <Link to={`/b/${token}/requests/${d.requestId}`}>{d.requestPo}</Link> : "—"}</td>
                  <td>{d.uploadedBy === "you" ? "You" : "Merchandiser"}</td>
                  <td className="num nowrap">{fmtDate(d.at.slice(0, 10))}</td>
                  <td className="r num faint" style={{ paddingRight: 20 }}>{size(d.size)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
