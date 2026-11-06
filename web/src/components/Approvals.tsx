import { FormEvent, ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { refreshBadges } from "../lib/badges";
import { ago, fmtDateTime } from "../lib/format";
import { APPROVAL_KINDS, Approval, isOpenApproval } from "../lib/flow";
import { EmptyState, useCanWrite } from "./ui";

type Side = "office" | "buyer";

/** Where an approval stands, in the words of whoever is reading. */
export function approvalState(a: Approval, side: Side): { text: string; tone: "" | "green" | "amber" | "red" } {
  if (a.status === "approved") return { text: side === "buyer" ? "You approved" : "Approved by the buyer", tone: "green" };
  if (a.status === "withdrawn") return { text: "Withdrawn", tone: "" };
  if (a.status === "changes") return { text: side === "buyer" ? "Waiting for your merchandiser" : "Buyer asked for changes", tone: side === "buyer" ? "" : "amber" };
  if (side === "buyer") return { text: "Waiting for your decision", tone: "amber" };
  return { text: a.buyerSeenAt ? `Waiting for the buyer · opened ${ago(a.buyerSeenAt)}` : "Waiting for the buyer · not opened yet", tone: "" };
}

function Trail({ a }: { a: Approval }) {
  return (
    <ol className="trail">
      {a.events.map((e, i) => (
        <li key={i}>
          <b>{e.text}</b> <span className="faint small">· {e.actor === "buyer" ? "buyer" : "merchandiser"} · {fmtDateTime(e.at)}</span>
          {e.note && <div className="muted small">“{e.note}”</div>}
        </li>
      ))}
    </ol>
  );
}

/** One approval as a card: what it is, where it stands, its history, and the actions its side can take. */
export function ApprovalCard({ a, side, actions, showOrder }: { a: Approval; side: Side; actions?: ReactNode; showOrder?: { to: string } }) {
  const st = approvalState(a, side);
  return (
    <article className={`approval${isOpenApproval(a) ? " open" : ""}`}>
      <header>
        <div>
          <div className="row" style={{ gap: 8 }}>
            <b>{a.title}</b><span className="tag">{a.kindLabel}</span>
          </div>
          <div className="faint small">
            {showOrder ? <Link to={showOrder.to}>{a.poNo}</Link> : a.poNo} · {a.style}{a.buyer ? ` · ${a.buyer}` : ""} · asked {ago(a.requestedAt)}
          </div>
        </div>
        <span className={`pill ${st.tone ? `pill-${st.tone}` : ""}`}>{st.text}</span>
      </header>
      {a.note && <p className="muted" style={{ margin: 0 }}>{a.note}</p>}
      {a.completesStep && a.status === "requested" && <p className="faint small" style={{ margin: 0 }}>Approving marks “{a.completesStep}” done on the plan.</p>}
      {a.events.length > 1 && <Trail a={a} />}
      {actions}
    </article>
  );
}

/** The buyer's two answers: approve, or say what has to change. */
export function BuyerDecision({ token, a, onDone }: { token: string; a: Approval; onDone: (message: string) => void }) {
  const canWrite = useCanWrite();
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (a.status !== "requested") return null;
  if (!canWrite) return <p className="faint small" style={{ margin: 0 }}>Your account can look at this but not decide it.</p>;

  async function send(path: "approve" | "changes", body: { note?: string }) {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/b/${token}/approvals/${a.id}/${path}`, { body });
      refreshBadges();
      onDone(path === "approve" ? `You approved “${a.title}”` : "Your changes were sent to your merchandiser");
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  return asking ? (
    <form className="stack" style={{ gap: 8 }} onSubmit={(e: FormEvent) => { e.preventDefault(); void send("changes", { note }); }}>
      <label className="field"><span>What needs to change?</span>
        <textarea className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)} minLength={3} required placeholder="For example: the neck rib is too wide, please narrow it by 5 mm." />
      </label>
      {err && <div className="banner banner-error">{err}</div>}
      <div className="row">
        <button className="btn btn-primary" disabled={busy || note.trim().length < 3}>Send changes to the merchandiser</button>
        <button type="button" className="btn btn-ghost" onClick={() => setAsking(false)}>Back</button>
      </div>
    </form>
  ) : (
    <div className="stack" style={{ gap: 8 }}>
      {err && <div className="banner banner-error">{err}</div>}
      <div className="row">
        <button className="btn btn-primary" disabled={busy} onClick={() => void send("approve", {})}>Approve</button>
        <button className="btn" disabled={busy} onClick={() => setAsking(true)}>Ask for changes</button>
      </div>
    </div>
  );
}

/** The office's answer to a buyer who sent it back, or the choice to withdraw. */
export function OfficeDecision({ a, onDone }: { a: Approval; onDone: (message: string) => void }) {
  const [again, setAgain] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!isOpenApproval(a)) return null;

  async function go(path: string, body: unknown, done: string) {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/m/approvals/${a.id}/${path}`, { body: body ?? {} });
      refreshBadges();
      onDone(done);
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  if (again) {
    return (
      <form className="stack" style={{ gap: 8 }} onSubmit={(e: FormEvent) => { e.preventDefault(); void go("resubmit", { note }, "Sent to the buyer again"); }}>
        <label className="field"><span>What did you change?</span>
          <textarea className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)} required placeholder="For example: neck rib narrowed by 5 mm, new sample sent on 8 Nov." />
        </label>
        {err && <div className="banner banner-error">{err}</div>}
        <div className="row">
          <button className="btn btn-primary" disabled={busy || !note.trim()}>Send to the buyer again</button>
          <button type="button" className="btn btn-ghost" onClick={() => setAgain(false)}>Back</button>
        </div>
      </form>
    );
  }
  return (
    <div className="stack" style={{ gap: 8 }}>
      {err && <div className="banner banner-error">{err}</div>}
      <div className="row">
        {a.status === "changes" && <button className="btn btn-primary btn-sm" onClick={() => setAgain(true)}>Answer and send again</button>}
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void go("withdraw", {}, "Approval withdrawn")}>Withdraw</button>
      </div>
    </div>
  );
}

