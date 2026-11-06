import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ThemeToggle } from "../lib/theme";

const MIN = 8;

/** Change your own password. A buyer whose password the office chose is sent here before anything else. */
export default function ChangePassword() {
  const { user, loading, refresh } = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  const forced = !!user.must_change_secret;
  const home = user.role === "supervisor" ? "/s" : user.role === "buyer" ? "/b/me" : "/m";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (next.length < MIN) return setError(`Use at least ${MIN} characters.`);
    if (next !== again) return setError("The two new passwords are different.");
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/password", { body: { current, new: next } });
      await refresh();
      nav(home, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-wrap">
      <div className="login stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="brand"><img src="/icon.svg" alt="" />LoomTrack</div>
          <ThemeToggle />
        </div>
        <form className="card card-pad stack" onSubmit={submit}>
          <h1>{forced ? "Choose your own password" : "Change password"}</h1>
          {forced && <p className="muted" style={{ margin: 0 }}>The password you were given is only for your first sign-in. Choose one only you know.</p>}
          <label className="field"><span>{forced ? "Password you were given" : "Current password"}</span>
            <input className="input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" autoFocus required />
          </label>
          <label className="field"><span>New password (at least {MIN} characters)</span>
            <input className="input" type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" required />
          </label>
          <label className="field"><span>New password again</span>
            <input className="input" type="password" value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" required />
          </label>
          {error && <p className="error-text">{error}</p>}
          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>Save password</button>
          {!forced && <Link className="small" to={home}>Cancel</Link>}
        </form>
      </div>
    </main>
  );
}
