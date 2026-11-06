import { useState } from "react";
import { Toast, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import type { UnitRow } from "../../lib/fabric";
import { fmtDate, num } from "../../lib/format";

function Week({ w }: { w: UnitRow["weeks"][number] }) {
  if (w.utilisation === null) return <span className="faint">—</span>;
  const pct = Math.round(w.utilisation * 100);
  const tone = pct > 100 ? "red" : pct > 85 ? "amber" : "green";
  return (
    <div style={{ minWidth: 90 }}>
      <b className={`num t-${tone}`}>{pct}%</b>
      <div className={`progress ${tone}`} style={{ marginTop: 4 }} aria-hidden="true"><i style={{ width: `${Math.min(100, pct)}%` }} /></div>
      <div className="faint small num">{num(w.booked)} / {num(w.possible)}</div>
    </div>
  );
}

function CapacityField({ u, onSaved, notify }: { u: UnitRow; onSaved: () => void; notify: (m: string) => void }) {
  const [value, setValue] = useState(u.dailyCapacity ? String(u.dailyCapacity) : "");
  const [busy, setBusy] = useState(false);
  const changed = value !== (u.dailyCapacity ? String(u.dailyCapacity) : "");
  async function save() {
    setBusy(true);
    try {
      await api(`/api/m/units/${u.id}`, { method: "PATCH", body: { dailyCapacity: value ? Number(value) : null } });
      notify(value ? "Capacity saved" : "Capacity cleared");
      onSaved();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="row" style={{ flexWrap: "nowrap", gap: 6 }}>
      <input className="input input-sm num" style={{ width: 110 }} inputMode="numeric" value={value} placeholder="not set" aria-label={`Daily capacity of ${u.name}`}
        onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))} onKeyDown={(e) => e.key === "Enter" && changed && void save()} />
      <span className="faint small">pcs / day</span>
      {changed && <button className="btn btn-sm btn-primary" disabled={busy} onClick={save}>Save</button>}
    </div>
  );
}

export default function Units() {
  const { data, error, reload } = useApi<{ units: UnitRow[] }>("/api/m/units");
  const [toast, setToast] = useState<string | null>(null);
  const own = data?.units.filter((u) => u.kind === "own") ?? [];
  const jobWork = data?.units.filter((u) => u.kind === "subcontract") ?? [];
  const weeks = own[0]?.weeks ?? [];

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Units and capacity</h1>
          <p className="sub">
            How many pieces each of our units can stitch in a working day. The capacity check on a new order or a buyer's request uses this, with what is already booked,
            to say whether a date is realistic.
          </p>
        </div>
      </div>
      {error && <div className="banner banner-error">{error}</div>}
      <div className="stack">
        <section className="card">
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ paddingLeft: 20 }}>Unit</th>
                  <th>Stitching capacity</th>
                  {weeks.map((w) => <th key={w.from}>Week of {fmtDate(w.from)}</th>)}
                </tr>
              </thead>
              <tbody>
                {own.map((u) => (
                  <tr key={u.id}>
                    <td style={{ paddingLeft: 20 }}><b style={{ fontWeight: 500 }}>{u.name}</b></td>
                    <td><CapacityField key={`${u.id}-${u.dailyCapacity}`} u={u} onSaved={() => void reload()} notify={setToast} /></td>
                    {u.weeks.map((w) => <td key={w.from}>{u.dailyCapacity ? <Week w={w} /> : <span className="faint">set capacity</span>}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <p className="faint small" style={{ margin: 0 }}>
          How it is worked out: each order still stitching at a unit is spread evenly over the working days it has left (Monday to Saturday, minus holidays). A new order
          is spread over the stitching window its plan would give it. Up to 85% of the unit's capacity is comfortable, up to 100% is tight, and over 100% needs you to
          confirm. Other stages (cutting, finishing, packing) are not checked.
        </p>
        {jobWork.length > 0 && (
          <section className="card card-pad stack" style={{ gap: 6 }}>
            <h2>Job work units</h2>
            <p className="faint small" style={{ margin: 0 }}>Printing and washing units are not checked for capacity here.</p>
            <ul className="reasons">{jobWork.map((u) => <li key={u.id}>{u.name} <span className="faint small">· {u.process}</span></li>)}</ul>
          </section>
        )}
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
