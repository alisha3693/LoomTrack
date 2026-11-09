// Fabric on an order or request, capacity results and material lines: the shapes the API returns, and small helpers.

export interface Fabric {
  type: string | null;
  composition: string | null;
  gsm: number | null;
  note?: string | null;
}

/** Offered as suggestions; anything can be typed. */
export const FABRIC_TYPES = [
  "Single jersey",
  "Slub jersey",
  "Lycra jersey",
  "Interlock",
  "Rib 1x1",
  "Rib 2x2",
  "Pique",
  "Fleece",
  "Fleece, brushed back",
  "French terry",
  "Waffle",
  "Mesh",
];

/** "Single jersey · 95% cotton, 5% elastane · 180 GSM", or null when nothing was given. */
export function fabricLine(f: Fabric | null | undefined): string | null {
  if (!f) return null;
  const parts = [f.type, f.composition, f.gsm ? `${f.gsm} GSM` : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export type Verdict = "fits" | "tight" | "over" | "no_window" | "unknown";

export interface StageFit {
  process: string;
  stage: string;
  verb: string;
  capacity: number | null;
  verdict: Verdict;
  utilisation: number | null;
  booked: number;
  possible: number;
  workingDays: number;
  windowStart: string | null;
  windowEnd: string | null;
  requiredPerDay: number | null;
  summary: string;
}

/** One unit's result: the top-level numbers are those of its tightest stage; `stages` has every checked stage. */
export interface UnitFit {
  unitId: number;
  name: string;
  capacity: number | null;
  verdict: Verdict;
  utilisation: number | null;
  needed: number;
  booked: number;
  possible: number;
  workingDays: number;
  windowStart: string | null;
  windowEnd: string | null;
  requiredPerDay: number | null;
  earliest: { exFactory: string; utilisation: number } | null;
  overlapping: { orderNo: string; poNo: string; qtyLeft: number }[];
  summary: string;
  limitingStage: string;
  limitingProcess: string;
  verb: string;
  notSet: string[];
  stages: StageFit[];
}

export interface UnitRow {
  id: number;
  name: string;
  kind: "own" | "subcontract";
  process: string | null;
  dailyCapacity: number | null;
  weeks: { from: string; booked: number; possible: number; utilisation: number | null }[];
  processes: { process: string; dailyCapacity: number | null; weeks: { from: string; booked: number; possible: number; utilisation: number | null }[] }[];
}
