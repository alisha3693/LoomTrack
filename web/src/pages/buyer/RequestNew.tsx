import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { fmtSize, KIND_LABEL, Kind } from "../../components/Attachments";
import { FABRIC_TYPES } from "../../lib/fabric";
import { addDaysIso, num } from "../../lib/format";
import BuyerFrame from "./BuyerFrame";

const DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"].map((size) => ({ size, qty: "" }));

export default function RequestNew() {
  const { token = "" } = useParams();
  return <BuyerFrame token={token}>{(_name, today) => <Form token={token} today={today} />}</BuyerFrame>;
}

function Form({ token, today }: { token: string; today: string }) {
  const nav = useNavigate();
  const [f, setF] = useState({ poNo: "", style: "", description: "", colour: "", pantone: "", hex: "", exFactory: "", fabricType: "", fabricComposition: "", fabricGsm: "", fabricNote: "" });
  const [sizes, setSizes] = useState(DEFAULT_SIZES);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<{ file: File; kind: Kind }[]>([]);
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
    if (f.fabricGsm && (Number(f.fabricGsm) < 50 || Number(f.fabricGsm) > 800)) return setError("Fabric weight (GSM) is usually between 50 and 800.");
    setBusy(true);
    try {
      const r = await api<{ id: number }>(`/api/b/${token}/requests`, {
        body: {
          poNo: f.poNo.trim(), style: f.style.trim(), description: f.description.trim() || null, colour: f.colour.trim(),
          colourPantone: f.pantone.trim() || null, colourHex: f.hex || null, exFactory: f.exFactory, sizes: rows,
          fabricType: f.fabricType.trim() || null, fabricComposition: f.fabricComposition.trim() || null,
          fabricGsm: f.fabricGsm ? Number(f.fabricGsm) : null, fabricNote: f.fabricNote.trim() || null,
        },
      });
      // The request exists now; add the files one by one so a bad file does not lose the request.
      const failed: string[] = [];
      for (const p of picked) {
        const form = new FormData();
        form.append("kind", p.kind);
        form.append("file", p.file);
        try {
          await api(`/api/b/${token}/requests/${r.id}/attachments`, { form });
        } catch (e) {
          failed.push(`${p.file.name} (${(e as Error).message.replace(/\.$/, "")})`);
        }
      }
      nav(`/b/${token}/requests/${r.id}`, { state: { uploadErrors: failed } });
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
        <h2>Fabric (optional)</h2>
        <p className="faint small" style={{ margin: 0 }}>If you know what you want it made from. We will confirm or suggest an alternative.</p>
        <div className="grid-2">
          <label className="field"><span>Fabric type</span>
            <input className="input" list="fabric-types" value={f.fabricType} onChange={set("fabricType")} maxLength={60} placeholder="Single jersey" />
            <datalist id="fabric-types">{FABRIC_TYPES.map((t) => <option key={t} value={t} />)}</datalist>
          </label>
          <label className="field"><span>Weight (GSM)</span>
            <input className="input num" inputMode="numeric" value={f.fabricGsm} onChange={(e) => setF((x) => ({ ...x, fabricGsm: e.target.value.replace(/\D/g, "").slice(0, 3) }))} placeholder="180" />
          </label>
          <label className="field"><span>Composition</span>
            <input className="input" value={f.fabricComposition} onChange={set("fabricComposition")} maxLength={120} placeholder="95% cotton, 5% elastane" />
          </label>
          <label className="field"><span>Note (fabric code, certification, finish)</span>
            <input className="input" value={f.fabricNote} onChange={set("fabricNote")} maxLength={200} />
          </label>
        </div>
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

      <section className="card card-pad stack">
        <h2>Designs, patterns, prints and fabric (optional)</h2>
        <p className="faint small" style={{ margin: 0 }}>PDF, images, Photoshop, ZIP, Excel/Word or DXF. Up to 10 files, 15 MB each. Only you and our merchandiser can see them.</p>
        {picked.map((p, i) => (
          <div key={i} className="row" style={{ justifyContent: "space-between" }}>
            <span>{p.file.name} <span className="faint small">{fmtSize(p.file.size)}</span></span>
            <span className="row">
              <select className="select select-sm" style={{ width: "auto" }} aria-label="Kind of file" value={p.kind}
                onChange={(e) => setPicked((all) => all.map((x, j) => (j === i ? { ...x, kind: e.target.value as Kind } : x)))}>
                {(Object.keys(KIND_LABEL) as Kind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
              </select>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPicked((all) => all.filter((_, j) => j !== i))}>Remove</button>
            </span>
          </div>
        ))}
        <label className="btn btn-sm" style={{ alignSelf: "flex-start", cursor: "pointer" }}>
          Add files
          <input type="file" multiple hidden accept=".pdf,.ai,.png,.jpg,.jpeg,.webp,.gif,.tif,.tiff,.psd,.zip,.xlsx,.docx,.dxf"
            onChange={(e) => { const fs = Array.from(e.target.files ?? []); setPicked((all) => [...all, ...fs.map((file) => ({ file, kind: "design" as Kind }))].slice(0, 10)); e.target.value = ""; }} />
        </label>
      </section>

      {error && <div className="banner banner-error">{error}</div>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-ghost" onClick={() => nav(`/b/${token}`)}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>Send request</button>
      </div>
    </form>
  );
}
