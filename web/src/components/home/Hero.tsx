import { Link } from "react-router-dom";
import { Container } from "./primitives";

export default function Hero() {
  return (
    <section id="top">
      <Container className="h-hero">
        <p className="h-mono h-span-all">Production tracking for Tiruppur knitwear exporters</p>
        <h1>Every order, tracked stitch by stitch.</h1>
        <div>
          <p className="h-lede">The floor reports in Tamil. The office sees a slip the day it happens. The buyer gets a straight answer before they have to ask.</p>
          <div className="h-cta">
            <Link className="btn btn-primary btn-lg" to="/login">Sign in</Link>
            <a className="btn btn-lg" href="#features">See how it works</a>
          </div>
        </div>
      </Container>
    </section>
  );
}
