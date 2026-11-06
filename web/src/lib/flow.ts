// What passes between the buyer and the merchandiser: inbox entries, approvals and the order timeline.

export interface InboxItem {
  kind: "order" | "request";
  id: number;
  title: string;
  subtitle: string;
  party: string;
  count: number;
  last: { author: "buyer" | "merchandiser"; text: string; at: string };
  turn: "you" | "them";
  unread: boolean;
}

export type ApprovalStatus = "requested" | "approved" | "changes" | "withdrawn";

export interface ApprovalEvent { actor: "buyer" | "merchandiser"; action: string; text: string; note: string | null; at: string }

export interface Approval {
  id: number;
  orderId: number;
  poNo: string;
  style: string;
  kind: string;
  kindLabel: string;
  title: string;
  note: string | null;
  status: ApprovalStatus;
  requestedAt: string;
  decidedAt: string | null;
  completesStep: string | null;
  events: ApprovalEvent[];
  /** Office only. */
  buyer?: string;
  buyerSeenAt?: string | null;
}

export interface ActivityItem { at: string; kind: "date" | "step" | "message" | "request" | "approval" | "notice" | "material"; actor: string; title: string; detail: string | null }

export const APPROVAL_KINDS: { key: string; label: string }[] = [
  { key: "fit_sample", label: "Fit sample" },
  { key: "pp_sample", label: "Pre-production sample" },
  { key: "lab_dip", label: "Lab dip / colour" },
  { key: "packaging", label: "Packaging" },
  { key: "other", label: "Something else" },
];

export const isOpenApproval = (a: Approval) => a.status === "requested" || a.status === "changes";
