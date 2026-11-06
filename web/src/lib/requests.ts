// Shapes and wording for order requests, shared by the office and buyer screens.

export type RequestStatus = "submitted" | "query" | "countered" | "accepted" | "declined" | "withdrawn";

export interface RequestRow {
  id: number;
  requestNo: string;
  kind: "new_order" | "amendment";
  buyer: string;
  poNo: string;
  style: string;
  colour: string;
  colourHex: string | null;
  exFactory: string;
  totalQty: number;
  status: RequestStatus;
  updatedAt: string;
  createdAt: string;
}

export interface RequestMessage {
  author: "buyer" | "merchandiser";
  event: "submitted" | "message" | "query" | "counter" | "agreed" | "accepted" | "declined" | "withdrawn";
  body: string | null;
  proposedExFactory: string | null;
  at: string;
}

export interface RequestDetailData {
  id: number;
  requestNo: string;
  kind: "new_order" | "amendment";
  poNo: string;
  style: string;
  description: string | null;
  colour: string;
  colourHex: string | null;
  colourPantone: string | null;
  exFactory: string;
  status: RequestStatus;
  sizes: { size: string; qty: number }[];
  totalQty: number;
  createdAt: string;
  updatedAt: string;
  messages: RequestMessage[];
  orderNo: string | null;
  // office only
  buyer?: string;
  orderId?: number | null;
  // buyer only
  canReply?: boolean;
  canAgree?: boolean;
  canWithdraw?: boolean;
}

type Tone = "green" | "amber" | "red" | "";

/** Whose turn it is, in words for each audience. */
export function statusLabel(status: RequestStatus, audience: "office" | "buyer"): { text: string; tone: Tone } {
  const office: Record<RequestStatus, [string, Tone]> = {
    submitted: ["Needs your answer", "amber"],
    query: ["Waiting for the buyer", ""],
    countered: ["Waiting for the buyer", ""],
    accepted: ["Accepted", "green"],
    declined: ["Declined", "red"],
    withdrawn: ["Withdrawn", ""],
  };
  const buyer: Record<RequestStatus, [string, Tone]> = {
    submitted: ["With the merchandiser", ""],
    query: ["Question for you", "amber"],
    countered: ["New date proposed", "amber"],
    accepted: ["Accepted", "green"],
    declined: ["Declined", "red"],
    withdrawn: ["Withdrawn", ""],
  };
  const [text, tone] = (audience === "office" ? office : buyer)[status];
  return { text, tone };
}

export const EVENT_TEXT: Record<RequestMessage["event"], (author: "buyer" | "merchandiser", you: boolean) => string> = {
  submitted: () => "Request submitted",
  message: (a, you) => (a === "buyer" ? (you ? "You replied" : "Buyer replied") : "Merchandiser wrote"),
  query: () => "Merchandiser asked a question",
  counter: () => "Merchandiser proposed a different date",
  agreed: (_, you) => (you ? "You agreed to the new date" : "Buyer agreed to the new date"),
  accepted: () => "Request accepted",
  declined: () => "Request declined",
  withdrawn: (_, you) => (you ? "You withdrew the request" : "Buyer withdrew the request"),
};
