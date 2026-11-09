import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState, PageHeader, Progress, Skeleton, StatusPill, Toast, useApi } from "../../components/ui";
import { api, download } from "../../lib/api";
import { fmtDate, num, plural } from "../../lib/format";
import type { BoardOrder } from "../../lib/types";
import { BuyerRow, LoginRow, OutboxRow, SentLog } from "./Buyers";

/** A temporary password, shown once. It is not kept anywhere the office can look it up again. */
interface Issued { who: string; login: string; password: string }
const TABS = [
  { id: "orders", label: "Orders" },
  { id: "people", label: "People and access" },
  { id: "notify", label: "Notifications" },
  { id: "link", label: "Link and exports" },
  { id: "sent", label: "Sent messages" },
];

export default function BuyerProfile() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? params.get("tab")! : "orders";
  const { data: buyers, reload } = useApi<BuyerRow[]>("/api/m/buyers");
  const { data: board } = useApi<{ orders: BoardOrder[] }>(`/api/m/board?buyer=${id}`);
  const { data: outbox, reload: reloadOutbox } = useApi<OutboxRow[]>("/api/m/outbox");
  const [toast, setToast] = useState<string | null>(null);
  const b = buyers?.find((x) => String(x.id) === id);

  if (!buyers) return <main className="page"><Skeleton rows={4} /></main>;
  if (!b) return <main className="page"><EmptyState title="We could not find that buyer" action={<Link className="btn" to="/m/buyers">Back to buyers</Link>} /></main>;

  return (
    <main className="page">
      <PageHeader
        crumbs={[{ label: "Buyers", to: "/m/buyers" }, { label: b.name }]}
        title={b.name}
        sub={`${b.country ?? "No country set"} · ${plural(b.active_orders, "active order")} · ${b.logins.length ? plural(b.logins.length, "sign-in") : "link only"}`}
        actions={<a className="btn btn-sm" href={`/b/${b.link_token}`} target="_blank" rel="noreferrer" title="Opens the page this buyer sees, in a new tab">What the buyer sees ↗</a>}
      />
      <div className="tabs no-print" role="tablist" aria-label="About this buyer" style={{ margin: "20px 0 18px" }}>
        {TABS.map((t) => <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setParams(t.id === "orders" ? {} : { tab: t.id }, { replace: true })}>{t.label}</button>)}
      </div>

      {tab === "orders" && <Orders orders={board?.orders ?? null} buyerId={b.id} />}
      {tab === "people" && <People b={b} reload={reload} notify={setToast} />}
      {tab === "notify" && <Notify b={b} reload={reload} notify={setToast} />}
      {tab === "link" && <LinkAndExports b={b} reload={reload} notify={setToast} />}
      {tab === "sent" && <SentLog rows={outbox ? outbox.filter((m) => m.buyer === b.name) : null} onChanged={reloadOutbox} />}
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}

/** Who hears from LoomTrack outside the app. WhatsApp needs a number and the buyer's agreement, which is recorded. */
function Notify({ b, reload, notify }: { b: BuyerRow; reload: () => Promise<void>; notify: (m: string) => void }) {
  const [email, setEmail] = useState(!!b.notifyEmail);
  const [number, setNumber] = useState(b.whatsappNumber ?? "");
  const [agreed, setAgreed] = useState(!!b.whatsappOptIn);
  const [problem, setProblem] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const dirty = email !== !!b.notifyEmail || number !== (b.whatsappNumber ?? "") || agreed !== !!b.whatsappOptIn;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setProblem(null);
    setSaving(true);
    try {
      await api(`/api/m/buyers/${b.id}/notifications`, { method: "PATCH", body: { notifyEmail: email, whatsappNumber: number.trim() || null, whatsappOptIn: agreed } });
      await reload();
      notify("Saved");
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="stack" onSubmit={save}>
      <section className="card card-pad stack">
        <div>
          <h2>Email</h2>
          <p className="faint small" style={{ margin: "2px 0 0" }}>
            Sent to each person who signs in for this buyer: replies, requests answered, approvals needed, confirmed delay notices.
            {b.logins.length === 0 && " This buyer has no sign-ins yet, so there is nobody to email."}
          </p>
        </div>
        {b.logins.length > 0 && <p className="muted small" style={{ margin: 0 }}>{b.logins.map((l) => l.login).join(", ")}</p>}
        <label className="check-row"><input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} /> Send email to this buyer's people</label>
      </section>
      <section className="card card-pad stack">
        <div>
          <h2>WhatsApp</h2>
          <p className="faint small" style={{ margin: "2px 0 0" }}>Short messages that say something needs attention, with a button that opens LoomTrack. Only with the buyer's agreement; they can reply STOP at any time.</p>
        </div>
        <label className="field" style={{ maxWidth: 320 }}>
          <span>WhatsApp number, with country code</span>
          <input className="input" inputMode="tel" autoComplete="off" placeholder="+91 98765 43210" value={number} onChange={(e) => setNumber(e.target.value)} />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <span>This buyer agreed to receive WhatsApp messages from us about their orders</span>
        </label>
        {b.whatsappOptIn ? <p className="faint small" style={{ margin: 0 }}>Agreement recorded {b.whatsappOptInAt ? fmtDate(b.whatsappOptInAt.slice(0, 10), true) : ""}. Keep proof of it outside LoomTrack as well (their email or a signed form).</p> : null}
        {!b.whatsappOptIn && b.whatsappNumber === null && <p className="faint small" style={{ margin: 0 }}>Off. Nothing is sent to WhatsApp for this buyer.</p>}
      </section>
      {problem && <p className="error-text" role="alert">{problem}</p>}
      <div><button className="btn btn-primary" disabled={!dirty || saving}>{saving ? "Saving…" : "Save"}</button></div>
    </form>
  );
}

