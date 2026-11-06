import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Progress } from "../components/ui";
import { ThemeToggle } from "../lib/theme";

const ROLES = [
  {
    id: "buyers",
    title: "Follow every order without chasing anyone.",
    text: "Send a request with colours, quantities and files. See progress, and a clear warning when a date is at risk.",
  },
  {
    id: "merchandisers",
    title: "Turn a request into a plan, and keep every promise visible.",
    text: "Plan from templates you control. Every date change is recorded with its reason, so nothing is ever lost.",
  },
  {
    id: "supervisors",
    title: "Report the day's work in seconds, in Tamil, even offline.",
    text: "Pieces made and a photo from the phone. It sends when the signal returns.",
  },
];
const ROLE_LABEL: Record<string, string> = { buyers: "Buyers", merchandisers: "Merchandisers", supervisors: "Supervisors" };

const STEPS = [
  { title: "The buyer asks", text: "A request arrives with the design, colour and the date wanted." },
  { title: "The office plans", text: "The date is agreed and the plan set, stage by stage." },
  { title: "The floor reports", text: "Supervisors record pieces made each day from their phones." },
  { title: "Everyone sees the truth", text: "Progress and early warnings update for buyer and office." },
];

/** The public home page. It holds no data: it explains the product and sends each person to the right door. */
export default function Landing() {
  const nav = useNavigate();
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "LoomTrack · Production tracking for knitwear";
  }, []);

  function openLink(e: FormEvent) {
    e.preventDefault();
    // Accept the whole link or just its last part.
    const m = link.trim().match(/\/b\/([A-Za-z0-9_-]{20,})/) ?? link.trim().match(/^([A-Za-z0-9_-]{20,})$/);
    if (!m) return setError("That does not look like a buyer link. Paste the link you were sent.");
    nav(`/b/${m[1]}`);
  }

  return (
    <div className="home">
      <header className="home-nav">
        <div className="home-inner">
          <a className="brand" href="#top"><img src="/icon.svg" alt="" width="26" height="26" />LoomTrack</a>
          <nav className="home-links" aria-label="Sections">
            <a href="#roles">Who it is for</a>
            <a href="#how">How it works</a>
            <a href="#link">I have a link</a>
          </nav>
          <div className="row" style={{ gap: 8 }}>
            <ThemeToggle />
            <Link className="btn btn-primary" to="/login">Sign in</Link>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="home-hero">
          <div className="home-inner">
            <div className="stack" style={{ gap: 28 }}>
              <p className="home-kicker">Production tracking for knitwear</p>
              <h1>Know where every order stands, before the date slips.</h1>
              <p className="home-sub">
                One place for the buyer, the merchandising office and the factory floor. Orders are requested, planned and followed, with a warning the moment a delivery date is at risk.
              </p>
              <div className="row" style={{ gap: 12 }}>
                <Link className="btn btn-primary btn-lg" to="/login">Sign in</Link>
                <a className="btn btn-lg" href="#link">I have a buyer link</a>
              </div>
              <p className="faint small" style={{ margin: 0 }}>Buyer accounts are created by your merchandiser.</p>
            </div>

            <figure className="home-example" style={{ margin: 0 }} aria-label="An example order, as the buyer sees it">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", flexWrap: "nowrap" }}>
                <div>
                  <div className="po">B-PO-88240</div>
                  <div className="muted small">Men's polo, white · 8,000 pcs</div>
                </div>
                <span className="pill pill-red">Delay notice</span>
              </div>
              <div className="facts">
                <div><span>Ex-factory</span><b>Thu 12 Nov</b></div>
                <div><span>Expected</span><b className="t-red">Tue 17 Nov</b></div>
                <div><span>Quantity</span><b>8,000 pcs</b></div>
              </div>
              <div className="bars">
                <div><div><span>Cutting</span><span className="muted">100%</span></div><Progress pct={100} tone="green" /></div>
                <div><div><span>Stitching</span><span className="muted">100%</span></div><Progress pct={100} tone="green" /></div>
                <div><div><span>Packing</span><span className="muted">38%</span></div><Progress pct={38} tone="red" /></div>
              </div>
              <figcaption className="tag-line">An example order, as the buyer sees it.</figcaption>
            </figure>
          </div>
        </section>

        <section id="roles" className="home-section">
          <div className="home-inner stack" style={{ gap: 48 }}>
            <h2 style={{ maxWidth: 560 }}>Built for the three people every order depends on.</h2>
            <div className="home-cols">
              {ROLES.map((r) => (
                <article key={r.id}>
                  <div className="home-label">{ROLE_LABEL[r.id]}</div>
                  <h3>{r.title}</h3>
                  <p className="muted" style={{ margin: 0 }}>{r.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="home-section home-alt">
          <div className="home-inner stack" style={{ gap: 48 }}>
            <h2>How an order moves.</h2>
            <ol className="home-steps">
              {STEPS.map((s, i) => (
                <li key={s.title}>
                  <span className="home-num" aria-hidden="true">{i + 1}</span>
                  <b style={{ fontWeight: 500 }}>{s.title}</b>
                  <span>{s.text}</span>
                </li>
              ))}
            </ol>
            <p className="muted" style={{ margin: 0, maxWidth: 640 }}>
              Warnings come from plain arithmetic on the pieces made against the pieces needed each day, not from guesswork. A warning reaches the buyer only after the merchandiser confirms it.
            </p>
          </div>
        </section>

        <section id="link" className="home-section">
          <div className="home-inner home-link">
            <div className="stack" style={{ gap: 12 }}>
              <h2>Have a private link?</h2>
              <p className="muted" style={{ margin: 0, maxWidth: 420 }}>Paste the link your merchandiser sent you to open your orders without signing in. Lost it? Ask for a new one.</p>
            </div>
            <form className="stack" onSubmit={openLink}>
              <label className="field"><span>Your link</span>
                <input className="input" style={{ height: 52, borderRadius: 12 }} value={link} onChange={(e) => { setLink(e.target.value); setError(null); }} placeholder="Paste your link" />
              </label>
              {error && <div className="banner banner-error">{error}</div>}
              <button className="btn btn-primary btn-lg" disabled={!link.trim()}>Open my orders</button>
            </form>
          </div>
        </section>
      </main>

      <footer className="home-foot">
        <div className="home-inner row" style={{ justifyContent: "space-between" }}>
          <span className="faint small">LoomTrack · Tiruppur</span>
          <Link className="faint small" to="/login">Team sign in</Link>
        </div>
      </footer>
    </div>
  );
}
