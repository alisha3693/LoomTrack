import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import { useApi } from "./ui";

interface Message {
  id: number;
  author: "buyer" | "merchandiser";
  body: string;
  at: string;
}

/**
 * The conversation about an order, the same thread on both sides. `me` says which side is looking, so
 * its messages sit on the right. `path` is the messages endpoint: GET to read, POST {message} to write.
 */
export default function Conversation({
  path, me, otherName, onRead, onSent, hint,
}: {
  path: string;
  me: "buyer" | "merchandiser";
  otherName: string;
  /** Called with the time of the newest message once it is on screen. */
  onRead?: (latestAt: string | null) => void;
  onSent?: () => void;
  hint?: string;
}) {
  const { data, error, reload } = useApi<{ messages: Message[] }>(path);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const messages = data?.messages ?? [];
  const last = messages[messages.length - 1];

  useEffect(() => {
    if (data) onRead?.(last?.at ?? null);
    end.current?.scrollIntoView({ block: "nearest" });
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

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

  return (
    <div className="stack" style={{ gap: 12 }}>
      {error && <div className="banner banner-error">{error}</div>}
      {data && messages.length === 0 && (
        <div className="chat-empty">No messages yet. {hint ?? "Anything you write here is seen by the other side."}</div>
      )}
      <div className="chat" aria-live="polite">
        {messages.map((m) => {
          const mine = m.author === me;
          return (
            <div key={m.id} className={`bubble ${mine ? "mine" : ""}`}>
              <div className="who">{mine ? "You" : otherName.charAt(0).toUpperCase() + otherName.slice(1)} · {fmtDateTime(m.at)}</div>
              <p>{m.body}</p>
            </div>
          );
        })}
        <div ref={end} />
      </div>
      {last && last.author === me && <div className="faint small">Sent. {otherName} will see it the next time they open this order.</div>}
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
    </div>
  );
}
