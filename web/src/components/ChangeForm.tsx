import { FormEvent, useState } from "react";
import { addDaysIso, fmtDate, num } from "../lib/format";

export interface ChangeBody {
  exFactory?: string;
  sizes?: { size: string; qty: number }[];
  reason: string;
}

/**
 * New ex-factory date and/or new quantities for an order that already exists. Only what the person
 * actually changed is sent. Used by the buyer ("Request a change") and the office ("Record a change").
 */
export default function ChangeForm({
  currentDate, currentSizes, today, reasonLabel, submitLabel, onSubmit, onCancel,
}: {
  currentDate: string;
  currentSizes: { size: string; qty: number }[];
  today: string;
  reasonLabel: string;
  submitLabel: string;
  onSubmit: (body: ChangeBody) => Promise<void>;
  onCancel: () => void;
}) {
  const [date, setDate] = useState(currentDate);
  const [sizes, setSizes] = useState(currentSizes.map((s) => ({ size: s.size, qty: String(s.qty) })));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const total = sizes.reduce((a, s) => a + (Number(s.qty) || 0), 0);
  const was = currentSizes.reduce((a, s) => a + s.qty, 0);
  const rows = sizes.filter((s) => s.size.trim() && Number(s.qty) > 0).map((s) => ({ size: s.size.trim().toUpperCase(), qty: Number(s.qty) }));
  const sameSizes = rows.length === currentSizes.length && rows.every((r, i) => r.size === currentSizes[i].size && r.qty === currentSizes[i].qty);
  const dateChanged = date !== currentDate;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!dateChanged && sameSizes) return setError("Change the date or a quantity first.");
    if (!rows.length) return setError("The quantities add up to zero.");
    setBusy(true);
    try {
      await onSubmit({ exFactory: dateChanged ? date : undefined, sizes: sameSizes ? undefined : rows, reason: reason.trim() });
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <label className="field"><span>Ex-factory date <span className="faint">(now {fmtDate(currentDate, true)})</span></span>
        <input className="input" type="date" min={addDaysIso(today, 1)} value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>

      <div className="stack" style={{ gap: 6 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="small muted">Quantities by size</span>
          <span className="small muted">Total <b className="num">{num(total)}</b> pcs{total !== was ? ` (was ${num(was)})` : ""}</span>
        </div>
        <div className="row" style={{ alignItems: "flex-end" }}>
          {sizes.map((s, i) => (
            <div key={i} className="field" style={{ width: 92 }}>
              <input className="input input-sm" aria-label="Size" value={s.size} onChange={(e) => setSizes((all) => all.map((x, j) => (j === i ? { ...x, size: e.target.value } : x)))} />
              <input className="input num" aria-label={`Quantity ${s.size}`} inputMode="numeric" value={s.qty} placeholder="0"
                onChange={(e) => setSizes((all) => all.map((x, j) => (j === i ? { ...x, qty: e.target.value.replace(/\D/g, "") } : x)))} />
            </div>
          ))}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSizes((all) => [...all, { size: "", qty: "" }])}>+ Size</button>
        </div>
        <span className="faint small">Set a size to 0 to remove it.</span>
      </div>

      <label className="field"><span>{reasonLabel}</span>
        <textarea className="textarea" rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} required />
      </label>
      {error && <div className="banner banner-error">{error}</div>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy || !reason.trim()}>{submitLabel}</button>
      </div>
    </form>
  );
}
