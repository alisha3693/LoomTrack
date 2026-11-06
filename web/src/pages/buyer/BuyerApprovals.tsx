import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApprovalCard, BuyerDecision, NoApprovals } from "../../components/Approvals";
import { PageHeader, Skeleton, Toast, useApi } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import type { Approval } from "../../lib/flow";
import BuyerFrame from "./BuyerFrame";

type Show = "you" | "all";

export default function BuyerApprovals() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{() => <List token={token} />}</BuyerFrame>;
}

function List({ token }: { token: string }) {
  const { data, reload } = useApi<{ approvals: Approval[] }>(`/api/b/${token}/approvals`);
  useBadgeRefresh(() => void reload());
  const all = data?.approvals ?? null;
  const waiting = all?.filter((a) => a.status === "requested") ?? [];
  const [show, setShow] = useState<Show | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const view: Show = show ?? (waiting.length ? "you" : "all");
  const shown = all && (view === "you" ? waiting : all);

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader title="Approvals" sub="Samples, lab dips and packaging your merchandiser needs you to sign off before work goes on." />
      <div className="filter-tabs" role="group" aria-label="Show approvals">
        <button aria-pressed={view === "you"} onClick={() => setShow("you")}>Waiting for you <span className="n num">{waiting.length}</span></button>
        <button aria-pressed={view === "all"} onClick={() => setShow("all")}>All <span className="n num">{all?.length ?? 0}</span></button>
      </div>
      {!shown ? <Skeleton rows={3} /> : shown.length === 0 ? (
        all && all.length > 0 ? <p className="muted">You have decided everything. Nothing is waiting for you.</p> : <NoApprovals side="buyer" />
      ) : (
        <div className="stack">
          {shown.map((a) => (
            <ApprovalCard key={a.id} a={a} side="buyer" showOrder={{ to: `/b/${token}/orders/${a.orderId}` }}
              actions={<BuyerDecision token={token} a={a} onDone={(m) => { setToast(m); void reload(); }} />} />
          ))}
        </div>
      )}
      <p className="faint small"><Link to={`/b/${token}/orders`}>Back to your orders</Link></p>
      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}
