import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { refreshBadges } from "../lib/badges";
import { ago, fmtDate, fmtDateTime } from "../lib/format";
import { useApi, useCanWrite } from "./ui";

interface Message {
  key: string;
  source: "order" | "request";
  id: number | null;
  event?: string;
  author: "buyer" | "merchandiser";
  body: string | null;
  proposedExFactory?: string | null;
  requestNo?: string;
  at: string;
}

const EVENT_TEXT: Record<string, string> = {
  submitted: "Request submitted", message: "Wrote on the request", query: "Asked a question", counter: "Proposed another date",
  agreed: "Agreed to the proposed date", accepted: "Request accepted", declined: "Request declined", withdrawn: "Request cancelled",
};

/**
 * The conversation about an order, the same thread on both sides. It opens with what was said while the
 * order was still a request. `me` says which side is looking, so its messages sit on the right. Opening it
 * marks it read, and the other side then sees "Seen". `path` is the messages endpoint.
 */
export default function Conversation({
  path, me, otherName, onSent, hint,
}: {
  path: string;
  me: "buyer" | "merchandiser";
  otherName: string;
  onSent?: () => void;
  hint?: string;
}) {
  const { data, error, reload } = useApi<{ messages: Message[]; readUpTo: number }>(path);
  const canWrite = useCanWrite();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const messages = data?.messages ?? [];
  const said = messages.filter((m) => m.source === "order");
  const last = said[said.length - 1];
  const ownLast = [...said].reverse().find((m) => m.author === me);
  const seen = !!ownLast && !!data && ownLast.id !== null && ownLast.id <= data.readUpTo;
  const newestId = last?.id ?? 0;

  // Opening the conversation marks it read; the sidebar's count follows.
  useEffect(() => {
    if (!data) return;
    end.current?.scrollIntoView({ block: "nearest" });
    api(`${path}/read`, { method: "POST" }).then(refreshBadges).catch(() => {});
  }, [path, newestId, !!data]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send() {
    const message = text.trim();
    if (!message) return;
    setBusy(true);
    setErr(null);
    try {
      await api(path, { body: { message } });
      setText("");
      await reload();
      onSent?.();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const name = otherName.charAt(0).toUpperCase() + otherName.slice(1);
  return (
    <div className="stack" style={{ gap: 12 }}>
      {error && <div className="banner banner-error">{error}</div>}
      {data && messages.length === 0 && (
        <div className="chat-empty">No messages yet. {hint ?? "Anything you write here is seen by the other side."}</div>
      )}
      <div className="chat" aria-live="polite">
        {messages.map((m) => {
          if (m.source === "request") {
            const who = m.author === me ? "You" : name;
            return (
              <div key={m.key} className="chat-event">
                <span>{who}: {EVENT_TEXT[m.event ?? ""] ?? m.event}{m.proposedExFactory ? ` (${fmtDate(m.proposedExFactory, true)})` : ""}{m.body ? ` — “${m.body}”` : ""}</span>
                <time>{fmtDateTime(m.at)}{m.requestNo ? ` · ${m.requestNo}` : ""}</time>
              </div>
            );
          }
          const mine = m.author === me;
          return (
            <div key={m.key} className={`bubble ${mine ? "mine" : ""}`}>
              <div className="who">{mine ? "You" : name} · {fmtDateTime(m.at)}</div>
              <p>{m.body}</p>
            </div>
          );
        })}
        <div ref={end} />
      </div>
      {ownLast && last === ownLast && (
        <div className="faint small" style={{ textAlign: "right" }}>
          {seen ? `Seen by ${otherName}` : `Sent ${ago(ownLast.at)}. ${name} has not opened it yet.`}
        </div>
      )}
      {canWrite ? (
        <>
          <label className="field">
            <span className="sr-only">Your message</span>
            <textarea
              className="textarea" rows={3} maxLength={2000} value={text} placeholder={`Write to ${otherName}…`}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") void send(); }}
            />
          </label>
          {err && <div className="banner banner-error">{err}</div>}
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="faint small">Ctrl + Enter to send</span>
            <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => void send()}>Send message</button>
          </div>
        </>
      ) : (
        <div className="banner">Your account can read this conversation but not write in it.</div>
      )}
    </div>
  );
}
