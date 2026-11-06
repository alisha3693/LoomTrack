import { useState } from "react";
import { useParams } from "react-router-dom";
import Inbox from "../../components/Inbox";
import { PageHeader, useApi } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import type { InboxItem } from "../../lib/flow";
import { plural } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

type Show = "all" | "you" | "unread";

export default function BuyerMessages() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token} wide>{() => <List token={token} />}</BuyerFrame>;
}

function List({ token }: { token: string }) {
  const { data, loading, reload } = useApi<{ conversations: InboxItem[] }>(`/api/b/${token}/inbox`);
  useBadgeRefresh(() => void reload());
  const [show, setShow] = useState<Show>("all");
  const all = data?.conversations ?? null;
  const items = all && all.filter((i) => show === "all" || (show === "you" ? i.turn === "you" : i.unread));
  const count = (f: (i: InboxItem) => boolean) => (all ? all.filter(f).length : 0);

  return (
    <div className="stack" style={{ gap: 18 }}>
      <PageHeader title="Messages" sub={all ? `${plural(all.length, "conversation")} with your merchandiser` : " "} />
      <div className="filter-tabs" role="group" aria-label="Show conversations">
        <button aria-pressed={show === "all"} onClick={() => setShow("all")}>All <span className="n num">{all?.length ?? 0}</span></button>
        <button aria-pressed={show === "you"} onClick={() => setShow("you")}>Waiting for you <span className="n num">{count((i) => i.turn === "you")}</span></button>
        <button aria-pressed={show === "unread"} onClick={() => setShow("unread")}>Not opened <span className="n num">{count((i) => i.unread)}</span></button>
      </div>
      <Inbox
        items={items} loading={loading} me="buyer"
        hrefFor={(i) => (i.kind === "order" ? `/b/${token}/orders/${i.id}?tab=messages` : `/b/${token}/requests/${i.id}`)}
        empty={{ title: show === "all" ? "No messages yet" : "Nothing here", hint: show === "all" ? "Open one of your orders and write to your merchandiser. Replies appear here." : "You are all caught up." }}
      />
    </div>
  );
}
