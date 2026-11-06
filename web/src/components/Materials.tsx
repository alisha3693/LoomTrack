import { FormEvent, useState } from "react";
import { api } from "../lib/api";
import type { Material, MaterialState } from "../lib/fabric";
import { fmtDate, num } from "../lib/format";
import type { MilestoneRow } from "../lib/types";
import { Modal } from "./ui";

const KIND = { fabric: "Fabric", trim: "Trims", packing: "Packing" } as const;
const STATE_TEXT: Record<MaterialState, string> = { late: "Late", at_risk: "At risk", on_track: "On track", received: "Received" };
const STATE_TONE: Record<MaterialState, string> = { late: "pill-red", at_risk: "pill-amber", on_track: "", received: "pill-green" };

interface Draft {
  kind: Material["kind"];
  name: string;
  supplier: string;
  suppliedBy: "us" | "buyer";
  qty: string;
  unit: string;
  status: Material["status"];
  orderedDate: string;
  expectedDate: string;
  receivedDate: string;
  neededFor: string; // a plan step code, or "" for a specific date
  neededBy: string;
  note: string;
}

const BLANK: Draft = { kind: "trim", name: "", supplier: "", suppliedBy: "us", qty: "", unit: "", status: "not_ordered", orderedDate: "", expectedDate: "", receivedDate: "", neededFor: "STITCH", neededBy: "", note: "" };

const draftOf = (m: Material): Draft => ({
  kind: m.kind, name: m.name, supplier: m.supplier ?? "", suppliedBy: m.suppliedBy, qty: m.qty ? String(m.qty) : "", unit: m.unit ?? "",
  status: m.status, orderedDate: m.orderedDate ?? "", expectedDate: m.expectedDate ?? "", receivedDate: m.receivedDate ?? "",
  neededFor: m.neededFor ?? "", neededBy: m.neededBy, note: m.note ?? "",
});

