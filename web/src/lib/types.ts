// Shapes returned by the FastAPI backend. Computed values are camelCase;
// raw database rows (order detail) keep their snake_case column names.

import type { Status } from "./format";

export interface Meta {
  buyers: { id: number; name: string; country: string | null }[];
  units: { id: number; name: string; kind: "own" | "subcontract"; process: string | null }[];
  templates: { key: string; name: string }[];
  reasons: { code: string; en: string; ta: string }[];
  today: string;
  openRequests: number;
  ai: { mode: "ollama" | "keywords"; model?: string; reason?: string };
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
  ai_source: "ollama" | "keywords" | null;
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
    order_no: string;
    po_no: string;
    style: string;
    colour: string;
    colour_hex: string | null;
    colour_pantone: string | null;
    qty_total: number;
    ex_factory: string;
    buyer_name: string;
    unit_name: string;
    template_key: string;
    state: string;
  };
  sizes: { size: string; qty: number }[];
  milestones: MilestoneRow[];
  projection: Projection;
  updates: UpdateRow[];
  warnings: WarningRow[];
  dateChanges: DateChangeRow[];
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
}
