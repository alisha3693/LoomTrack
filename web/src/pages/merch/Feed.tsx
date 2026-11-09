import { useEffect, useRef } from "react";
import NotificationFeed, { FeedItem } from "../../components/NotificationFeed";
import { PageHeader, Skeleton, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import { useMeta, useReloadMeta } from "./OfficeShell";

/** What buyers did that needs the office to know: new requests, answers, approvals and acknowledged delay notices. */
export default function Feed() {
  const meta = useMeta();
  const reloadMeta = useReloadMeta();
  const { data } = useApi<{ items: FeedItem[]; seenUpTo: number }>("/api/m/feed");
  const marked = useRef(false);
  useEffect(() => {
    if (!data || marked.current) return;
    marked.current = true;
    if (data.items.length) api("/api/m/feed/read", { method: "POST", body: {} }).then(reloadMeta).catch(() => undefined);
  }, [data, reloadMeta]);

  const linkFor = (i: FeedItem) => (i.topic === "Approval" ? "/m/approvals" : i.orderId && i.topic !== "Request" ? `/m/orders/${i.orderId}` : i.topic === "Request" ? "/m/requests" : "/m");

  return (
    <main className="page">
      <PageHeader title="Notifications" sub="What buyers have sent or answered: new requests, approvals and acknowledged delay notices, newest first." />
      <div style={{ marginTop: 20 }}>
        {data && meta ? <NotificationFeed items={data.items} seenUpTo={data.seenUpTo} today={meta.today} linkFor={linkFor} showBuyer /> : <Skeleton rows={4} />}
      </div>
    </main>
  );
}
