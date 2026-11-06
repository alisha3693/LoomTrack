import { ago, fmtDateTime } from "../lib/format";
import type { ActivityItem } from "../lib/flow";
import { EmptyState } from "./ui";
import Icon, { IconName } from "./Icon";

const ICON: Record<ActivityItem["kind"], IconName> = {
  date: "clock", step: "approvals", message: "messages", request: "requests", approval: "approvals", notice: "alert", material: "file",
};

/** A timeline of what happened on an order and who did it, newest first. */
export default function Activity({ items }: { items: ActivityItem[] | null }) {
  if (!items) return null;
  if (items.length === 0) return <EmptyState title="Nothing has happened yet" hint="Messages, approvals, date changes and delay notices appear here as they happen." />;
  return (
    <ol className="activity">
      {items.map((i, n) => (
        <li key={n}>
          <span className="activity-icon"><Icon name={ICON[i.kind]} size={16} /></span>
          <div>
            <div><b>{i.title}</b></div>
            {i.detail && <div className="muted small activity-detail">{i.detail}</div>}
            <div className="faint small" title={fmtDateTime(i.at)}>{i.actor === "buyer" ? "Buyer" : i.actor === "merchandiser" ? "Merchandiser" : i.actor} · {ago(i.at) || fmtDateTime(i.at)}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