function Orders({ orders, buyerId }: { orders: BoardOrder[] | null; buyerId: number }) {
  const nav = useNavigate();
  if (!orders) return <Skeleton rows={3} />;
  if (orders.length === 0) return <EmptyState title="No live orders" hint="Orders appear here once a request from this buyer is accepted." action={<Link className="btn btn-sm" to={`/m/orders/new?buyer=${buyerId}`}>New order</Link>} />;
  return (
    <div className="card table-scroll">
      <table className="table rows-link">
        <thead><tr><th style={{ paddingLeft: 20 }}>Order</th><th>Ex-factory</th><th>Now</th><th>Status</th></tr></thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} onClick={() => nav(`/m/orders/${o.id}`)}>
              <td style={{ paddingLeft: 20 }}><Link to={`/m/orders/${o.id}`} className="po" onClick={(e) => e.stopPropagation()}>{o.poNo}</Link><div className="muted small">{o.style}</div></td>
              <td className="nowrap num">{fmtDate(o.exFactory, true)}</td>
              <td style={{ minWidth: 160 }}>{o.keyStage ? <><div className="row small" style={{ justifyContent: "space-between" }}><span>{o.keyStage.name}</span><span className="num muted">{o.keyStage.pct}%</span></div><Progress pct={o.keyStage.pct} /></> : <span className="faint">All stages done</span>}</td>
              <td><StatusPill status={o.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function People({ b, reload, notify }: { b: BuyerRow; reload: () => Promise<void>; notify: (m: string) => void }) {
  const [issued, setIssued] = useState<Issued | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", canWrite: true });
  const [formError, setFormError] = useState<string | null>(null);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      const r = await api<{ login: string; password: string }>(`/api/m/buyers/${b.id}/logins`, { body: form });
      setIssued({ who: form.name.trim(), ...r });
      setAdding(false);
      setForm({ name: "", email: "", canWrite: true });
      void reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  };
  const reset = async (l: LoginRow) => {
    if (!confirm(`Make a new temporary password for ${l.name}? They are signed out everywhere and must choose a new password.`)) return;
    const r = await api<{ password: string }>(`/api/m/buyer-logins/${l.id}/reset`, { method: "POST" });
    setIssued({ who: l.name, login: l.login, password: r.password });
    void reload();
  };
  const remove = async (l: LoginRow) => {
    if (!confirm(`Remove the sign-in for ${l.name}? They are signed out now and can no longer sign in.`)) return;
    await api(`/api/m/buyer-logins/${l.id}`, { method: "DELETE" });
    notify("Sign-in removed");
    void reload();
  };
  const setAccess = async (l: LoginRow, canWrite: boolean) => {
    await api(`/api/m/buyer-logins/${l.id}`, { method: "PATCH", body: { canWrite } });
    notify(canWrite ? `${l.name} can now send, approve and change` : `${l.name} can now only look`);
    void reload();
  };
  const edit = async (l: LoginRow) => {
    const name = prompt("Name", l.name);
    if (name === null) return;
    const email = prompt(`Email they sign in with.${l.login ? " Changing it signs them out; they use the new email next time." : ""}`, l.login);
    if (email === null) return;
    try {
      await api(`/api/m/buyer-logins/${l.id}`, { method: "PATCH", body: { name, email } });
      notify("Saved");
      void reload();
    } catch (err) {
      notify((err as Error).message);
    }
  };
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      notify("Copied");
    } catch {
      notify("Select the text and copy it");
    }
  };

  return (
    <div className="stack">
      {issued && (
        <section className="card card-pad stack" role="status" style={{ borderColor: "var(--amber-line)", background: "var(--amber-bg)" }}>
          <b style={{ fontWeight: 500 }}>Sign-in for {issued.who}. Send this to them now: it is not shown again.</b>
          <div className="mono" style={{ lineHeight: 1.8 }}>Email: {issued.login}<br />Temporary password: <b>{issued.password}</b></div>
          <div className="small muted">They choose their own password the first time they sign in, at {window.location.origin}/login.</div>
          <div className="row">
            <button className="btn btn-sm" onClick={() => copy(`${window.location.origin}/login\nEmail: ${issued.login}\nTemporary password: ${issued.password}`)}>Copy details</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setIssued(null)}>Done</button>
          </div>
        </section>
      )}
      <section className="card">
        <div className="card-head">
          <div><h2>People who can sign in</h2><div className="faint small">Full access can send requests, approve and change. View only can read everything and do nothing else.</div></div>
          <button className="btn btn-sm" onClick={() => { setAdding(!adding); setFormError(null); }}>Add a person</button>
        </div>
        {b.logins.length === 0 && !adding && <div className="card-body"><p className="faint" style={{ margin: 0 }}>No one has an account yet. They can still use the private link.</p></div>}
        {b.logins.map((l) => (
          <div key={l.id} className="person-row">
            <div style={{ minWidth: 0 }}>
              <div>{l.name}{l.pending ? <span className="pill pill-amber" style={{ marginLeft: 10 }}>Has not signed in yet</span> : null}</div>
              <div className="faint small">{l.login}</div>
            </div>
            <label className="field person-access">
              <span className="sr-only">Access for {l.name}</span>
              <select className="select select-sm" value={l.canWrite ? "full" : "view"} onChange={(e) => void setAccess(l, e.target.value === "full")}>
                <option value="full">Full access</option>
                <option value="view">View only</option>
              </select>
            </label>
            <div className="row">
              <button className="btn btn-ghost btn-sm" onClick={() => edit(l)}>Edit</button>
              <button className="btn btn-ghost btn-sm" onClick={() => reset(l)}>New password</button>
              <button className="btn btn-ghost btn-sm" onClick={() => remove(l)}>Remove</button>
            </div>
          </div>
        ))}
        {adding && (
          <form className="card-body stack" onSubmit={add} style={{ borderTop: "1px solid var(--line)" }}>
            <div className="grid-3">
              <label className="field"><span>Name</span><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus /></label>
              <label className="field"><span>Email (their sign-in)</span><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label>
              <label className="field"><span>Access</span>
                <select className="select" value={form.canWrite ? "full" : "view"} onChange={(e) => setForm({ ...form, canWrite: e.target.value === "full" })}>
                  <option value="full">Full access</option>
                  <option value="view">View only</option>
                </select>
              </label>
            </div>
            {formError && <div className="banner banner-error">{formError}</div>}
            <div className="row"><button className="btn btn-primary">Create sign-in</button><button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>Cancel</button></div>
          </form>
        )}
      </section>
    </div>
  );
}

