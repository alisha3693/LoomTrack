import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { addDaysIso, fmtDate, num } from "../../lib/format";
import { Swatch } from "../../components/ui";
import { useMeta } from "./OfficeShell";

interface PlanItem {
  seq: number;
  code: string;
  nameEn: string;
  kind: "milestone" | "stage";
  process: string | null;
  outsourced: boolean;
  plannedStart: string | null;
  plannedDate: string;
}

const DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"].map((size) => ({ size, qty: "" }));

export default function OrderNew() {
  const meta = useMeta();
  const nav = useNavigate();
  const [form, setForm] = useState({ poNo: "", buyerId: "", style: "", colour: "", exFactory: "", unitId: "", templateKey: "basic" });
  const [sizes, setSizes] = useState<{ size: string; qty: string }[]>(DEFAULT_SIZES);
  const [hex, setHex] = useState("");
  const [pantone, setPantone] = useState("");
  const [plan, setPlan] = useState<PlanItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const total = sizes.reduce((a, s) => a + (Number(s.qty) || 0), 0);
  const hexOk = /^#[0-9A-Fa-f]{6}$/.test(hex);
  // Accept "1f2a44" as well as "#1F2A44".
  const tidyHex = () => setHex((h) => (/^[0-9A-Fa-f]{6}$/.test(h) ? `#${h.toUpperCase()}` : h.toUpperCase()));
  const minDate = meta ? addDaysIso(meta.today, 1) : undefined;

  // Regenerate the TNA plan whenever template or ex-factory changes.
  useEffect(() => {
    if (!form.exFactory || !form.templateKey) return setPlan([]);
    let live = true;
    api<{ items: PlanItem[] }>("/api/m/plan-preview", { body: { templateKey: form.templateKey, exFactory: form.exFactory } })
      .then((r) => live && setPlan(r.items))
      .catch(() => live && setPlan([]));
    return () => {
      live = false;
    };
  }, [form.exFactory, form.templateKey]);

  const editPlan = (code: string, key: "plannedStart" | "plannedDate", value: string) =>
    setPlan((p) => p.map((it) => (it.code === code ? { ...it, [key]: value } : it)));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const sizeRows = sizes.filter((s) => s.size.trim() && Number(s.qty) > 0).map((s) => ({ size: s.size.trim(), qty: Number(s.qty) }));
    if (!sizeRows.length) return setError("Enter at least one size quantity.");
    if (hex && !hexOk) return setError("Colour hex must look like #1F2A44.");
    setBusy(true);
    try {
      const r = await api<{ id: number }>("/api/m/orders", {
        body: {
          ...form,
          poNo: form.poNo.trim(),
          buyerId: Number(form.buyerId),
          colourHex: hex || null,
          colourPantone: pantone.trim() || null,
          unitId: Number(form.unitId),
          sizes: sizeRows,
          milestones: plan.filter((p) => p.code !== "EXF").map((p) => ({ code: p.code, plannedStart: p.plannedStart, plannedDate: p.plannedDate })),
        },
      });
      nav(`/m/orders/${r.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>New order</h1>
          <p className="sub">The time-and-action plan is worked back from the ex-factory date. Adjust any date before saving.</p>
        </div>
      </div>

      <form className="stack" onSubmit={submit}>
        <section className="card card-pad stack">
          <h2>Purchase order</h2>
          <p className="faint small" style={{ margin: 0 }}>We assign our own order number (LT-year-number) when you save. The PO number is the buyer's, exactly as on their document.</p>
          <div className="grid-2">
            <label className="field"><span>Buyer's PO number</span><input className="input" value={form.poNo} onChange={set("poNo")} placeholder="B-PO-88350" required /></label>
            <label className="field"><span>Buyer</span>
              <select className="select" value={form.buyerId} onChange={set("buyerId")} required>
                <option value="">Choose…</option>
                {meta?.buyers.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Style</span><input className="input" value={form.style} onChange={set("style")} placeholder="Men's crew neck tee" required /></label>
            <label className="field"><span>Colour name</span><input className="input" value={form.colour} onChange={set("colour")} placeholder="Navy" required /></label>
            <label className="field"><span>Pantone reference (optional)</span><input className="input" value={pantone} onChange={(e) => setPantone(e.target.value)} placeholder="19-4024 TCX" maxLength={30} /></label>
            <div className="field">
              <span>Colour swatch, hex (optional)</span>
              <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                <input type="color" className="color-pick" aria-label="Pick a colour" value={hexOk ? hex : "#ffffff"} onChange={(e) => setHex(e.target.value.toUpperCase())} />
                <input className="input" value={hex} onChange={(e) => setHex(e.target.value.trim())} onBlur={tidyHex} placeholder="#1F2A44" maxLength={7} aria-label="Colour hex" />
                {hexOk ? <span className="swatch swatch-lg" style={{ background: hex }} title="Approximate on screen" /> : <span className="swatch swatch-lg" style={{ background: "transparent", borderStyle: "dashed" }} />}
              </div>
              <span className="faint small">The Pantone reference is the real colour spec. The swatch is only an approximation on screen.</span>
            </div>
            <label className="field"><span>Ex-factory date</span><input className="input" type="date" min={minDate} value={form.exFactory} onChange={set("exFactory")} required /></label>
            <label className="field"><span>Production unit</span>
              <select className="select" value={form.unitId} onChange={set("unitId")} required>
                <option value="">Choose…</option>
                {meta?.units.filter((u) => u.kind === "own").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </label>
          </div>
        </section>

        <section className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Sizes</h2>
            <span className="muted">Total <b className="num">{num(total)}</b> pcs</span>
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
        </section>

        <section className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Time-and-action plan</h2>
            <span className="faint small"><Link to="/m/templates">Manage templates</Link></span>
            <select className="select select-sm" style={{ width: "auto" }} value={form.templateKey} onChange={set("templateKey")} aria-label="TNA template">
              {meta?.templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
            </select>
          </div>
          {plan.length === 0 ? (
            <p className="faint">Pick an ex-factory date to generate the plan.</p>
          ) : (
            <div className="table-scroll">
              <table className="table">
                <thead><tr><th>Step</th><th>Type</th><th>Start</th><th>Due</th></tr></thead>
                <tbody>
                  {plan.map((p) => (
                    <tr key={p.code}>
                      <td><b style={{ fontWeight: 500 }}>{p.nameEn}</b>{p.outsourced ? <span className="faint small"> · job work</span> : null}</td>
                      <td className="muted">{p.kind === "stage" ? "Production" : "Milestone"}</td>
                      <td>{p.plannedStart ? <input type="date" className="input input-sm" value={p.plannedStart} onChange={(e) => editPlan(p.code, "plannedStart", e.target.value)} /> : <span className="faint">—</span>}</td>
                      <td>
                        {p.code === "EXF" ? <b>{fmtDate(p.plannedDate, true)}</b> : <input type="date" className="input input-sm" value={p.plannedDate} onChange={(e) => editPlan(p.code, "plannedDate", e.target.value)} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {error && <div className="banner banner-error">{error}</div>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={() => nav(-1)}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Create order</button>
        </div>
      </form>
    </main>
  );
}
