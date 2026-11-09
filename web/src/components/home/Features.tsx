import { Container, Head, Waveform } from "./primitives";

export default function Features() {
  return (
    <section id="features" className="h-sec">
      <Container>
        <Head
          eyebrow="Features"
          title="Built for how a Tiruppur factory really runs."
          lede="Tamil on the floor, English in the office, patchy signal in between, and a buyer in another time zone."
        />
        <div className="h-bento">
          <article className="h-c h-dk s7">
            <p className="h-mono">Voice notes</p>
            <h3>Spoken in Tamil. Read in English.</h3>
            <p className="h-c-text">The supervisor talks. The office reads a translation with the original beside it, on your own server, with no paid AI service.</p>
            <div className="h-c-demo h-translate">
              <div>
                <Waveform />
                <span lang="ta" className="h-ta h-ta-lg">இன்று தையல் முடிந்தது 1,150, இயந்திரம் பழுது.</span>
              </div>
              <span className="h-arrow" aria-hidden="true">→</span>
              <div>
                <span className="h-mono">Machine translation</span>
                <span className="h-ta-lg">Stitching done: 1,150 pieces. A machine broke down.</span>
              </div>
            </div>
          </article>

          <article className="h-c s5">
            <p className="h-mono">Offline</p>
            <h3>A dead zone doesn't lose a report.</h3>
            <ul className="h-c-demo h-queue">
              <li><span>B-PO-88213 · Stitching</span><span>Waiting</span></li>
              <li><span>C-PO-0488 · Printing</span><span>Waiting</span></li>
              <li><span>B-PO-88240 · Stitching</span><span>Sent 10:42</span></li>
            </ul>
          </article>

          <article className="h-c s4">
            <p className="h-mono">Delay drafts</p>
            <h3>The floor's reason writes the draft.</h3>
            <p className="h-c-text">You review it and send it. Nothing goes out on its own.</p>
            <div className="h-c-demo h-chips"><span className="h-chip">Fabric delay</span><span className="h-chip done">Machine breakdown</span></div>
          </article>

          <article className="h-c s4">
            <p className="h-mono">Weekly status</p>
            <h3>Every buyer's week, in one sheet.</h3>
            <div className="h-c-demo h-xl" aria-hidden="true">
              <span className="h">Order</span><span className="h">Stage</span><span className="h">Ex-factory</span>
              <span>B-PO-88240</span><span>Stitching</span><span>14 Nov</span>
              <span>B-PO-88213</span><span>Stitching</span><span>20 Nov</span>
              <span>C-PO-0488</span><span>Printing</span><span>28 Nov</span>
            </div>
          </article>

          <article className="h-c s4">
            <p className="h-mono">Change history</p>
            <h3>A promise is never quietly rewritten.</h3>
            <div className="h-c-demo">
              <div className="h-change"><s>Thu 12 Nov</s><span>Sat 14 Nov</span></div>
              <p className="h-small">Machine breakdown · changed by Priya S.</p>
            </div>
          </article>
        </div>
      </Container>
    </section>
  );
}