/** What the order needs before it can be made, and whether each thing will be there when the plan wants it. */
export default function Materials({
  orderId, items, steps, today, active, onChanged, notify,
}: {
  orderId: number;
  items: Material[];
  steps: MilestoneRow[];
  today: string;
  active: boolean;
  onChanged: () => void | Promise<unknown>;
  notify: (message: string) => void;
}) {
  const [editing, setEditing] = useState<{ id: number | null; draft: Draft } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const late = items.filter((m) => m.risk.state === "late").length;
  const risky = items.filter((m) => m.risk.state === "at_risk").length;
  const received = items.filter((m) => m.status === "received").length;

  const run = async (fn: () => Promise<unknown>, done: string) => {
    try {
      await fn();
      notify(done);
      await onChanged();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  const body = (d: Draft) => ({
    kind: d.kind,
    name: d.name.trim(),
    supplier: d.supplier.trim() || null,
    suppliedBy: d.suppliedBy,
    qty: d.qty ? Number(d.qty) : null,
    unit: d.unit.trim() || null,
    status: d.status,
    orderedDate: d.status === "not_ordered" ? null : d.orderedDate || null,
    expectedDate: d.status === "not_ordered" ? null : d.expectedDate || null,
    receivedDate: d.status === "received" ? d.receivedDate || null : null,
    neededFor: d.neededFor || null,
    neededBy: d.neededFor ? null : d.neededBy || null,
    note: d.note.trim() || null,
  });

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      if (editing.id === null) await api(`/api/m/orders/${orderId}/materials`, { body: body(editing.draft) });
      else await api(`/api/m/materials/${editing.id}`, { method: "PATCH", body: body(editing.draft) });
      setEditing(null);
      notify(editing.id === null ? "Added" : "Saved");
      await onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setEditing((s) => (s ? { ...s, draft: { ...s.draft, [k]: e.target.value } } : s));
  const d = editing?.draft;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Materials</h2>
          <div className="faint small">
            {items.length === 0 ? "Nothing tracked yet" : `${received} of ${items.length} received`}
            {late > 0 && <> · <span className="t-red">{late} late</span></>}
            {risky > 0 && <> · <span className="t-amber">{risky} at risk</span></>}
            {" · does not change the delay projection"}
          </div>
        </div>
        {active && (
          <div className="row no-print">
            <button className="btn btn-sm" onClick={() => run(() => api(`/api/m/orders/${orderId}/materials/standard`, { method: "POST" }), "Standard list added")}>Add the standard list</button>
            <button className="btn btn-sm btn-primary" onClick={() => { setError(null); setEditing({ id: null, draft: BLANK }); }}>Add an item</button>
          </div>
        )}
      </div>
      {items.length === 0 ? (
        <div className="card-body faint">Add the fabric, trims and packing this order needs, and see which will arrive too late for the plan.</div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th style={{ paddingLeft: 20 }}>Item</th><th>Needed</th><th>Where it stands</th><th /></tr></thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td style={{ paddingLeft: 20 }}>
                    <b style={{ fontWeight: 500 }}>{m.name}</b> <span className="faint small">{KIND[m.kind]}</span>
                    {m.suppliedBy === "buyer" && <span className="tag" style={{ marginLeft: 6 }}>Buyer supplies</span>}
                    <div className="faint small">
                      {[m.qty ? `${num(m.qty)} ${m.unit ?? ""}`.trim() : null, m.supplier, m.note].filter(Boolean).join(" · ")}
                    </div>
                  </td>
                  <td className="nowrap"><div className="num">{fmtDate(m.neededBy, true)}</div><div className="faint small">{m.neededLabel}</div></td>
                  <td style={{ maxWidth: 380 }}>
                    <span className={`pill ${STATE_TONE[m.risk.state]}`}>{STATE_TEXT[m.risk.state]}</span>
                    <div className={`small ${m.risk.state === "late" ? "t-red" : m.risk.state === "at_risk" ? "t-amber" : "muted"}`} style={{ marginTop: 4 }}>{m.risk.message}</div>
                  </td>
                  <td className="nowrap" style={{ textAlign: "right", paddingRight: 20 }}>
                    {active && (
                      <div className="row no-print" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                        {m.status !== "received" && (
                          <button className="btn btn-sm" onClick={() => run(() => api(`/api/m/materials/${m.id}`, { method: "PATCH", body: { status: "received" } }), `${m.name} received`)}>Received</button>
                        )}
                        <button className="btn btn-ghost btn-sm" onClick={() => { setError(null); setEditing({ id: m.id, draft: { ...draftOf(m), status: m.status === "not_ordered" ? "ordered" : m.status, orderedDate: m.orderedDate ?? today } }); }}>
                          {m.status === "not_ordered" ? "Ordered…" : "Edit"}
                        </button>
                        <button className="btn btn-ghost btn-sm" aria-label={`Remove ${m.name}`}
                          onClick={() => confirm(`Remove ${m.name} from this order?`) && run(() => api(`/api/m/materials/${m.id}`, { method: "DELETE" }), "Removed")}>×</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && d && (
        <Modal title={editing.id === null ? "Add an item" : `Update ${d.name}`} onClose={() => setEditing(null)}>
          <form className="stack" onSubmit={save}>
            <div className="grid-2">
              <label className="field"><span>What</span><input className="input" value={d.name} onChange={set("name")} required maxLength={80} placeholder="Main label" autoFocus /></label>
              <label className="field"><span>Kind</span>
                <select className="select" value={d.kind} onChange={set("kind")}>
                  {(Object.keys(KIND) as Material["kind"][]).map((k) => <option key={k} value={k}>{KIND[k]}</option>)}
                </select>
              </label>
              <label className="field"><span>Quantity (optional)</span>
                <div className="row" style={{ flexWrap: "nowrap" }}>
                  <input className="input" inputMode="decimal" value={d.qty} onChange={(e) => setEditing((s) => (s ? { ...s, draft: { ...s.draft, qty: e.target.value.replace(/[^\d.]/g, "") } } : s))} />
                  <input className="input" style={{ width: 90 }} value={d.unit} onChange={set("unit")} placeholder="kg, pcs" maxLength={12} aria-label="Unit" />
                </div>
              </label>
              <label className="field"><span>Supplier (optional)</span><input className="input" value={d.supplier} onChange={set("supplier")} maxLength={80} /></label>
              <label className="field"><span>Supplied by</span>
                <select className="select" value={d.suppliedBy} onChange={set("suppliedBy")}>
                  <option value="us">Us</option>
                  <option value="buyer">The buyer (free issue)</option>
                </select>
              </label>
              <label className="field"><span>Needed for</span>
                <select className="select" value={d.neededFor} onChange={set("neededFor")}>
                  {steps.filter((s) => s.code !== "EXF").map((s) => <option key={s.code} value={s.code}>{s.name_en} {s.kind === "stage" ? "(when it starts)" : "(when it is due)"}</option>)}
                  <option value="">A specific date…</option>
                </select>
              </label>
              {!d.neededFor && <label className="field"><span>Needed by</span><input className="input" type="date" value={d.neededBy} onChange={set("neededBy")} required /></label>}
              <label className="field"><span>Where it stands</span>
                <select className="select" value={d.status} onChange={set("status")}>
                  <option value="not_ordered">Not ordered</option>
                  <option value="ordered">Ordered</option>
                  <option value="received">Received</option>
                </select>
              </label>
              {d.status !== "not_ordered" && <label className="field"><span>Ordered on</span><input className="input" type="date" max={today} value={d.orderedDate} onChange={set("orderedDate")} /></label>}
              {d.status !== "not_ordered" && <label className="field"><span>Expected on</span><input className="input" type="date" value={d.expectedDate} onChange={set("expectedDate")} /></label>}
              {d.status === "received" && <label className="field"><span>Received on</span><input className="input" type="date" max={today} value={d.receivedDate || today} onChange={set("receivedDate")} /></label>}
            </div>
            <label className="field"><span>Note (optional)</span><input className="input" value={d.note} onChange={set("note")} maxLength={300} /></label>
            {error && <div className="banner banner-error">{error}</div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy}>Save</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
