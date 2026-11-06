import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useLang } from "../../lib/i18n";
import { fmtDate, num } from "../../lib/format";
import { compressPhoto, makeRecognizer, pickAudioType } from "../../lib/media";
import { flushOutbox, newId, outbox } from "../../lib/outbox";
import { api } from "../../lib/api";
import { FileList } from "../../components/Attachments";
import { Toast } from "../../components/ui";
import type { FileItem } from "../../lib/types";
import { SupHeader } from "./SupHeader";
import { useSupData } from "./useSupData";

const OVER_QTY_ALLOWANCE = 1.05; // matches the server

export default function SupUpdate() {
  const { milestoneId } = useParams();
  const nav = useNavigate();
  const { lang, setLang, t } = useLang("ta");
  const { data, queuedQty } = useSupData();
  const stage = data?.stages.find((s) => s.milestone_id === Number(milestoneId));

  const [qty, setQty] = useState("");
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [audio, setAudio] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const recRef = useRef<{ stop: () => void } | null>(null);

  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);
  useEffect(() => () => recRef.current?.stop(), []);

  if (!data) return <div className="phone"><div className="phone-body faint">…</div></div>;
  if (!stage) {
    return (
      <div className="phone">
        <div className="phone-body"><Link to="/s" className="btn">← {t("back")}</Link></div>
      </div>
    );
  }

  const done = stage.done + queuedQty(stage.milestone_id);
  const stageName = lang === "ta" ? stage.name_ta : stage.name_en;

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    const small = await compressPhoto(file);
    setPhoto(small);
    setPhotoUrl(URL.createObjectURL(small));
  }

  async function toggleMic() {
    if (recording) {
      recRef.current?.stop();
      return;
    }
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone not available");
      return;
    }
    // Keep the original audio: the merchandiser can always listen to it.
    const type = pickAudioType();
    const recorder = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 24000 } : undefined);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((tr) => tr.stop());
      if (chunks.length) setAudio(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    };

    // Live transcript where the phone supports it (Chrome on Android).
    const rec = makeRecognizer(lang === "ta" ? "ta-IN" : "en-IN");
    const before = note ? `${note.trim()} ` : "";
    if (rec) {
      rec.onresult = (e) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
        setNote(before + text);
      };
      rec.onerror = () => {};
      try { rec.start(); } catch { /* already started or blocked */ }
    }
    recorder.start();
    setRecording(true);
    recRef.current = {
      stop: () => {
        if (recorder.state !== "inactive") recorder.stop();
        try { rec?.stop(); } catch { /* ignore */ }
        setRecording(false);
        recRef.current = null;
      },
    };
  }

  async function send() {
    setError(null);
    if (qty === "") return setError(t("enterQty"));
    const n = Number(qty);
    if (done + n > Math.floor(stage!.qty_total * OVER_QTY_ALLOWANCE)) return setError(`${t("tooMany")} (${num(stage!.qty_total)})`);
    recRef.current?.stop();
    setBusy(true);
    await outbox.put({
      id: newId(),
      milestoneId: stage!.milestone_id,
      workDate: data!.today,
      qty: n,
      noteText: note.trim(),
      noteSource: audio ? "voice" : note.trim() ? "text" : undefined,
      createdAt: new Date().toISOString(),
      photo: photo ?? undefined,
      audio: audio ?? undefined,
      label: `${stage!.po_no} · ${stage!.name_en}`,
    });
    await flushOutbox();
    const left = (await outbox.all()).filter((i) => !i.error);
    setToast(left.length ? t("queued") : t("sent"));
    setTimeout(() => nav("/s"), 900);
  }

  return (
    <div className="phone">
      <SupHeader
        title={stageName}
        sub={`${stage.po_no} · ${stage.style}`}
        lang={lang}
        setLang={setLang}
        left={<Link to="/s" className="btn btn-ghost btn-sm" aria-label={t("back")}>←</Link>}
      />
      <main className="phone-body">
        <FloorFiles orderId={stage.order_id} label={t("files")} />
        <div className="row faint small" style={{ justifyContent: "space-between" }}>
          <span className="num">{num(done)} {t("of")} {num(stage.qty_total)} · {t("dueBy")} {fmtDate(stage.planned_date)}</span>
          <span>{t("workDate")}: {fmtDate(data.today, true)}</span>
        </div>

        <label className="field">
          <span style={{ fontSize: 15 }}>{t("todayQty")}</span>
          <input className="qty-input num" inputMode="numeric" pattern="[0-9]*" value={qty} placeholder="0" autoFocus
            onChange={(e) => setQty(e.target.value.replace(/\D/g, "").slice(0, 6))} />
        </label>

        <div className="field">
          <span style={{ fontSize: 15 }}>{t("photo")}</span>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => onPhoto(e.target.files?.[0])} />
          {photoUrl ? (
            <div className="photo-preview">
              <img src={photoUrl} alt="" />
              <button className="btn btn-sm" onClick={() => fileRef.current?.click()}>{t("retake")}</button>
            </div>
          ) : (
            <button className="photo-btn" onClick={() => fileRef.current?.click()}>📷 {t("takePhoto")}</button>
          )}
        </div>

        <div className="field">
          <span style={{ fontSize: 15 }}>{t("issue")}</span>
          <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
            <textarea className="textarea" lang="ta" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("issuePlaceholder")} style={{ fontSize: 16 }} />
            <button className={`mic ${recording ? "on" : ""}`} onClick={toggleMic} aria-label={recording ? t("stop") : t("record")} title={recording ? t("stop") : t("record")}>
              {recording ? "■" : (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                </svg>
              )}
            </button>
          </div>
          {audio && !recording && (
            <div className="row small muted">
              ✓ {t("voiceSaved")}
              <button className="btn btn-ghost btn-sm" onClick={() => setAudio(null)}>{t("remove")}</button>
            </div>
          )}
        </div>
        {error && <div className="banner banner-error">{error}</div>}
      </main>
      <div className="send-bar">
        <button className="btn btn-primary btn-lg btn-block" disabled={busy} onClick={send}>{t("send")}</button>
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}

/** Files the merchandiser shared with the floor. Quietly absent when offline or when nothing is shared. */
function FloorFiles({ orderId, label }: { orderId: number; label: string }) {
  const [files, setFiles] = useState<FileItem[]>([]);
  useEffect(() => {
    api<{ files: FileItem[] }>(`/api/s/orders/${orderId}/attachments`).then((r) => setFiles(r.files)).catch(() => {});
  }, [orderId]);
  if (files.length === 0) return null;
  return (
    <details className="card card-pad">
      <summary>{label} ({files.length})</summary>
      <div style={{ marginTop: 10 }}><FileList files={files} hrefFor={(f) => f.url ?? "#"} /></div>
    </details>
  );
}
