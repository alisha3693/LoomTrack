import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { Empty, Modal, Toast, useApi } from "../../components/ui";
import { PlanBars, leadTime, type BarStep } from "../../components/PlanBars";
import type { TemplateList } from "../../lib/types";
import { clearDraft, listDrafts } from "../../lib/tplDraft";
import { useReloadMeta } from "./OfficeShell";

const barSteps = (steps: TemplateList["templates"][number]["steps"]): BarStep[] =>
  steps.map((s) => ({ key: s.code, name: s.nameEn, kind: s.kind, start: s.startOffset, end: s.endOffset }));

export default function Templates() {
  const nav = useNavigate();
  const [retired, setRetired] = useState(false);
  const { data, error, reload } = useApi<TemplateList>(`/api/m/templates?retired=${retired}`);
  const reloadMeta = useReloadMeta();
  const [toast, setToast] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<TemplateList["templates"][number] | null>(null);
  const [drafts, setDrafts] = useState(listDrafts);

  async function setActive(id: number, active: boolean) {
    try {
      await api(`/api/m/templates/${id}/${active ? "restore" : "retire"}`, { method: "POST" });
      setToast(active ? "Template restored" : "Template retired. Existing orders are not affected.");
      void reload();
      reloadMeta();
    } catch (e) {
      setToast((e as Error).message);
    }
  }

  async function remove(id: number) {
    try {
      await api(`/api/m/templates/${id}`, { method: "DELETE" });
      setToast("Template deleted");
      setDeleting(null);
      void reload();
      reloadMeta();
    } catch (e) {
      setToast((e as Error).message);
      setDeleting(null);
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Plan templates</h1>
          <p className="sub">A template is the list of steps and timings a new order starts from. Editing one never changes orders already created.</p>
        </div>
        <div className="row">
          <label className="row small muted" style={{ gap: 6 }}>
            <input type="checkbox" checked={retired} onChange={(e) => setRetired(e.target.checked)} /> Show retired
          </label>
          <button className="btn btn-primary" onClick={() => nav("/m/templates/new")}>New template</button>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}
      {drafts.length > 0 && (
        <section className="card card-pad stack">
          <h2>Drafts</h2>
          <p className="faint small">Unsaved work from the template editor, kept in this browser.</p>
          {drafts.map((d) => (
            <div key={d.scope} className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <b style={{ fontWeight: 500 }}>{d.name.trim() || "Untitled template"}</b>{" "}
                <span className="faint small">{d.scope.startsWith("edit") ? "changes to a saved template" : "new template"} · saved {new Date(d.savedAt).toLocaleString()}</span>
              </div>
              <div className="row">
                <Link className="btn btn-sm btn-primary" to={d.path}>Continue</Link>
                <button className="btn btn-ghost btn-sm" onClick={() => { clearDraft(d.scope); setDrafts(listDrafts()); }}>Discard</button>
              </div>
            </div>
          ))}
        </section>
      )}
      {data && data.templates.length === 0 && <Empty>No templates yet.</Empty>}
      <div className="stack">
        {data?.templates.map((t) => (
          <section key={t.id} className="card card-pad stack" style={{ opacity: t.active ? 1 : 0.6 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="row" style={{ gap: 10 }}>
                <h2>{t.name}</h2>
                {t.builtin && <span className="tag">Built in</span>}
                {!t.active && <span className="pill pill-amber">Retired</span>}
              </div>
              <div className="row">
                <span className="faint small">{t.usedBy === 0 ? "Not used yet" : `${t.usedBy} order${t.usedBy === 1 ? "" : "s"}`}</span>
                <Link className="btn btn-sm" to={`/m/templates/new?copy=${t.id}`}>Copy</Link>
                {t.active && <Link className="btn btn-sm" to={`/m/templates/${t.id}`}>Edit</Link>}
                {!t.builtin && (t.active
                  ? <button className="btn btn-ghost btn-sm" onClick={() => setActive(t.id, false)}>Retire</button>
                  : <button className="btn btn-sm" onClick={() => setActive(t.id, true)}>Restore</button>)}
                {!t.builtin && <button className="btn btn-ghost btn-sm" onClick={() => setDeleting(t)}>Delete</button>}
              </div>
            </div>
            <div className="faint small">
              Lead time {leadTime(barSteps(t.steps))} days before ex-factory · {t.steps.filter((s) => s.kind === "milestone").length} milestones · {t.steps.filter((s) => s.kind === "stage").length} production stages
            </div>
            <PlanBars steps={barSteps(t.steps)} compact />
          </section>
        ))}
      </div>
      {deleting && (
        <Modal title={`Delete “${deleting.name}”?`} onClose={() => setDeleting(null)}>
          <div className="stack">
            <p className="muted" style={{ margin: 0 }}>
              {deleting.usedBy > 0
                ? `${deleting.usedBy} order${deleting.usedBy === 1 ? " was" : "s were"} made from this template, so it cannot be deleted. Retire it instead and it will no longer be offered.`
                : "This removes the template for good. Orders are not affected."}
            </p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setDeleting(null)}>Keep it</button>
              {deleting.usedBy === 0 && <button className="btn btn-primary" onClick={() => remove(deleting.id)}>Delete template</button>}
            </div>
          </div>
        </Modal>
      )}
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
