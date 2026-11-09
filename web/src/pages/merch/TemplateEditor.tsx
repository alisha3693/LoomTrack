import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { addDaysIso, fmtDate } from "../../lib/format";
import { useApi } from "../../components/ui";
import { PlanBars, type BarStep } from "../../components/PlanBars";
import type { TemplateList, TemplateStep } from "../../lib/types";
import { clearDraft, readDraft, scopeOf, writeDraft } from "../../lib/tplDraft";
import { useMeta, useReloadMeta } from "./OfficeShell";

interface Row {
  id: number;
  code: string | null; // null = a new step typed in here
  nameEn: string;
  nameTa: string;
  kind: "stage" | "milestone";
  process: string;
  otherProcess?: boolean; // the merchandiser chose "Other" and is typing a process that is not in the list
  start: string; // days before ex-factory the stage starts, when it is not set to follow another step
  end: string; // days before ex-factory the step ends
  builtin: boolean;
  savedName: string; // to know whether a custom step was renamed
}

interface PreviewItem { code: string; nameEn: string; kind: string; plannedStart: string | null; plannedDate: string }

let nextId = 1;
const OTHER = "__other__";
/** The form without row ids, to tell whether anything has been changed since it was opened. */
const fingerprint = (name: string, all: Row[]) => JSON.stringify([name, all.map(({ id: _id, ...rest }) => rest)]);
const blank = (kind: "stage" | "milestone"): Row => ({
  id: nextId++, code: null, nameEn: "", nameTa: "", kind, process: "", start: "", end: "",
  builtin: false, savedName: "",
});
const fromStep = (s: TemplateStep | { code: string; nameEn: string; nameTa: string; kind: "stage" | "milestone"; process: string | null; builtin: boolean; endOffset?: number; startOffset?: number | null }): Row => ({
  id: nextId++, code: s.code, nameEn: s.nameEn, nameTa: s.nameTa, kind: s.kind, process: s.process ?? "",
  start: s.startOffset != null ? String(s.startOffset) : "", end: s.endOffset != null ? String(s.endOffset) : "",
  builtin: s.builtin, savedName: s.nameEn,
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

  const found = id ? data?.templates.find((t) => t.id === Number(id)) : undefined;
  // A built-in plan is rewritten from the app at every start, so changes to it are saved as the merchandiser's own copy.
  const editing = found && !found.builtin ? found : undefined;
  const builtinCopy = !!found?.builtin;
  const source = found ?? (copyOf ? data?.templates.find((t) => t.id === Number(copyOf)) : undefined);
  const scope = scopeOf(id, copyOf);
  const opened = useRef("");
  const [restored, setRestored] = useState(false);

  // Fill the form once: from the template being edited, from one being copied, or start with one stage.
  useEffect(() => {
    if (!data || ready) return;
    if (id && !found) return;
    let startName = "";
    let startRows: Row[];
    if (source) {
      startName = editing ? source.name : builtinCopy ? `${source.name} (my version)` : `${source.name} (copy)`;
      startRows = source.steps.filter((s) => s.code !== "EXF").map(fromStep);
    } else {
      startRows = [blank("stage")];
    }
    opened.current = fingerprint(startName, startRows);
    const draft = readDraft<Row>(scope);
    if (draft) {
      startName = draft.name;
      startRows = draft.rows.map((r) => ({ ...r, id: nextId++ }));
      setRestored(true);
    }
    setName(startName);
    setRows(startRows);
    setReady(true);
  }, [data, ready, id, found, editing, builtinCopy, source, scope]);

  // Whatever is on the form is kept as a draft in this browser, so leaving the page does not lose it.
  useEffect(() => {
    if (!ready) return;
    if (fingerprint(name, rows) === opened.current) clearDraft(scope);
    else writeDraft(scope, name, rows);
  }, [ready, name, rows, scope]);

  useEffect(() => {
    if (meta && !exFactory) setExFactory(addDaysIso(meta.today, 90));
  }, [meta, exFactory]);

  const set = (rowId: number, patch: Partial<Row>) => setRows((all) => all.map((r) => (r.id === rowId ? { ...r, ...patch } : r)));
  const used = useMemo(() => new Set(rows.map((r) => r.code).filter(Boolean)), [rows]);
  const library = (data?.library ?? []).filter((s) => !used.has(s.code));
  const move = (rowId: number, by: -1 | 1) =>
    setRows((all) => {
      const i = all.findIndex((r) => r.id === rowId);
      const j = i + by;
      if (i < 0 || j < 0 || j >= all.length) return all;
      const next = [...all];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  const payload = () =>
    rows.map((r) => {
      const start = r.kind === "stage" ? Number(r.start) : null;
      return r.code
        ? { code: r.code, endOffset: Number(r.end), startOffset: start }
        : { nameEn: r.nameEn.trim(), kind: r.kind, process: r.kind === "stage" ? r.process.trim() : null,
            endOffset: Number(r.end), startOffset: start };
    });
  const complete = rows.length > 0 && rows.every((r) => r.end !== "" && (r.kind === "milestone" || r.start !== "") && (r.code || r.nameEn.trim()) && (r.code || r.kind !== "stage" || r.process.trim()));
  // A stage has to start earlier than it ends, which means a bigger number of days before ex-factory.
  const backwards = (r: Row) => r.kind === "stage" && r.start !== "" && r.end !== "" && Number(r.start) <= Number(r.end);
  const anyBackwards = rows.some(backwards);
  const bars: BarStep[] = preview.map((p) => {
    const row = rows.find((r) => r.code === p.code) ?? rows.find((r) => r.nameEn.trim() === p.nameEn);
    return {
      key: p.code, name: p.nameEn, kind: p.kind as BarStep["kind"],
      start: p.kind === "stage" && row ? Number(row.start) : null, end: p.code === "EXF" ? 0 : row ? Number(row.end) : 0,
      due: p.plannedStart ? `${fmtDate(p.plannedStart)} to ${fmtDate(p.plannedDate)}` : fmtDate(p.plannedDate, true),
    };
  });

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
    if (anyBackwards) return setError("A production stage has to start earlier than it ends: its start is the larger number of days.");
    setBusy(true);
    try {
      // Renamed custom steps change for every template and order that uses them.
      for (const r of rows) {
        if (r.code && !r.builtin && r.nameEn.trim() !== r.savedName) {
          await api(`/api/m/steps/${r.code}`, { method: "PATCH", body: { nameEn: r.nameEn.trim() } });
        }
      }
      if (editing) await api(`/api/m/templates/${editing.id}`, { method: "PUT", body: { name: name.trim(), steps: payload() } });
      else await api("/api/m/templates", { body: { name: name.trim(), steps: payload() } });
      clearDraft(scope);
      reloadMeta();
      nav("/m/templates");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (id && data && !found) return <main className="page"><div className="banner banner-error">That template was not found.</div></main>;

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>{editing ? "Edit template" : builtinCopy ? "Edit built-in template" : copyOf ? "Copy template" : "New template"}</h1>
          <p className="sub">
            A plan is a list of steps, each due a number of days before ex-factory. Milestones (approvals, inspections, goods in-house) have one due day.
            Production stages have a start and a due day, and the start is the larger number of days. Ex-factory is added as the last step. Steps stay in the order you put them; use the arrows to move one, and changing a date never reorders them.
          </p>
        </div>
      </div>

      <div className="stack">
        <section className="card card-pad stack">
          <label className="field"><span>Template name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Embroidered polo" maxLength={60} /></label>
          {builtinCopy && <div className="banner">Built-in plans are reset every time the app starts, so your changes are saved as a new template of your own and the original stays as it is.</div>}
          {restored && (
            <div className="banner row" style={{ justifyContent: "space-between" }}>
              <span>Your unsaved changes from last time are back.</span>
              <button className="btn btn-sm" type="button" onClick={() => { clearDraft(scope); setRestored(false); setReady(false); }}>Discard draft</button>
            </div>
          )}
          {editing && editing.usedBy > 0 && (
            <div className="banner">{editing.usedBy} order{editing.usedBy === 1 ? " uses" : "s use"} this template. Saving changes affects only new orders.</div>
          )}
        </section>

        <section className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Steps</h2>
            <span className="faint small">Days are counted back from ex-factory</span>
          </div>
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Step</th><th>Type</th><th>Process</th><th title="Days before ex-factory">Starts</th><th title="Days before ex-factory">Due</th><th title="How many calendar days a production stage runs">Runs</th><th /></tr></thead>
              <tbody>
                {rows.map((r, idx) => {
                  const locked = r.code !== null && r.builtin;
                  return (
                    <tr key={r.id}>
                      <td style={{ minWidth: 200 }}>
                        {locked ? <b style={{ fontWeight: 500 }}>{r.nameEn}</b> : (
                          <div className="stack" style={{ gap: 4 }}>
                            <input className="input input-sm" aria-label="Step name" placeholder="Step name" value={r.nameEn} onChange={(e) => set(r.id, { nameEn: e.target.value })} />
                          </div>
                        )}
                      </td>
                      <td>
                        {r.code ? <span className="muted">{r.kind === "stage" ? "Stage" : "Milestone"}</span> : (
                          <select className="select select-sm" aria-label="Type" value={r.kind} onChange={(e) => set(r.id, { kind: e.target.value as Row["kind"], start: "" })}>
                            <option value="stage">Stage</option><option value="milestone">Milestone</option>
                          </select>
                        )}
                      </td>
                      <td>
                        {r.kind !== "stage" ? <span className="faint">—</span> : r.code ? <span className="muted" style={{ textTransform: "capitalize" }}>{r.process || "—"}</span> : (
                          <div className="stack" style={{ gap: 4 }}>
                            <select className="select select-sm" aria-label="Process" style={{ width: 130 }} value={r.otherProcess ? OTHER : r.process}
                              onChange={(e) => (e.target.value === OTHER ? set(r.id, { otherProcess: true, process: "" }) : set(r.id, { otherProcess: false, process: e.target.value }))}>
                              <option value="" disabled>Choose…</option>
                              {(data?.processes ?? []).map((x) => <option key={x} value={x}>{x[0].toUpperCase() + x.slice(1)}</option>)}
                              <option value={OTHER}>Other…</option>
                            </select>
                            {r.otherProcess && <input className="input input-sm" aria-label="Other process" placeholder="e.g. heat press" style={{ width: 130 }} value={r.process} onChange={(e) => set(r.id, { process: e.target.value })} />}
                          </div>
                        )}
                      </td>
                      <td>{r.kind === "stage"
                        ? <input className="input input-sm num" aria-label="Starts, days before ex-factory" inputMode="numeric" style={{ width: 70 }} value={r.start} aria-invalid={backwards(r) || undefined} onChange={(e) => set(r.id, { start: e.target.value.replace(/\D/g, "") })} />
                        : <span className="faint">—</span>}</td>
                      <td><input className="input input-sm num" aria-label="Ends, days before ex-factory" inputMode="numeric" style={{ width: 70 }} value={r.end} aria-invalid={backwards(r) || undefined} onChange={(e) => set(r.id, { end: e.target.value.replace(/\D/g, "") })} /></td>
                      <td className="num muted">{r.kind !== "stage" ? <span className="faint">—</span> : r.start !== "" && r.end !== "" && !backwards(r) ? <span style={{ whiteSpace: "nowrap" }}>{Number(r.start) - Number(r.end)} days</span> : <span className="faint">—</span>}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="btn btn-ghost btn-sm" type="button" aria-label="Move step up" disabled={idx === 0} onClick={() => move(r.id, -1)}>↑</button>
                        <button className="btn btn-ghost btn-sm" type="button" aria-label="Move step down" disabled={idx === rows.length - 1} onClick={() => move(r.id, 1)}>↓</button>
                        <button className="btn btn-ghost btn-sm" type="button" aria-label="Remove step" onClick={() => setRows((all) => all.filter((x) => x.id !== r.id))}>Remove</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {anyBackwards && <div className="banner banner-error" role="alert">A production stage has to start earlier than it ends. Its start is the larger number of days before ex-factory.</div>}
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
            <h2>Plan and example dates</h2>
            <label className="row small muted" style={{ gap: 8 }}>Ex-factory
              <input type="date" className="input input-sm" style={{ width: "auto" }} value={exFactory} onChange={(e) => setExFactory(e.target.value)} />
            </label>
          </div>
          {preview.length === 0
            ? <p className="faint small">{previewNote ?? "Fill in the timings to see the dates this template would produce."}</p>
            : (
              <>
                <PlanBars steps={bars} />
              </>
            )}
          {previewNote && preview.length > 0 && <p className="faint small">{previewNote}</p>}
        </section>

        {error && <div className="banner banner-error">{error}</div>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" type="button" onClick={() => { clearDraft(scope); nav("/m/templates"); }}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !name.trim() || anyBackwards} onClick={save}>Save template</button>
        </div>
      </div>
    </main>
  );
}
