// What the buyer's pages know about an order, and what should be put in front of them.

import type { AttentionItem } from "../components/Attention";
import type { Notice } from "../components/NoticeCard";
import type { BuyerMaterial, Fabric } from "./fabric";
import type { Approval } from "./flow";
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
  materials: BuyerMaterial[];
  /** `unread` is true when the office wrote last and the buyer has not opened it. */
  lastMessage: { author: "buyer" | "merchandiser"; at: string; count: number; unread: boolean } | null;
  qty: number;
  sizes: { size: string; qty: number }[];
  exFactory: string;
  state: string;
  notice: Notice | null;
  overallPct: number;
  milestones: { code: string; name: string; kind: "milestone" | "stage"; plannedDate: string; actualDate: string | null; pct: number; done: number | null }[];
  attachments: FileItem[];
  photos: { id: number; date: string; stage: string }[];
  dateChanges: { field: string; oldValue: string | null; newValue: string | null; reason: string; changedAt: string; milestone: string | null }[];
}

export interface BuyerData {
  buyer: { name: string; country: string | null };
  today: string;
  orders: BuyerOrder[];
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
export function attentionFor(token: string, orders: BuyerOrder[], requests: RequestRow[], approvals: Approval[]): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const a of approvals) {
    if (a.status === "requested") items.push({ key: `ap${a.id}`, tone: "amber", title: `Approve: ${a.title}`, detail: `For ${a.poNo}. ${a.completesStep ? "Approving it completes the plan step." : "Your merchandiser is waiting for your decision."}`, cta: "Review and decide", to: `/b/${token}/approvals` });
  }
  for (const r of requests) {
    if (r.status === "countered") items.push({ key: `rq${r.id}`, tone: "amber", title: `Agree to a new date for ${r.poNo}`, detail: "Your merchandiser proposed a different ex-factory date.", cta: "Review and answer", to: `/b/${token}/requests/${r.id}` });
    else if (r.status === "query") items.push({ key: `rq${r.id}`, tone: "amber", title: `Your merchandiser has a question about ${r.poNo}`, detail: "They need your answer before they can go on.", cta: "Answer", to: `/b/${token}/requests/${r.id}` });
  }
  for (const o of orders) {
    if (o.state !== "active") continue;
    if (o.notice && !o.notice.acknowledgedAt) items.push({ key: `n${o.id}`, tone: "red", title: `Delay notice for ${o.poNo}`, detail: `Now expected ${fmtDate(o.notice.expectedExFactory, true)}, instead of ${fmtDate(o.exFactory, true)}. Please acknowledge it.`, cta: "See the details", to: `/b/${token}/orders/${o.id}` });
    if (o.lastMessage?.unread) {
      items.push({ key: `m${o.id}`, tone: "blue", title: `New reply about ${o.poNo}`, detail: "Your merchandiser wrote to you.", cta: "Read it", to: `/b/${token}/orders/${o.id}?tab=messages` });
    }
    const owed = o.materials.filter((m) => m.suppliedBy === "buyer" && !m.received);
    if (owed.length) items.push({ key: `f${o.id}`, tone: "amber", title: `We are waiting for ${owed.map((m) => m.name.toLowerCase()).join(", ")} from you`, detail: `For ${o.poNo}. Production cannot use it until it arrives.`, cta: "See the materials", to: `/b/${token}/orders/${o.id}?tab=materials` });
  }
  return items;
}
