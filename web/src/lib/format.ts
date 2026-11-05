const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function fmtDate(iso: string | null | undefined, withDay = false): string {
  if (!iso) return "—";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  const s = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return withDay ? `${DAYS[d.getUTCDay()]} ${s}` : s;
}

export function fmtDateTime(sqlite: string | null | undefined): string {
  if (!sqlite) return "—";
  const [date, time] = sqlite.split(" ");
  return `${fmtDate(date)}${time ? ` ${time.slice(0, 5)}` : ""}`;
}

export function addDaysIso(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function num(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString("en-IN");
}

export function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export type Status = "green" | "amber" | "red";

export const STATUS_LABEL: Record<Status, string> = {
  red: "Will miss ex-factory",
  amber: "Behind plan",
  green: "On track",
};
