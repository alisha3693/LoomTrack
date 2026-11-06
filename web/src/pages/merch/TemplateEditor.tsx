import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { addDaysIso, fmtDate } from "../../lib/format";
import { useApi } from "../../components/ui";
import type { TemplateList, TemplateStep } from "../../lib/types";
import { useMeta, useReloadMeta } from "./OfficeShell";

interface Row {
  id: number;
  code: string | null; // null = a new step typed in here
  nameEn: string;
  nameTa: string;
  kind: "stage" | "milestone";
  process: string;
  start: string; // days before ex-factory the stage starts
  end: string; // days before ex-factory the step ends
  builtin: boolean;
  savedName: string; // to know whether a custom step was renamed
  savedNameTa: string;
}

interface PreviewItem { code: string; nameEn: string; kind: string; plannedStart: string | null; plannedDate: string }

let nextId = 1;
const blank = (kind: "stage" | "milestone"): Row => ({
  id: nextId++, code: null, nameEn: "", nameTa: "", kind, process: "", start: kind === "stage" ? "" : "", end: "",
  builtin: false, savedName: "", savedNameTa: "",
});
const fromStep = (s: TemplateStep | { code: string; nameEn: string; nameTa: string; kind: "stage" | "milestone"; process: string | null; builtin: boolean; endOffset?: number; startOffset?: number | null }): Row => ({
  id: nextId++, code: s.code, nameEn: s.nameEn, nameTa: s.nameTa, kind: s.kind, process: s.process ?? "",
  start: s.startOffset != null ? String(s.startOffset) : "", end: s.endOffset != null ? String(s.endOffset) : "",
  builtin: s.builtin, savedName: s.nameEn, savedNameTa: s.nameTa,
});

