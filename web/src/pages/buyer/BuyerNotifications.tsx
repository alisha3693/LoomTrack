import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import NotificationFeed, { FeedItem } from "../../components/NotificationFeed";
import { PageHeader, Skeleton, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import { refreshBadges } from "../../lib/badges";
import BuyerFrame from "./BuyerFrame";

export default function BuyerNotifications() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{(_n, today) => <List token={token} today={today} />}</BuyerFrame>;
}

function List({ token, today }: { token: string; today: string }) {
  const { data } = useApi<{ items: FeedItem[]; seenUpTo: number }>(`/api/b/${token}/feed`);
  const marked = useRef(false);
  // Opening the page counts as seeing it; what was new stays marked until the next visit.
  useEffect(() => {
    if (!data || marked.current) return;
    marked.current = true;
    if (data.items.length) api(`/api/b/${token}/feed/read`, { method: "POST", body: {} }).then(refreshBadges).catch(() => undefined);
  }, [data, token]);

  const linkFor = (i: FeedItem) => {
    const base = `/b/${token}`;
    if (i.topic === "Approval") return `${base}/approvals`;
    if (i.topic === "Request" || i.topic === "Change") return i.orderId && i.topic === "Change" ? `${base}/orders/${i.orderId}` : `${base}/requests`;
    return i.orderId ? `${base}/orders/${i.orderId}` : `${base}/orders`;
  };

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader title="Notifications" sub="Everything your merchandiser has told you about your orders and requests, newest first. The same messages are also emailed to you." />
      {data ? <NotificationFeed items={data.items} seenUpTo={data.seenUpTo} today={today} linkFor={linkFor} /> : <Skeleton rows={4} />}
    </div>
  );
}
