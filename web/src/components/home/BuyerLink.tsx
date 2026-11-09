import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container } from "./primitives";

/** Buyers who were sent a private link open their orders here, without signing in. */
export default function BuyerLink() {
  const nav = useNavigate();
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);

  function open(e: FormEvent) {
    e.preventDefault();
    // Accept the whole link or just its last part.
    const m = link.trim().match(/\/b\/([A-Za-z0-9_-]{20,})/) ?? link.trim().match(/^([A-Za-z0-9_-]{20,})$/);
    if (!m) return setError("That does not look like a buyer link. Paste the link you were sent.");
    nav(`/b/${m[1]}`);
  }

  return (
    <section id="link">
      <Container>
        <div className="h-linkrow">
          <div>
            <h3>Have a private link?</h3>
            <p className="h-c-text">Paste the link your merchandiser sent you to open your orders without signing in. Lost it? Ask for a new one.</p>
          </div>
          <form className="h-link" onSubmit={open}>
            <label className="field"><span>Your link</span>
              <input className="input" value={link} onChange={(e) => { setLink(e.target.value); setError(null); }} placeholder="Paste your link" />
            </label>
            <button className="btn btn-primary" disabled={!link.trim()}>Open my orders</button>
            {error && <div className="banner banner-error h-link-error">{error}</div>}
          </form>
        </div>
      </Container>
    </section>
  );
}