export default function TemplateEditor() {
  const { id } = useParams();
  const [search] = useSearchParams();
  const copyOf = search.get("copy");
  const nav = useNavigate();
  const meta = useMeta();
  const reloadMeta = useReloadMeta();
  const { data } = useApi<TemplateList>("/api/m/templates?retired=true");

  const [name, setName] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exFactory, setExFactory] = useState("");
  const [preview, setPreview] = useState<PreviewItem[]>([]);
  const [previewNote, setPreviewNote] = useState<string | null>(null);

  const editing = id ? data?.templates.find((t) => t.id === Number(id)) : undefined;
  const source = editing ?? (copyOf ? data?.templates.find((t) => t.id === Number(copyOf)) : undefined);

  // Fill the form once: from the template being edited, from one being copied, or start with one stage.
  useEffect(() => {
    if (!data || ready) return;
    if (id && !editing) return;
    if (source) {
      setName(editing ? source.name : `${source.name} (copy)`);
      setRows(source.steps.filter((s) => s.code !== "EXF").map(fromStep));
    } else {
      setRows([blank("stage")]);
    }
    setReady(true);
  }, [data, ready, id, editing, source]);

  useEffect(() => {
    if (meta && !exFactory) setExFactory(addDaysIso(meta.today, 90));
  }, [meta, exFactory]);

  const set = (rowId: number, patch: Partial<Row>) => setRows((all) => all.map((r) => (r.id === rowId ? { ...r, ...patch } : r)));
  const used = useMemo(() => new Set(rows.map((r) => r.code).filter(Boolean)), [rows]);
  const library = (data?.library ?? []).filter((s) => !used.has(s.code));
  const sortByEnd = () => setRows((all) => [...all].sort((a, b) => (Number(b.end) || 0) - (Number(a.end) || 0)));

  const payload = () =>
    rows.map((r) =>
      r.code
        ? { code: r.code, endOffset: Number(r.end), startOffset: r.kind === "stage" ? Number(r.start) : null }
        : { nameEn: r.nameEn.trim(), nameTa: r.nameTa.trim() || null, kind: r.kind, process: r.kind === "stage" ? r.process.trim() : null,
            endOffset: Number(r.end), startOffset: r.kind === "stage" ? Number(r.start) : null },
    );
  const complete = rows.length > 0 && rows.every((r) => r.end !== "" && (r.kind === "milestone" || r.start !== "") && (r.code || r.nameEn.trim()));

  // Example dates for the layout as it stands, so the effect of an offset is visible before saving.
  useEffect(() => {
    if (!ready || !exFactory || !complete) return setPreview([]);
    let live = true;
    const t = setTimeout(() => {
      api<{ items: PreviewItem[] }>("/api/m/templates/preview", { body: { exFactory, steps: payload() } })
        .then((r) => { if (live) { setPreview(r.items); setPreviewNote(null); } })
        .catch((e: Error) => { if (live) { setPreview([]); setPreviewNote(e.message); } });
    }, 350);
    return () => { live = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, exFactory, ready]);

  async function save() {
    setError(null);
    if (!complete) return setError("Fill in a name and the timing of every step.");
    setBusy(true);
    try {
      // Renamed custom steps change for every template and order that uses them.
      for (const r of rows) {
        if (r.code && !r.builtin && (r.nameEn.trim() !== r.savedName || r.nameTa.trim() !== r.savedNameTa)) {
          await api(`/api/m/steps/${r.code}`, { method: "PATCH", body: { nameEn: r.nameEn.trim(), nameTa: r.nameTa.trim() || r.nameEn.trim() } });
        }
      }
      if (editing) await api(`/api/m/templates/${editing.id}`, { method: "PUT", body: { name: name.trim(), steps: payload() } });
      else await api("/api/m/templates", { body: { name: name.trim(), steps: payload() } });
      reloadMeta();
      nav("/m/templates");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (id && data && !editing) return <main className="page"><div className="banner banner-error">That template was not found.</div></main>;

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>{editing ? "Edit template" : copyOf ? "Copy template" : "New template"}</h1>
          <p className="sub">
            Each step has two timings, counted in calendar days before ex-factory. A production stage starts earlier than it ends, so its start is the bigger number.
            Ex-factory is added automatically as the last step.
          </p>
        </div>
      </div>

      <div className="stack">
        <section className="card card-pad stack">
          <label className="field"><span>Template name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Embroidered polo" maxLength={60} /></label>
          {editing && editing.usedBy > 0 && (
            <div className="banner">{editing.usedBy} order{editing.usedBy === 1 ? " uses" : "s use"} this template. Saving changes affects only new orders.</div>
          )}
        </section>

        <section className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Steps</h2>
            <button className="btn btn-ghost btn-sm" onClick={sortByEnd} type="button">Sort by end day</button>
          </div>
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Step</th><th>Type</th><th>Process</th><th title="Days before ex-factory">Starts</th><th title="Days before ex-factory">Ends</th><th /></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const locked = r.code !== null && r.builtin;
                  return (
                    <tr key={r.id}>
                      <td style={{ minWidth: 200 }}>
                        {locked ? <b style={{ fontWeight: 500 }}>{r.nameEn}</b> : (
                          <div className="stack" style={{ gap: 4 }}>
                            <input className="input input-sm" aria-label="Step name" placeholder="Step name" value={r.nameEn} onChange={(e) => set(r.id, { nameEn: e.target.value })} />
                            <input className="input input-sm" aria-label="Tamil name" placeholder="Tamil name (shown to supervisors)" value={r.nameTa} onChange={(e) => set(r.id, { nameTa: e.target.value })} />
                          </div>
                        )}
                      </td>
                      <td>
                        {r.code ? <span className="muted">{r.kind === "stage" ? "Production" : "Milestone"}</span> : (
                          <select className="select select-sm" aria-label="Type" value={r.kind} onChange={(e) => set(r.id, { kind: e.target.value as Row["kind"], start: "" })}>
                            <option value="stage">Production</option><option value="milestone">Milestone</option>
                          </select>
                        )}
                      </td>
                      <td>
                        {r.kind !== "stage" ? <span className="faint">—</span> : r.code ? <span className="muted">{r.process || "—"}</span> : (
                          <input className="input input-sm" aria-label="Process" placeholder="embroidery" style={{ width: 120 }} value={r.process} onChange={(e) => set(r.id, { process: e.target.value })} />
                        )}
                      </td>
                      <td>{r.kind === "stage"
                        ? <input className="input input-sm num" aria-label="Starts, days before ex-factory" inputMode="numeric" style={{ width: 70 }} value={r.start} onChange={(e) => set(r.id, { start: e.target.value.replace(/\D/g, "") })} />
                        : <span className="faint">—</span>}</td>
                      <td><input className="input input-sm num" aria-label="Ends, days before ex-factory" inputMode="numeric" style={{ width: 70 }} value={r.end} onChange={(e) => set(r.id, { end: e.target.value.replace(/\D/g, "") })} /></td>
                      <td><button className="btn btn-ghost btn-sm" type="button" aria-label="Remove step" onClick={() => setRows((all) => all.filter((x) => x.id !== r.id))}>Remove</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="row">
            <button className="btn btn-sm" type="button" onClick={() => setRows((a) => [...a, blank("stage")])}>+ New production stage</button>
            <button className="btn btn-sm" type="button" onClick={() => setRows((a) => [...a, blank("milestone")])}>+ New milestone</button>
            <select className="select select-sm" style={{ width: "auto" }} aria-label="Add an existing step" value=""
              onChange={(e) => { const s = library.find((x) => x.code === e.target.value); if (s) setRows((a) => [...a, fromStep({ ...s })]); }}>
              <option value="">Add an existing step…</option>
              {library.map((s) => <option key={s.code} value={s.code}>{s.nameEn} ({s.kind === "stage" ? "production" : "milestone"})</option>)}
            </select>
          </div>
        </section>

        <section className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Example dates</h2>
            <label className="row small muted" style={{ gap: 8 }}>Ex-factory
              <input type="date" className="input input-sm" style={{ width: "auto" }} value={exFactory} onChange={(e) => setExFactory(e.target.value)} />
            </label>
          </div>
          {preview.length === 0
            ? <p className="faint small">{previewNote ?? "Fill in the timings to see the dates this template would produce."}</p>
            : (
              <table className="table">
                <thead><tr><th>Step</th><th>Start</th><th>Due</th></tr></thead>
                <tbody>
                  {preview.map((p) => (
                    <tr key={p.code}>
                      <td>{p.nameEn}</td>
                      <td className="muted">{p.plannedStart ? fmtDate(p.plannedStart) : "—"}</td>
                      <td>{fmtDate(p.plannedDate, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          {previewNote && preview.length > 0 && <p className="faint small">{previewNote}</p>}
        </section>

        {error && <div className="banner banner-error">{error}</div>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" type="button" onClick={() => nav("/m/templates")}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !name.trim()} onClick={save}>Save template</button>
        </div>
      </div>
    </main>
  );
}