/** The office's form to ask the buyer to approve something on an order. */
export function AskForApproval({ orderId, onAsked }: { orderId: number; onAsked: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("pp_sample");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/m/orders/${orderId}/approvals`, { body: { kind, title, note: note || null } });
      setOpen(false);
      setTitle("");
      setNote("");
      onAsked("Sent to the buyer for approval");
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) return <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>Ask the buyer to approve something</button>;
  return (
    <form className="card card-pad stack" onSubmit={submit}>
      <h2>Ask the buyer to approve</h2>
      <div className="grid-2">
        <label className="field"><span>What for</span>
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
            {APPROVAL_KINDS.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
          </select>
        </label>
        <label className="field"><span>Name it</span>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} required placeholder="PP sample, navy crew neck" />
        </label>
      </div>
      <label className="field"><span>Note for the buyer (optional)</span>
        <textarea className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Sent by courier on 3 Nov. Please check the neck rib and the print placement." />
      </label>
      {(kind === "fit_sample" || kind === "pp_sample") && <p className="faint small" style={{ margin: 0 }}>When the buyer approves, the plan step “{kind === "fit_sample" ? "Fit sample approval" : "PP sample approval"}” is marked done.</p>}
      {err && <div className="banner banner-error">{err}</div>}
      <div className="row">
        <button className="btn btn-primary" disabled={busy || !title.trim()}>Send for approval</button>
        <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}

export function NoApprovals({ side }: { side: Side }) {
  return side === "office"
    ? <EmptyState title="No approvals yet" hint="Ask the buyer to approve a sample, a lab dip or packaging. They answer here, and you see when they have opened it." />
    : <EmptyState title="Nothing to approve" hint="When your merchandiser sends a sample or a lab dip for your approval, it appears here." />;
}
