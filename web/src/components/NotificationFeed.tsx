import { Link } from "react-router-dom";
import { EmptyState } from "./ui";
import { ago, fmtDate } from "../lib/format";

export interface FeedItem {
  id: number;
  event: string;
  topic: string;
  title: string;
  text: string;
  at: string;
  orderId: number | null;
  poNo: string | null;
  buyerId: number;
  buyerName: string;
}

const TONE: Record<string, string> = { Delay: "pill-red", Floor: "pill-amber", Order: "pill-red", Request: "", Change: "" };

/** What the app has told this side, newest first and grouped by day. What is new since the last visit is marked. */
export default function NotificationFeed({ items, seenUpTo, today, linkFor, showBuyer }: {
  items: FeedItem[];
  seenUpTo: number;
  today: string;
  linkFor: (i: FeedItem) => string;
  showBuyer?: boolean;
}) {
  if (items.length === 0) return <EmptyState title="No notifications yet" hint="Delay notices, request answers, approvals and cancellations show up here as they happen." />;
  const days: { day: string; list: FeedItem[] }[] = [];
  for (const i of items) {
    const day = i.at.slice(0, 10);
    const last = days[days.length - 1];
    if (last?.day === day) last.list.push(i);
    else days.push({ day, list: [i] });
  }
  return (
    <div className="stack" style={{ gap: 22 }}>
      {days.map(({ day, list }) => (
        <section key={day} aria-label={day === today ? "Today" : fmtDate(day, true)} className="stack" style={{ gap: 8 }}>
          <div className="section-title" style={{ margin: 0 }}>{day === today ? "Today" : fmtDate(day, true)}</div>
          <div className="card">
            {list.map((i) => {
              const fresh = i.id > seenUpTo;
              return (
                <Link key={i.id} to={linkFor(i)} className="order-row" style={{ gridTemplateColumns: "auto 1fr auto", alignItems: "flex-start" }}>
                  <span className={fresh ? "dot-new" : ""} style={fresh ? undefined : { display: "inline-block", width: 8 }} title={fresh ? "New" : undefined} aria-label={fresh ? "New" : undefined} />
                  <div style={{ minWidth: 0 }}>
                    <div className="t">{i.title}</div>
                    <div className="muted small" style={{ overflowWrap: "anywhere", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{i.text.split(/\s*\n+\s*/).join(" ")}</div>
                    {showBuyer && <div className="faint small">{i.buyerName}{i.poNo ? ` · ${i.poNo}` : ""}</div>}
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span className={`pill ${TONE[i.topic] ? TONE[i.topic] : ""}`}>{i.topic}</span>
                    <div className="faint small" style={{ marginTop: 4 }}>{ago(i.at)}</div>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
