import { Container } from "./primitives";

const FACTS = [
  { n: "3", title: "People, one record", text: "Buyer, merchandiser and supervisor read the same order." },
  { n: "2", title: "Languages, no retyping", text: "Tamil from the line, English in the office, automatically." },
  { n: "0", title: "Bars of signal needed", text: "Reports wait on the phone and send when the signal returns." },
];

export default function Facts() {
  return (
    <section>
      <Container>
        <div className="h-facts">
          {FACTS.map((f) => (
            <div key={f.n} className="h-fact">
              <b aria-hidden="true">{f.n}</b>
              <h3><span className="sr-only">{f.n} </span>{f.title}</h3>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
