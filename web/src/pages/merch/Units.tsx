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

function CapacityField({ unitId, unitName, process, value: current, onSaved, notify }: {
  unitId: number; unitName: string; process: string; value: number | null; onSaved: () => void; notify: (m: string) => void;
}) {
  const [value, setValue] = useState(current ? String(current) : "");
  const [busy, setBusy] = useState(false);
  const changed = value !== (current ? String(current) : "");
  async function save() {
    setBusy(true);
    try {
      await api(`/api/m/units/${unitId}`, { method: "PATCH", body: { dailyCapacity: value ? Number(value) : null, process } });
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
      <input className="input input-sm num" style={{ width: 110 }} inputMode="numeric" value={value} placeholder="not set" aria-label={`Daily ${process} capacity of ${unitName}`}
        onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))} onKeyDown={(e) => e.key === "Enter" && changed && void save()} />
      <span className="faint small">pcs / day</span>
      {changed && <button className="btn btn-sm btn-primary" disabled={busy} onClick={save}>Save</button>}
    </div>
  );
}

/** The one link a supervisor needs to put the app on their phone. */
function PhoneApp({ notify }: { notify: (m: string) => void }) {
  const link = `${window.location.origin}/install`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      notify("Link copied");
    } catch {
      notify("Select the link and copy it");
    }
  };
  return (
    <section className="card card-pad stack">
      <div>
        <h2>Supervisors' phone app</h2>
        <p className="faint small" style={{ margin: "2px 0 0" }}>
          Send each supervisor this link. It opens a page in Tamil that installs LoomTrack on their phone; they then sign in with their phone number and PIN.
          {!window.isSecureContext && " This address is not https, so phones will not offer to install it."}
        </p>
      </div>
      <div className="row">
        <input className="input input-sm mono" readOnly value={link} style={{ flex: 1, minWidth: 220 }} onFocus={(e) => e.target.select()} aria-label="Install link" />
        <button className="btn btn-sm" onClick={() => void copy()}>Copy</button>
      </div>
    </section>
  );
}

export default function Units() {
  const { data, error, reload } = useApi<{ units: UnitRow[] }>("/api/m/units");
  const [toast, setToast] = useState<string | null>(null);
  const own = data?.units.filter((u) => u.kind === "own") ?? [];
  const jobWork = data?.units.filter((u) => u.kind === "subcontract") ?? [];
  const weeks = own[0]?.processes[0]?.weeks ?? [];

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Units and capacity</h1>
          <p className="sub">
            How many pieces each of our units can do in a working day, for each stage we do ourselves (cutting, stitching, finishing, packing). The capacity check on a new order
            or a buyer's request uses this, with what is already booked, to say whether a date is realistic.
          </p>
        </div>
      </div>
      {error && <div className="banner banner-error">{error}</div>}
      <div className="stack">
        <PhoneApp notify={setToast} />
        <section className="card">
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ paddingLeft: 20 }}>Unit</th>
                  <th>Stage</th>
                  <th>Capacity</th>
                  {weeks.map((w) => <th key={w.from}>Week of {fmtDate(w.from)}</th>)}
                </tr>
              </thead>
              <tbody>
                {own.flatMap((u) => u.processes.map((p, i) => (
                  <tr key={`${u.id}-${p.process}`} style={i === 0 ? { borderTop: "2px solid var(--line)" } : undefined}>
                    <td style={{ paddingLeft: 20 }}>{i === 0 && <b style={{ fontWeight: 500 }}>{u.name}</b>}</td>
                    <td style={{ textTransform: "capitalize" }}>{p.process}</td>
                    <td><CapacityField key={`${u.id}-${p.process}-${p.dailyCapacity}`} unitId={u.id} unitName={u.name} process={p.process} value={p.dailyCapacity} onSaved={() => void reload()} notify={setToast} /></td>
                    {p.weeks.map((w) => <td key={w.from}>{p.dailyCapacity ? <Week w={w} /> : <span className="faint">set capacity</span>}</td>)}
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </section>
        <p className="faint small" style={{ margin: 0 }}>
          How it is worked out: for each stage, every order that still has pieces to do at a unit is spread evenly over the working days that stage has left (Monday to Saturday, minus holidays).
          A new order is spread over the window its plan would give each stage. Up to 85% of a stage's capacity is comfortable, up to 100% is tight, and over 100% needs you to
          confirm. A unit is as full as its tightest stage. A stage with no capacity set is not checked. Milestones and job work are not counted.
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
