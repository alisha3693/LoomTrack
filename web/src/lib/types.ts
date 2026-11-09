// Shapes returned by the FastAPI backend. Computed values are camelCase;
// raw database rows (order detail) keep their snake_case column names.

import type { Status } from "./format";
import type { RequestStatus } from "./requests";

import type { ActivityItem } from "./flow";

export interface Meta {
  buyers: { id: number; name: string; country: string | null }[];
  units: { id: number; name: string; kind: "own" | "subcontract"; process: string | null }[];
  templates: { key: string; name: string }[];
  reasons: { code: string; en: string; ta: string }[];
  today: string;
  openRequests: number;
  unreadNotifications: number;
  canReset: boolean;
  testDate: string | null;
  /** Approvals where the buyer asked for changes, so the office has to answer. */
  ai: { mode: "indictrans2" | "keywords"; model?: string; device?: string; reason?: string };
}

export interface BoardOrder {
  id: number;
  orderNo: string;
  poNo: string;
  buyer: string;
  unit: string;
  style: string;
  colour: string;
  colourHex: string | null;
  qty: number;
  exFactory: string;
  shipWeek: string;
  status: Status;
  projectedExFactory: string;
  slackDays: number;
  keyStage: {
    name: string;
    pct: number;
    done: number;
    requiredPerDay: number | null;
    runRate: number;
    rateBasis: "actual" | "planned" | "done";
    workingDaysLeft: number;
  } | null;
  stages: { code: string; name: string; pct: number; state: string }[];
  headline: string | null;
  pendingWarnings: number;
  lastUpdate: string | null;
  /** Approvals waiting on the buyer, and ones the buyer sent back to the office. */
  /** The latest delay notice was confirmed and the buyer has not acknowledged it. */
  noticeUnacknowledged: boolean;
}

export interface StageProjection {
  code: string;
  name: string;
  done: number;
  remaining: number;
  pct: number;
  plannedStart: string;
  plannedEnd: string;
  workingDaysLeft: number;
  requiredPerDay: number | null;
  runRate: number;
  rateBasis: "actual" | "planned" | "done";
  rateWindowDays: number;
  constrainedByUpstream: boolean;
  projectedFinish: string;
  slipDays: number;
  state: "done" | "on_track" | "slipping" | "not_started";
}

export interface Projection {
  status: Status;
  exFactory: string;
  projectedExFactory: string;
  slackDays: number;
  keyStage: string | null;
  stages: StageProjection[];
  reasons: string[];
  overdueMilestones: { code: string; name: string; plannedDate: string }[];
}

export interface MilestoneRow {
  id: number;
  seq: number;
  code: string;
  name_en: string;
  name_ta: string;
  kind: "milestone" | "stage";
  process: string | null;
  planned_start: string | null;
  planned_date: string;
  actual_date: string | null;
  unit_name: string | null;
  unit_kind: "own" | "subcontract" | null;
}

export interface UpdateRow {
  id: string;
  work_date: string;
  qty: number;
  note_text: string | null;
  note_source: "text" | "voice" | null;
  stage: string;
  stage_code: string;
  supervisor: string;
  received_at: string;
  has_reason: number;
  ai_category: string | null;
  ai_translation: string | null;
  ai_confidence: number | null;
  ai_source: "indictrans2" | "keywords" | null;
  ai_error: string | null;
  final_category: string | null;
  changed_at: string | null;
  audio_url: string | null;
  photos: { id: number; buyerVisible: boolean; url: string }[];
}

export interface WarningRow {
  id: number;
  level: "amber" | "red";
  projected_ex_factory: string;
  slack_days: number;
  summary: string;
  buyer_message: string | null;
  state: "pending" | "confirmed" | "dismissed" | "superseded" | "resolved";
  created_at: string;
  decided_at: string | null;
  buyer_seen_at: string | null;
  buyer_ack_at: string | null;
}

export interface DateChangeRow {
  id: number;
  field: string;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  changed_at: string;
  milestone: string | null;
  changed_by_name: string | null;
}

export interface OrderDetail {
  today: string;
  order: {
    id: number;
    buyer_id: number;
    order_no: string;
    po_no: string;
    style: string;
    colour: string;
    colour_hex: string | null;
    colour_pantone: string | null;
    fabric_type: string | null;
    fabric_composition: string | null;
    fabric_gsm: number | null;
    fabric_note: string | null;
    qty_total: number;
    ex_factory: string;
    buyer_name: string;
    unit_name: string;
    template_key: string;
    state: string;
    cancel_reason: string | null;
    cancelled_at: string | null;
    shipped_date: string | null;
    production_complete_at: string | null;
  };
  sizes: { size: string; qty: number }[];
  milestones: MilestoneRow[];
  projection: Projection;
  updates: UpdateRow[];
  warnings: WarningRow[];
  dateChanges: DateChangeRow[];
  attachments: FileItem[];
  activity: ActivityItem[];
  buyerPath: string | null;
  changeRequests: { id: number; requestNo: string; kind: "new_order" | "amendment"; status: RequestStatus; exFactory: string; updatedAt: string }[];
}

export interface SupStage {
  order_id: number;
  order_no: string;
  po_no: string;
  style: string;
  colour: string;
  colour_hex: string | null;
  qty_total: number;
  ex_factory: string;
  milestone_id: number;
  code: string;
  name_en: string;
  name_ta: string;
  planned_start: string;
  planned_date: string;
  done: number;
  today_qty: number;
  target_per_day: number;
  upstream_name_en: string | null;
  upstream_name_ta: string | null;
  waiting_on_en: string[]; // checkpoints and job work the office has not marked done; the stage is locked until they are
  waiting_on_ta: string[];
  ready: number | null; // pieces the stage before has finished that this stage has not worked on yet
}

export interface TemplateStep {
  code: string;
  nameEn: string;
  nameTa: string;
  kind: "stage" | "milestone";
  process: string | null;
  builtin: boolean;
  endOffset: number;
  startOffset: number | null;
  after: string | null; // a stage that starts the day after this step ends
}

export interface TemplateRow {
  id: number;
  key: string;
  name: string;
  builtin: boolean;
  active: boolean;
  usedBy: number;
  steps: TemplateStep[];
}

export interface TemplateList {
  templates: TemplateRow[];
  library: { code: string; nameEn: string; nameTa: string; kind: "stage" | "milestone"; process: string | null; builtin: boolean }[];
  processes: string[]; // the work the app knows by name; a stage's process decides who does it
}

/** A design, pattern, print or fabric file. `url` and the two flags are only sent to the office. */
export interface FileItem {
  id: number;
  kind: "design" | "pattern" | "print" | "fabric" | "other";
  filename: string;
  mime: string;
  size: number;
  uploadedBy: "buyer" | "merchandiser" | "you";
  at: string;
  url?: string;
  buyerVisible?: boolean;
  supervisorVisible?: boolean;
}
