import { useState } from "react";
import { ApprovalCard, NoApprovals, OfficeDecision } from "../../components/Approvals";
import { PageHeader, Skeleton, Toast, useApi } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import type { Approval } from "../../lib/flow";
import { plural } from "../../lib/format";

type Show = "you" | "waiting" | "closed" | "all";

/** Everything the buyers have been asked to approve, and what they answered. */
export default function Approvals() {
  const { data, reload } = useApi<{ approvals: Approval[] }>("/api/m/approvals");
  useBadgeRefresh(() => void reload());
  const [show, setShow] = useState<Show>("you");
  const [toast, setToast] = useState<string | null>(null);
  const all = data?.approvals ?? null;
  const part = {
    you: (a: Approval) => a.status === "changes",
    waiting: (a: Approval) => a.status === "requested",
    closed: (a: Approval) => a.status === "approved" || a.status === "withdrawn",
    all: () => true,
  } as const;
  const n = (k: Show) => (all ? all.filter(part[k]).length : 0);
  const shown = all?.filter(part[show]) ?? null;

  return (
    <main className="page">
      <PageHeader title="Approvals" sub="Samples, lab dips and packaging the buyer signs off. Ask for one from the order page." />
      <div className="stack" style={{ gap: 14 }}>
        <div className="filter-tabs" role="group" aria-label="Show approvals">
          {([["you", "Sent back to you"], ["waiting", "Waiting for the buyer"], ["closed", "Closed"], ["all", "All"]] as [Show, string][]).map(([k, label]) => (
            <button key={k} aria-pressed={show === k} onClick={() => setShow(k)}>{label} <span className="n num">{n(k)}</span></button>
          ))}
        </div>
        {!shown ? <Skeleton rows={3} /> : shown.length === 0 ? (
          show === "all" ? <NoApprovals side="office" /> : <p className="muted" style={{ margin: "12px 0" }}>{show === "you" ? "No buyer has sent anything back." : `No ${plural(0, "approval").replace("0 ", "")} here.`}</p>
        ) : (
          <div className="stack">
            {shown.map((a) => (
              <ApprovalCard key={a.id} a={a} side="office" showOrder={{ to: `/m/orders/${a.orderId}?tab=approvals` }}
                actions={<OfficeDecision a={a} onDone={(m) => { setToast(m); void reload(); }} />} />
            ))}
          </div>
        )}
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
