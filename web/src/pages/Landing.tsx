import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ThemeToggle } from "../lib/theme";

/** The public front page. It holds no data: staff sign in, buyers open the private link they were sent. */
export default function Landing() {
  const nav = useNavigate();
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "LoomTrack · Production order tracking";
  }, []);

  function openLink(e: FormEvent) {
    e.preventDefault();
    // Accept the whole link or just its last part.
    const m = link.trim().match(/\/b\/([A-Za-z0-9_-]{20,})/) ?? link.trim().match(/^([A-Za-z0-9_-]{20,})$/);
    if (!m) return setError("That does not look like a buyer link. Paste the link you were sent.");
    nav(`/b/${m[1]}`);
  }

  return (
    <div className="login-wrap">
      <div className="stack" style={{ width: "100%", maxWidth: 460, gap: 16 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row" style={{ gap: 10 }}>
            <img src="/icon.svg" alt="" width={32} height={32} />
            <h1 style={{ fontSize: 24 }}>LoomTrack</h1>
          </div>
          <ThemeToggle />
        </div>
        <p className="muted" style={{ margin: 0 }}>Production order tracking for our buyers and our team: where every order stands, and early warning when a date is at risk.</p>

        <section className="card card-pad stack">
          <h2>Buyers</h2>
          <p className="muted" style={{ margin: 0 }}>Open the private link your merchandiser sent you to see your orders, send a new order request, or follow one you have sent.</p>
          <form className="stack" onSubmit={openLink}>
            <label className="field"><span>Your link</span>
              <input className="input" value={link} onChange={(e) => { setLink(e.target.value); setError(null); }} placeholder="Paste your link" />
            </label>
            {error && <div className="banner banner-error">{error}</div>}
            <button className="btn btn-primary" disabled={!link.trim()}>Open my orders</button>
          </form>
          <p className="faint small" style={{ margin: 0 }}>Lost your link? Ask your merchandiser for a new one.</p>
        </section>

        <section className="card card-pad stack">
          <h2>Our team</h2>
          <p className="muted" style={{ margin: 0 }}>Merchandisers and supervisors sign in here.</p>
          <Link className="btn" to="/login">Staff sign in</Link>
        </section>
      </div>
    </div>
  );
}
