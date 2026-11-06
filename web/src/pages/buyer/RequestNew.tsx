import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { addDaysIso, num } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

const DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"].map((size) => ({ size, qty: "" }));

export default function RequestNew() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token}>{(_name, today) => <Form token={token} today={today} />}</BuyerFrame>;
}

function Form({ token, today }: { token: string; today: string }) {
  const nav = useNavigate();
  const [f, setF] = useState({ poNo: "", style: "", description: "", colour: "", pantone: "", hex: "", exFactory: "" });
  const [sizes, setSizes] = useState(DEFAULT_SIZES);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  const total = sizes.reduce((a, s) => a + (Number(s.qty) || 0), 0);
  const hexOk = /^#[0-9A-Fa-f]{6}$/.test(f.hex);
  const tidyHex = () => setF((x) => ({ ...x, hex: /^[0-9A-Fa-f]{6}$/.test(x.hex) ? `#${x.hex.toUpperCase()}` : x.hex.toUpperCase() }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const rows = sizes.filter((s) => s.size.trim() && Number(s.qty) > 0).map((s) => ({ size: s.size.trim(), qty: Number(s.qty) }));
    if (!rows.length) return setError("Enter at least one size quantity.");
    if (f.hex && !hexOk) return setError("The colour hex must look like #1F2A44.");
    setBusy(true);
    try {
      const r = await api<{ id: number }>(`/api/b/${token}/requests`, {
        body: {
          poNo: f.poNo.trim(), style: f.style.trim(), description: f.description.trim() || null, colour: f.colour.trim(),
          colourPantone: f.pantone.trim() || null, colourHex: f.hex || null, exFactory: f.exFactory, sizes: rows,
        },
      });
      nav(`/b/${token}/requests/${r.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <div>
        <h2 style={{ fontSize: 22 }}>New order request</h2>
        <p className="muted">Tell us what you need. Your merchandiser will confirm it, ask a question, or suggest a different date.</p>
      </div>

      <section className="card card-pad stack">
        <div className="grid-2">
          <label className="field"><span>Your PO number</span><input className="input" value={f.poNo} onChange={set("poNo")} required placeholder="B-PO-88350" /></label>
          <label className="field"><span>Style</span><input className="input" value={f.style} onChange={set("style")} required placeholder="Men's raglan tee" /></label>
          <label className="field"><span>Colour name</span><input className="input" value={f.colour} onChange={set("colour")} required placeholder="Charcoal" /></label>
          <label className="field"><span>Pantone reference (optional)</span><input className="input" value={f.pantone} onChange={set("pantone")} maxLength={30} placeholder="19-3906 TCX" /></label>
          <div className="field">
            <span>Colour swatch, hex (optional)</span>
            <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              <input type="color" className="color-pick" aria-label="Pick a colour" value={hexOk ? f.hex : "#ffffff"} onChange={(e) => setF((x) => ({ ...x, hex: e.target.value.toUpperCase() }))} />
              <input className="input" value={f.hex} onChange={(e) => setF((x) => ({ ...x, hex: e.target.value.trim() }))} onBlur={tidyHex} maxLength={7} placeholder="#36454F" aria-label="Colour hex" />
              <span className="swatch swatch-lg" style={hexOk ? { background: f.hex } : { background: "transparent", borderStyle: "dashed" }} />
            </div>
          </div>
          <label className="field"><span>Ex-factory date you need</span><input className="input" type="date" min={addDaysIso(today, 1)} value={f.exFactory} onChange={set("exFactory")} required /></label>
        </div>
        <label className="field"><span>Notes (optional)</span>
          <textarea className="textarea" rows={3} maxLength={1000} value={f.description} onChange={set("description")} placeholder="Construction, trims, packing, anything we should know" />
        </label>
      </section>

      <section className="card card-pad stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Quantities by size</h2>
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

      {error && <div className="banner banner-error">{error}</div>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-ghost" onClick={() => nav(`/b/${token}`)}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>Send request</button>
      </div>
    </form>
  );
}
