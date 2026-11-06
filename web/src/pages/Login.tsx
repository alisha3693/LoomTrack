import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useLang } from "../lib/i18n";
import { ThemeToggle } from "../lib/theme";

export default function Login() {
  const { user, signIn } = useAuth();
  const { lang, setLang, t } = useLang("en");
  const nav = useNavigate();
  const [login, setLogin] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await signIn(login.trim(), secret);
      if (u.role === "supervisor") setLang(u.lang === "en" ? "en" : "ta");
      nav(u.must_change_secret ? "/account/password" : u.role === "supervisor" ? "/s" : u.role === "buyer" ? "/b/me" : "/m", { replace: true });
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
          <div className="brand">
            <img src="/icon.svg" alt="" />
            LoomTrack
          </div>
          <div className="row" style={{ gap: 8 }}>
          <ThemeToggle />
          <div className="lang-toggle" role="group" aria-label="Language">
            <button type="button" aria-pressed={lang === "ta"} onClick={() => setLang("ta")}>தமிழ்</button>
            <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
          </div>
          </div>
        </div>
        <form className="card card-pad stack" onSubmit={submit}>
          <h1>{t("signIn")}</h1>
          <label className="field">
            <span>{t("loginLabel")}</span>
            <input className="input" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" inputMode="email" autoFocus required />
          </label>
          <label className="field">
            <span>{t("secretLabel")}</span>
            <input className="input" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoComplete="current-password" required />
          </label>
          {error && <p className="error-text">{error}</p>}
          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {t("signIn")}
          </button>
        </form>
        <details className="small">
          <summary>Demo logins</summary>
          <div className="faint" style={{ marginTop: 6, lineHeight: 1.8 }}>
            Merchandiser: priya@companya.in / loom1234
            <br />
            Buyer: hannah@companyb.example / buyer1234
            <br />
            Supervisor Unit 1: 9840000001 / 1111 · Unit 2: 9840000002 / 2222
            <br />
            Unit 3: 9840000003 / 3333 · Print unit: 9840000004 / 4444 · Wash unit: 9840000005 / 5555
          </div>
        </details>
      </div>
    </main>
  );
}
