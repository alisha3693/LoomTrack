import { Link } from "react-router-dom";
import { Container, Stitches } from "./primitives";

// A piece of cloth still on the needles: the top rows are not finished yet.
const CLOTH = [34, 62, 86, 100, 100];

export default function HomeFooter() {
  return (
    <>
      <section className="h-closing h-dk">
        <Container className="h-closing-in">
          <h2>Give every order one honest page.</h2>
          <p>Sign in to see your orders, or ask your merchandiser for a buyer account.</p>
          <Link className="btn btn-lg" to="/login">Sign in</Link>
        </Container>
        {CLOTH.map((pct, i) => <Stitches key={i} count={72} pct={pct} />)}
      </section>
      <footer>
        <Container className="h-foot">
          <span>LoomTrack · Knitwear production tracking · Tiruppur</span>
          <Link to="/login">Team sign in</Link>
        </Container>
      </footer>
    </>
  );
}
