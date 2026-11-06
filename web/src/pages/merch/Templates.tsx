import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { Empty, Toast, useApi } from "../../components/ui";
import type { TemplateList } from "../../lib/types";
import { useReloadMeta } from "./OfficeShell";

export default function Templates() {
  const nav = useNavigate();
  const [retired, setRetired] = useState(false);
  const { data, error, reload } = useApi<TemplateList>(`/api/m/templates?retired=${retired}`);
  const reloadMeta = useReloadMeta();
  const [toast, setToast] = useState<string | null>(null);

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
      {data && data.templates.length === 0 && <Empty>No templates yet.</Empty>}
      <div className="stack">
        {data?.templates.map((t) => (
          <section key={t.id} className="card card-pad stack" style={{ opacity: t.active ? 1 : 0.6 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="row" style={{ gap: 10 }}>
                <h2>{t.name}</h2>
                {t.builtin && <span className="pill">Built in</span>}
                {!t.active && <span className="pill pill-amber">Retired</span>}
              </div>
              <div className="row">
                <span className="faint small">{t.usedBy === 0 ? "Not used yet" : `${t.usedBy} order${t.usedBy === 1 ? "" : "s"}`}</span>
                <Link className="btn btn-sm" to={`/m/templates/new?copy=${t.id}`}>Copy</Link>
                {!t.builtin && t.active && <Link className="btn btn-sm" to={`/m/templates/${t.id}`}>Edit</Link>}
                {!t.builtin && (t.active
                  ? <button className="btn btn-ghost btn-sm" onClick={() => setActive(t.id, false)}>Retire</button>
                  : <button className="btn btn-sm" onClick={() => setActive(t.id, true)}>Restore</button>)}
              </div>
            </div>
            <div className="muted small">
              {t.steps.filter((s) => s.kind === "stage").map((s) => s.nameEn).join(" → ")}
            </div>
            <div className="faint small">
              {t.steps.length} steps, {t.steps.filter((s) => s.kind === "stage").length} production stages
            </div>
          </section>
        ))}
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
