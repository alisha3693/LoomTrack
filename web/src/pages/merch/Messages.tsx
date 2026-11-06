import { useState } from "react";
import Inbox from "../../components/Inbox";
import { PageHeader, useApi } from "../../components/ui";
import { useBadgeRefresh } from "../../lib/badges";
import type { InboxItem } from "../../lib/flow";
import { plural } from "../../lib/format";

type Show = "all" | "you" | "unread";

/** Every conversation with every buyer in one list: the ones waiting on you first. */
export default function Messages() {
  const { data, loading, reload } = useApi<{ conversations: InboxItem[] }>("/api/m/inbox");
  useBadgeRefresh(() => void reload());
  const [show, setShow] = useState<Show>("all");
  const all = data?.conversations ?? null;
  const items = all && all.filter((i) => show === "all" || (show === "you" ? i.turn === "you" : i.unread));
  const count = (f: (i: InboxItem) => boolean) => (all ? all.filter(f).length : 0);

  return (
    <main className="page">
      <PageHeader title="Messages" sub={all ? `${plural(all.length, "conversation")} with buyers` : " "} />
      <div className="stack" style={{ gap: 14 }}>
        <div className="filter-tabs" role="group" aria-label="Show conversations">
          <button aria-pressed={show === "all"} onClick={() => setShow("all")}>All <span className="n num">{all?.length ?? 0}</span></button>
          <button aria-pressed={show === "you"} onClick={() => setShow("you")}>Waiting for you <span className="n num">{count((i) => i.turn === "you")}</span></button>
          <button aria-pressed={show === "unread"} onClick={() => setShow("unread")}>Not opened <span className="n num">{count((i) => i.unread)}</span></button>
        </div>
        <Inbox
          items={items} loading={loading} me="merchandiser"
          hrefFor={(i) => (i.kind === "order" ? `/m/orders/${i.id}?tab=conversation` : `/m/requests/${i.id}`)}
          empty={{ title: show === "all" ? "No conversations yet" : "Nothing here", hint: show === "all" ? "When a buyer writes about an order or a request, it appears here." : "You are all caught up." }}
        />
      </div>
    </main>
  );
}
