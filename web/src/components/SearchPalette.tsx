import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { statusLabel, RequestStatus } from "../lib/requests";

interface Results {
  orders: { id: number; poNo: string; orderNo: string; style: string; colour: string; state: string; status: string | null; buyer: string }[];
  requests: { id: number; requestNo: string; poNo: string; style: string; kind: string; status: RequestStatus; buyer: string }[];
  buyers: { id: number; name: string; country: string | null }[];
}

interface Entry {
  key: string;
  group: string;
  title: string;
  sub: string;
  to: string;
  tag?: string;
}

const GO_TO: Entry[] = [
  { key: "g-orders", group: "Go to", title: "Orders", sub: "The board, trouble first", to: "/m" },
  { key: "g-requests", group: "Go to", title: "Order requests", sub: "What buyers have asked for", to: "/m/requests" },
  { key: "g-new", group: "Go to", title: "New order", sub: "Plan an order yourself", to: "/m/orders/new" },
  { key: "g-buyers", group: "Go to", title: "Buyers", sub: "Links, sign-ins, weekly exports", to: "/m/buyers" },
  { key: "g-templates", group: "Go to", title: "Plan templates", sub: "Stages and timings", to: "/m/templates" },
  { key: "g-units", group: "Go to", title: "Units and capacity", sub: "Stitching capacity and load", to: "/m/units" },
];

/** Jump to any order, request or buyer by what you remember of it: PO, our number, style, colour, buyer. */
export default function SearchPalette({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Results | null>(null);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return setFound(null);
    let live = true;
    const t = setTimeout(() => {
      api<Results>(`/api/m/search?q=${encodeURIComponent(term)}`).then((r) => live && setFound(r)).catch(() => live && setFound(null));
    }, 150);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  const entries: Entry[] = useMemo(() => {
    if (!found) {
      const term = q.trim().toLowerCase();
      return GO_TO.filter((g) => !term || g.title.toLowerCase().includes(term));
    }
    return [
      ...found.orders.map((o) => ({
        key: `o${o.id}`, group: "Orders", title: o.poNo, to: `/m/orders/${o.id}`,
        sub: `${o.orderNo} · ${o.style}, ${o.colour.toLowerCase()} · ${o.buyer}`,
        tag: o.state !== "active" ? o.state : o.status === "red" ? "Will miss date" : o.status === "amber" ? "Behind plan" : undefined,
      })),
      ...found.requests.map((r) => ({
        key: `r${r.id}`, group: "Requests", title: r.poNo, to: `/m/requests/${r.id}`,
        sub: `${r.requestNo} · ${r.kind === "amendment" ? "change · " : ""}${r.style} · ${r.buyer}`, tag: statusLabel(r.status, "office").text,
      })),
      ...found.buyers.map((b) => ({ key: `b${b.id}`, group: "Buyers", title: b.name, sub: `${b.country ?? ""} · see their orders`, to: `/m?buyer=${b.id}` })),
    ];
  }, [found, q]);

  useEffect(() => setActive(0), [entries.length, q]);

  const go = (e: Entry | undefined) => {
    if (!e) return;
    onClose();
    nav(e.to);
  };

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") (e.preventDefault(), setActive((i) => Math.min(entries.length - 1, i + 1)));
    else if (e.key === "ArrowUp") (e.preventDefault(), setActive((i) => Math.max(0, i - 1)));
    else if (e.key === "Enter") (e.preventDefault(), go(entries[active]));
    else if (e.key === "Escape") onClose();
  }

  let lastGroup = "";
  return (
    <div className="palette-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Search">
        <input
          ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} role="combobox" aria-expanded="true" aria-controls="palette-list"
          placeholder="Search orders, requests, buyers: a PO, LT number, style, colour…" autoComplete="off" spellCheck={false}
        />
        <div className="palette-list" id="palette-list" role="listbox">
          {q.trim().length >= 2 && found && entries.length === 0 && <div className="chat-empty">Nothing matches “{q.trim()}”. Try part of a PO number or the buyer's name.</div>}
          {entries.map((e, i) => {
            const header = e.group !== lastGroup ? <div className="palette-group">{e.group}</div> : null;
            lastGroup = e.group;
            return (
              <div key={e.key}>
                {header}
                <button className="palette-item" role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(e)}>
                  <span className="grow"><div><b style={{ fontWeight: 600 }}>{e.title}</b></div><div className="faint small">{e.sub}</div></span>
                  {e.tag && <span className="pill">{e.tag}</span>}
                </button>
              </div>
            );
          })}
        </div>
        <div className="palette-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span><span><kbd>Esc</kbd> to close</span></div>
      </div>
    </div>
  );
}
