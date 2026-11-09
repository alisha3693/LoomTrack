import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Skeleton, Toast } from "./ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

interface Profile { role: "buyer" | "merchandiser"; name: string; email: string; phone: string | null; company: string | null }

/** A signed-in person's own name, sign-in email and phone number, changed together on one page. */
export default function MyDetailsForm() {
  const { refresh } = useAuth();
  const [saved, setSaved] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = (p: Profile) => { setSaved(p); setName(p.name); setEmail(p.email); setPhone(p.phone ?? ""); setPassword(""); };
  useEffect(() => { void api<Profile>("/api/auth/profile").then(load).catch((e) => setError((e as Error).message)); }, []);

  if (!saved) return error ? <p className="error-text" role="alert">{error}</p> : <Skeleton rows={4} />;

  const emailChanged = email.trim().toLowerCase() !== saved.email.toLowerCase();
  const dirty = emailChanged || name.trim() !== saved.name || phone.trim() !== (saved.phone ?? "");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const p = await api<Profile>("/api/auth/profile", { method: "PATCH", body: { name, email, phone: phone.trim() || null, currentPassword: emailChanged ? password : null } });
      load(p);
      await refresh();
      setToast("Your details are saved");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div>
        <h1>My details</h1>
        <p className="muted" style={{ margin: "4px 0 0" }}>{saved.company ? `How ${saved.company} is reached. ` : ""}Change what you need and save once.</p>
      </div>
      <form className="card card-pad stack" onSubmit={submit} style={{ maxWidth: 520 }}>
        <label className="field"><span>Your name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
        </label>
        <label className="field"><span>Email (you sign in with this)</span>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label className="field"><span>{saved.role === "buyer" ? "WhatsApp number, with country code" : "Phone number, with country code"}</span>
          <input className="input" inputMode="tel" autoComplete="tel" placeholder={saved.role === "buyer" ? "+44 7700 900123" : "+91 98765 43210"} value={phone} onChange={(e) => setPhone(e.target.value)} />
          <small className="faint">{saved.role === "buyer" ? "Short alerts that an order needs your attention. Leave it empty to receive none. Reply STOP any time to stop them." : "Shown to your team as the way to reach you."}</small>
        </label>
        {emailChanged && (
          <label className="field"><span>Your current password (needed to change the email)</span>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            <small className="faint">After saving, sign in with the new email next time.</small>
          </label>
        )}
        {error && <p className="error-text" role="alert">{error}</p>}
        <div className="row">
          <button className="btn btn-primary" disabled={!dirty || busy}>{busy ? "Saving…" : "Save"}</button>
          <button type="button" className="btn btn-ghost" disabled={!dirty || busy} onClick={() => { load(saved); setError(null); }}>Undo changes</button>
          <Link className="btn btn-ghost" to="/account/password" style={{ marginLeft: "auto" }}>Change password</Link>
        </div>
      </form>
      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}
