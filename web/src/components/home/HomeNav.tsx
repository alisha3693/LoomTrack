import { Link } from "react-router-dom";
import { ThemeToggle } from "../../lib/theme";
import { Container } from "./primitives";

const LINKS = [
  { href: "#roles", label: "Who it is for" },
  { href: "#stages", label: "Stages" },
  { href: "#features", label: "Features" },
];

export default function HomeNav() {
  return (
    <header className="h-nav">
      <Container className="h-nav-row">
        <a className="h-logo" href="#top"><span className="h-mark" aria-hidden="true" />LoomTrack</a>
        <nav className="h-links" aria-label="Sections">
          {LINKS.map((l) => <a key={l.href} href={l.href}>{l.label}</a>)}
        </nav>
        <div className="h-actions">
          <ThemeToggle />
          <Link className="btn btn-primary" to="/login">Sign in</Link>
        </div>
      </Container>
    </header>
  );
}