function LinkAndExports({ b, reload, notify }: { b: BuyerRow; reload: () => Promise<void>; notify: (m: string) => void }) {
  const link = `${window.location.origin}/b/${b.link_token}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      notify("Link copied");
    } catch {
      notify(link);
    }
  };
  const rotate = async () => {
    if (!confirm(`Make a new link for ${b.name}? The old link stops working immediately.`)) return;
    await api(`/api/m/buyers/${b.id}/rotate-link`, { method: "POST" });
    notify("New link created. Send it to the buyer.");
    void reload();
  };
  const exportXlsx = (audience: "buyer" | "internal") =>
    download(`/api/m/exports/weekly?buyerId=${b.id}&audience=${audience}`, `${b.name.replace(/\W+/g, "-")}-weekly-${audience}.xlsx`).catch((e) => notify(e.message));

  return (
    <div className="stack">
      <section className="card card-pad stack">
        <div><h2>Private link</h2><p className="faint small" style={{ margin: "2px 0 0" }}>Anyone with this link sees this buyer's orders, without signing in. Make a new one if it was shared by mistake.</p></div>
        <div className="row">
          <input className="input input-sm mono" readOnly value={link} style={{ flex: 1, minWidth: 220 }} onFocus={(e) => e.target.select()} aria-label="Buyer link" />
          <button className="btn btn-sm" onClick={copy}>Copy</button>
          <button className="btn btn-ghost btn-sm" onClick={rotate}>New link</button>
        </div>
      </section>
      <section className="card card-pad stack">
        <div><h2>Weekly status (Excel)</h2><p className="faint small" style={{ margin: "2px 0 0" }}>The buyer edition leaves out anything internal. The internal edition is for you.</p></div>
        <div className="row">
          <button className="btn btn-sm" onClick={() => exportXlsx("buyer")}>Buyer edition</button>
          <button className="btn btn-ghost btn-sm" onClick={() => exportXlsx("internal")}>Internal edition</button>
        </div>
      </section>
    </div>
  );
}
