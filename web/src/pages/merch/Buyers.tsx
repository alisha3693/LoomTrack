import { FormEvent, useState } from "react";
import { Toast, useApi } from "../../components/ui";
import { api, download } from "../../lib/api";
import { fmtDateTime } from "../../lib/format";

interface LoginRow { id: number; name: string; login: string; pending: number }
interface BuyerRow { id: number; name: string; country: string | null; link_token: string; link_active: number; active_orders: number; logins: LoginRow[] }

/** A temporary password, shown once. It is not kept anywhere the office can look it up again. */
interface Issued { who: string; login: string; password: string }
interface OutboxRow { id: number; buyer: string; subject: string; body: string; channel: string; created_at: string }

export default function Buyers() {
  const { data: buyers, reload } = useApi<BuyerRow[]>("/api/m/buyers");
  const { data: outbox } = useApi<OutboxRow[]>("/api/m/outbox");
  const [toast, setToast] = useState<string | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const [adding, setAdding] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", email: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const link = (token: string) => `${window.location.origin}/b/${token}`;

  const copy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(link(token));
      setToast("Link copied");
    } catch {
      setToast(link(token));
    }
  };
  const rotate = async (b: BuyerRow) => {
    if (!confirm(`Make a new link for ${b.name}? The old link stops working immediately.`)) return;
    await api(`/api/m/buyers/${b.id}/rotate-link`, { method: "POST" });
    setToast("New link created. Send it to the buyer.");
    void reload();
  };
  const addLogin = async (e: FormEvent, b: BuyerRow) => {
    e.preventDefault();
    setFormError(null);
    try {
      const r = await api<{ login: string; password: string }>(`/api/m/buyers/${b.id}/logins`, { body: { name: form.name, email: form.email } });
      setIssued({ who: form.name.trim(), ...r });
      setAdding(null);
      setForm({ name: "", email: "" });
      void reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  };
  const resetLogin = async (l: LoginRow) => {
    if (!confirm(`Make a new temporary password for ${l.name}? They are signed out everywhere and must choose a new password.`)) return;
    const r = await api<{ password: string }>(`/api/m/buyer-logins/${l.id}/reset`, { method: "POST" });
    setIssued({ who: l.name, login: l.login, password: r.password });
    void reload();
  };
  const removeLogin = async (l: LoginRow) => {
    if (!confirm(`Remove the sign-in for ${l.name}? They are signed out now and can no longer sign in.`)) return;
    await api(`/api/m/buyer-logins/${l.id}`, { method: "DELETE" });
    setToast("Sign-in removed");
    void reload();
  };
  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setToast("Copied");
    } catch {
      setToast("Select the text and copy it");
    }
  };
  const exportXlsx = (b: BuyerRow, audience: "buyer" | "internal") =>
    download(`/api/m/exports/weekly?buyerId=${b.id}&audience=${audience}`, `${b.name.replace(/\W+/g, "-")}-weekly-${audience}.xlsx`).catch((e) => setToast(e.message));

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>Buyers &amp; exports</h1>
          <p className="sub">Each buyer can use a private link, or sign in with their own account. Either way they see only their own orders, and delays appear only after you confirm them.</p>
        </div>
      </div>
      {issued && (
        <section className="card card-pad stack" role="status" style={{ marginBottom: 16, borderColor: "var(--amber-line)", background: "var(--amber-bg)" }}>
          <b style={{ fontWeight: 500 }}>Sign-in for {issued.who}. Send this to them now: it is not shown again.</b>
          <div className="mono" style={{ lineHeight: 1.8 }}>
            Email: {issued.login}<br />Temporary password: <b>{issued.password}</b>
          </div>
          <div className="small muted">They will be asked to choose their own password the first time they sign in, at {window.location.origin}/login.</div>
          <div className="row">
            <button className="btn btn-sm" onClick={() => copyText(`${window.location.origin}/login
Email: ${issued.login}
Temporary password: ${issued.password}`)}>Copy details</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setIssued(null)}>Done</button>
          </div>
        </section>
      )}
      <div className="stack">
        {buyers?.map((b) => (
          <section key={b.id} className="card card-pad stack" style={{ gap: 12 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <h2>{b.name}</h2>
                <div className="faint small">{b.country} · {b.active_orders} active orders</div>
              </div>
              <a className="btn btn-sm" href={`/b/${b.link_token}`} target="_blank" rel="noreferrer">Open buyer view ↗</a>
            </div>
            <div className="row">
              <input className="input input-sm mono" readOnly value={link(b.link_token)} style={{ flex: 1, minWidth: 220 }} onFocus={(e) => e.target.select()} aria-label="Buyer link" />
              <button className="btn btn-sm" onClick={() => copy(b.link_token)}>Copy</button>
              <button className="btn btn-ghost btn-sm" onClick={() => rotate(b)}>New link</button>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b style={{ fontWeight: 500 }}>Sign-in accounts</b>
                <button className="btn btn-sm" onClick={() => { setAdding(adding === b.id ? null : b.id); setFormError(null); }}>Add a person</button>
              </div>
              {b.logins.length === 0 && adding !== b.id && <p className="faint small" style={{ margin: 0 }}>No one has an account yet. They can still use the link above.</p>}
              {b.logins.map((l) => (
                <div key={l.id} className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    {l.name} <span className="faint small">{l.login}</span>
                    {l.pending ? <span className="pill pill-amber" style={{ marginLeft: 8 }}>Has not signed in yet</span> : null}
                  </div>
                  <div className="row">
                    <button className="btn btn-ghost btn-sm" onClick={() => resetLogin(l)}>New password</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => removeLogin(l)}>Remove</button>
                  </div>
                </div>
              ))}
              {adding === b.id && (
                <form className="row" onSubmit={(e) => addLogin(e, b)} style={{ alignItems: "flex-end" }}>
                  <label className="field" style={{ flex: 1, minWidth: 140 }}><span>Name</span>
                    <input className="input input-sm" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus />
                  </label>
                  <label className="field" style={{ flex: 1, minWidth: 200 }}><span>Email (their sign-in)</span>
                    <input className="input input-sm" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
                  </label>
                  <button className="btn btn-primary btn-sm">Create sign-in</button>
                </form>
              )}
              {adding === b.id && formError && <div className="banner banner-error">{formError}</div>}
            </div>
            <div className="row">
              <span className="small muted">Weekly status (Excel):</span>
              <button className="btn btn-sm" onClick={() => exportXlsx(b, "buyer")}>Buyer edition</button>
              <button className="btn btn-ghost btn-sm" onClick={() => exportXlsx(b, "internal")}>Internal edition</button>
            </div>
          </section>
        ))}

        <section className="card">
          <div className="card-head"><h2>Sent to buyers</h2><span className="faint small">Demo: messages are recorded here instead of emailed</span></div>
          <div className="card-body">
            {!outbox?.length ? <p className="faint">Nothing sent yet.</p> : (
              <ul className="reasons">
                {outbox.map((m) => (
                  <li key={m.id}>
                    <b style={{ fontWeight: 500 }}>{m.subject}</b> <span className="faint small">→ {m.buyer} · {fmtDateTime(m.created_at)}</span>
                    <div className="muted small">{m.body}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
