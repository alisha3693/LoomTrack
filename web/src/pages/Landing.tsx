import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ThemeToggle } from "../lib/theme";

const ROLES = [
  {
    id: "buyers",
    title: "Buyers",
    lead: "Place orders and follow them without chasing anyone.",
    points: [
      "Send an order request with your colours, quantities, files and the date you need",
      "See every order's progress, and a warning as soon as a date is at risk",
      "Ask for a date or quantity change and get a clear answer",
    ],
  },
  {
    id: "merchandisers",
    title: "Merchandisers",
    lead: "Turn a request into a plan, and keep every promise visible.",
    points: [
      "Review requests, ask questions, propose another date, accept into an order",
      "Plan from templates you control, with stages and dates you can change",
      "Every date change is recorded with a reason, so nothing is ever lost",
    ],
  },
  {
    id: "supervisors",
    title: "Supervisors",
    lead: "Report the day's work in seconds, in Tamil, even with no signal.",
    points: [
      "Enter pieces made and a photo from the phone",
      "Works offline and sends when the signal returns",
      "Sees only the stages their own unit is working on",
    ],
  },
];

const STEPS = [
  { n: "1", title: "The buyer asks", text: "An order request arrives with the design, colour and the date wanted." },
  { n: "2", title: "The merchandiser plans", text: "They agree the date with the buyer and set the plan, stage by stage." },
  { n: "3", title: "The floor reports", text: "Supervisors record pieces made each day from their phones." },
  { n: "4", title: "Everyone sees the truth", text: "Progress and early warnings update for the buyer and the office." },
];

/** The public home page. It holds no data: it explains the product and sends each person to the right door. */
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
    <div className="home">
      <header className="home-nav">
        <div className="home-inner row" style={{ justifyContent: "space-between" }}>
          <a className="brand" href="#top"><img src="/icon.svg" alt="" />LoomTrack</a>
          <nav className="row home-links" aria-label="Sections">
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
          <div className="home-inner stack" style={{ gap: 20 }}>
            <p className="home-kicker">Production order tracking for knitwear</p>
            <h1>Know where every order stands, before the date slips.</h1>
            <p className="home-sub">
              LoomTrack connects the buyer, the merchandising office and the factory floor. Orders are requested, planned and followed in one place, with an early warning when a delivery date is at risk.
            </p>
            <div className="row" style={{ gap: 12 }}>
              <Link className="btn btn-primary btn-lg" to="/login">Sign in</Link>
              <a className="btn btn-lg" href="#link">I have a buyer link</a>
            </div>
            <p className="faint small" style={{ margin: 0 }}>Buyer accounts are created by your merchandiser. Ask them for yours.</p>
          </div>
        </section>

        <section id="roles" className="home-section">
          <div className="home-inner stack" style={{ gap: 20 }}>
            <h2>Built for the three people every order depends on</h2>
            <div className="home-grid">
              {ROLES.map((r) => (
                <article key={r.id} className="card card-pad stack" style={{ gap: 10 }}>
                  <h3>{r.title}</h3>
                  <p className="muted" style={{ margin: 0 }}>{r.lead}</p>
                  <ul className="home-list">
                    {r.points.map((p) => <li key={p}>{p}</li>)}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="home-section home-alt">
          <div className="home-inner stack" style={{ gap: 20 }}>
            <h2>How an order moves</h2>
            <ol className="home-steps">
              {STEPS.map((s) => (
                <li key={s.n} className="stack" style={{ gap: 6 }}>
                  <span className="home-num" aria-hidden="true">{s.n}</span>
                  <b>{s.title}</b>
                  <span className="muted">{s.text}</span>
                </li>
              ))}
            </ol>
            <p className="muted" style={{ margin: 0, maxWidth: 680 }}>
              Delay warnings come from plain arithmetic on the pieces actually made against the pieces needed each day, not from guesswork. A warning reaches the buyer only after the merchandiser has confirmed it.
            </p>
          </div>
        </section>

        <section id="link" className="home-section">
          <div className="home-inner">
            <div className="card card-pad stack" style={{ maxWidth: 560 }}>
              <h2>Have a private link?</h2>
              <p className="muted" style={{ margin: 0 }}>Paste the link your merchandiser sent you to open your orders without signing in.</p>
              <form className="stack" onSubmit={openLink}>
                <label className="field"><span>Your link</span>
                  <input className="input" value={link} onChange={(e) => { setLink(e.target.value); setError(null); }} placeholder="Paste your link" />
                </label>
                {error && <div className="banner banner-error">{error}</div>}
                <button className="btn btn-primary" disabled={!link.trim()}>Open my orders</button>
              </form>
              <p className="faint small" style={{ margin: 0 }}>Lost your link? Ask your merchandiser for a new one.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="home-foot">
        <div className="home-inner row" style={{ justifyContent: "space-between" }}>
          <span className="faint small">LoomTrack · Tiruppur</span>
          <span className="row small" style={{ gap: 16 }}>
            <Link to="/login">Team sign in</Link>
            <a href="#top">Back to top</a>
          </span>
        </div>
      </footer>
    </div>
  );
}
