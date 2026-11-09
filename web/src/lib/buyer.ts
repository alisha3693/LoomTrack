// What the buyer's pages know about an order, and what should be put in front of them.

import type { AttentionItem } from "../components/Attention";
import type { Notice } from "../components/NoticeCard";
import type { Fabric } from "./fabric";
import { fmtDate } from "./format";
import type { RequestRow } from "./requests";
import type { FileItem } from "./types";

export interface BuyerOrder {
  id: number;
  poNo: string;
  style: string;
  colour: string;
  colourHex: string | null;
  colourPantone: string | null;
  fabric: Fabric;
  qty: number;
  sizes: { size: string; qty: number }[];
  exFactory: string;
  state: string;
  shippedDate: string | null;
  shippedVerdict: string | null;
  notice: Notice | null;
  overallPct: number;
  milestones: { code: string; name: string; kind: "milestone" | "stage"; plannedDate: string; actualDate: string | null; pct: number; done: number | null }[];
  attachments: FileItem[];
  photos: { id: number; date: string; stage: string }[];
  dateChanges: { field: string; oldValue: string | null; newValue: string | null; reason: string; changedAt: string; milestone: string | null }[];
}

/** An order the merchandiser cancelled: the buyer only needs to know that, and why. */
export interface CancelledOrder { id: number; poNo: string; style: string; qty: number; exFactory: string; reason: string | null; cancelledAt: string | null }

export interface BuyerData {
  buyer: { name: string; country: string | null };
  today: string;
  orders: BuyerOrder[];
  cancelledOrders: CancelledOrder[];
}

/** One word for where an order is, from what the buyer is allowed to know (never the internal colour). */
export function orderChip(o: BuyerOrder): { text: string; tone: "" | "green" | "amber" | "red" } {
  if (o.state === "shipped") return { text: "Shipped", tone: "green" };
  if (o.notice) return { text: "Delay notice", tone: "red" };
  if (o.overallPct >= 100) return { text: "Packed", tone: "green" };
  if (o.milestones.some((m) => m.kind === "stage" && m.pct > 0)) return { text: "In production", tone: "" };
  return { text: "Planned", tone: "" };
}

export const isClosed = (s: RequestRow["status"]) => s === "accepted" || s === "declined" || s === "withdrawn";

/** Everything waiting on the buyer, most important first. */
export function attentionFor(token: string, orders: BuyerOrder[], requests: RequestRow[]): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const r of requests) {
    if (r.status === "countered") items.push({ key: `rq${r.id}`, tone: "amber", title: `Agree to a new date for ${r.poNo}`, detail: "Your merchandiser proposed a different ex-factory date.", cta: "Review and answer", to: `/b/${token}/requests/${r.id}` });
    else if (r.status === "query") items.push({ key: `rq${r.id}`, tone: "amber", title: `Your merchandiser has a question about ${r.poNo}`, detail: "They need your answer before they can go on.", cta: "Answer", to: `/b/${token}/requests/${r.id}` });
  }
  for (const o of orders) {
    if (o.state !== "active") continue;
    if (o.notice && !o.notice.acknowledgedAt) items.push({ key: `n${o.id}`, tone: "red", title: `Delay notice for ${o.poNo}`, detail: `Now expected ${fmtDate(o.notice.expectedExFactory, true)}, instead of ${fmtDate(o.exFactory, true)}. Please acknowledge it.`, cta: "See the details", to: `/b/${token}/orders/${o.id}` });
  }
  return items;
}
