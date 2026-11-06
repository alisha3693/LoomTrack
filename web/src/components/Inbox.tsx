import { Link } from "react-router-dom";
import { ago } from "../lib/format";
import type { InboxItem } from "../lib/flow";
import { EmptyState, Skeleton } from "./ui";

/**
 * Every conversation in one list, the ones that wait on you first. A dot marks what you have not opened.
 * `hrefFor` decides where a row leads; the same list serves the office and the buyer.
 */
export default function Inbox({
  items, loading, hrefFor, me, empty,
}: {
  items: InboxItem[] | null;
  loading: boolean;
  hrefFor: (i: InboxItem) => string;
  me: "buyer" | "merchandiser";
  empty: { title: string; hint: string };
}) {
  if (!items) return loading ? <Skeleton rows={5} /> : null;
  if (items.length === 0) return <EmptyState title={empty.title} hint={empty.hint} />;
  return (
    <div className="card inbox" role="list">
      {items.map((i) => (
        <Link key={`${i.kind}${i.id}`} to={hrefFor(i)} className={`inbox-row${i.unread ? " unread" : ""}`} role="listitem">
          <span className="inbox-dot">{i.unread ? <><i aria-hidden="true" /><span className="sr-only">Not opened yet</span></> : null}</span>
          <div className="inbox-main">
            <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              <b>{i.title}</b>
              <span className="faint small inbox-sub">{i.subtitle}</span>
              {i.kind === "request" && <span className="tag">Request</span>}
            </div>
            <div className="inbox-last">
              <span className="muted">{i.last.author === me ? "You: " : `${me === "buyer" ? "Merchandiser" : i.party}: `}</span>
              {i.last.text}
            </div>
          </div>
          <div className="inbox-side">
            <span className="faint small">{ago(i.last.at)}</span>
            {i.turn === "you" ? <span className="pill pill-amber">Your turn</span> : <span className="faint small">Waiting for them</span>}
          </div>
        </Link>
      ))}
    </div>
  );
}
