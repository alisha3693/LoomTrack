import { ReactNode, useRef, useState } from "react";
import { api } from "../lib/api";
import type { FileItem } from "../lib/types";

export const KIND_LABEL = { design: "Design", pattern: "Pattern", print: "Print artwork", fabric: "Fabric", other: "Other" } as const;
export type Kind = keyof typeof KIND_LABEL;
const KINDS = Object.keys(KIND_LABEL) as Kind[];
const ACCEPT = ".pdf,.ai,.png,.jpg,.jpeg,.webp,.gif,.tif,.tiff,.psd,.zip,.xlsx,.docx,.dxf";

export function fmtSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function FileList({ files, hrefFor, actions }: { files: FileItem[]; hrefFor: (f: FileItem) => string; actions?: (f: FileItem) => ReactNode }) {
  if (files.length === 0) return <p className="faint small" style={{ margin: 0 }}>No files yet.</p>;
  return (
    <ul className="reasons">
      {files.map((f) => (
        <li key={f.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <span className="tag">{KIND_LABEL[f.kind]}</span>{" "}
              <a href={hrefFor(f)} target="_blank" rel="noreferrer">{f.filename}</a>{" "}
              <span className="faint small">{fmtSize(f.size)}</span>
            </div>
            <div className="row">{actions?.(f)}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Pick a kind, then a file; the file is sent as soon as it is chosen. */
export function FileUpload({ onUpload, extra }: { onUpload: (kind: Kind, file: File) => Promise<void>; extra?: ReactNode }) {
  const [kind, setKind] = useState<Kind>("design");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function chosen(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(kind, file);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row">
        <select className="select select-sm" style={{ width: "auto" }} aria-label="Kind of file" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          {KINDS.map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        {extra}
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => void chosen(e.target.files?.[0])} />
        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Uploading…" : "Add a file"}</button>
      </div>
      <div className="faint small">PDF, images, Photoshop, ZIP, Excel/Word or DXF. Up to 15 MB each.</div>
      {error && <div className="banner banner-error">{error}</div>}
    </div>
  );
}

/** The merchandiser's file list: who sees what, upload, remove. Works on a request or an order. */
export function OfficeFiles({ files, uploadPath, onChanged }: { files: FileItem[]; uploadPath: string; onChanged: () => void }) {
  const [buyerSees, setBuyerSees] = useState(false);
  const [floorSees, setFloorSees] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = async (f: FileItem, body: object) => {
    setError(null);
    try {
      await api(`/api/m/attachments/${f.id}`, { method: "PATCH", body });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async (f: FileItem) => {
    if (!window.confirm(`Remove ${f.filename}?`)) return;
    try {
      await api(`/api/m/attachments/${f.id}`, { method: "DELETE" });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="stack">
      <FileList
        files={files}
        hrefFor={(f) => f.url ?? "#"}
        actions={(f) => (
          <>
            <label className="row small muted" style={{ gap: 4 }} title="The buyer can open this file">
              <input type="checkbox" checked={!!f.buyerVisible} disabled={f.uploadedBy === "buyer"} onChange={(e) => void patch(f, { buyerVisible: e.target.checked })} /> Buyer
            </label>
            <label className="row small muted" style={{ gap: 4 }} title="Supervisors can open this file">
              <input type="checkbox" checked={!!f.supervisorVisible} onChange={(e) => void patch(f, { supervisorVisible: e.target.checked })} /> Floor
            </label>
            <span className="faint small">{f.uploadedBy === "buyer" ? "from buyer" : "ours"}</span>
            {f.uploadedBy === "merchandiser" && <button className="btn btn-ghost btn-sm" onClick={() => void remove(f)}>Remove</button>}
          </>
        )}
      />
      {error && <div className="banner banner-error">{error}</div>}
      <FileUpload
        onUpload={async (kind, file) => {
          const form = new FormData();
          form.append("kind", kind);
          form.append("buyerVisible", String(buyerSees));
          form.append("supervisorVisible", String(floorSees));
          form.append("file", file);
          await api(uploadPath, { form });
          onChanged();
        }}
        extra={
          <>
            <label className="row small muted" style={{ gap: 4 }}><input type="checkbox" checked={buyerSees} onChange={(e) => setBuyerSees(e.target.checked)} /> Buyer can see</label>
            <label className="row small muted" style={{ gap: 4 }}><input type="checkbox" checked={floorSees} onChange={(e) => setFloorSees(e.target.checked)} /> Floor can see</label>
          </>
        }
      />
    </div>
  );
}
