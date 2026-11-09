import { Container, Head } from "./primitives";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function Problem() {
  return (
    <section className="h-sec">
      <Container>
        <Head
          eyebrow="The problem"
          title="The floor knows on Monday. The buyer finds out on Saturday."
          lede="Most delays are known on the line days before anyone else hears. Those are the days you could have used to save the ship date."
        />
        <div className="h-scroll" tabIndex={0} role="group" aria-label="An example week, with and without LoomTrack">
          <div className="h-week">
            <div className="h-day first"><span className="h-mono">An example week</span></div>
            {DAYS.map((d) => <div key={d} className="h-day"><span className="h-mono">{d}</span></div>)}

            <div className="h-lane">Notebook and phone calls</div>
            <div className="h-span h-span-6"><div className="h-long"><span>Floor knows</span><span>Buyer asks, office finds out</span></div></div>

            <div className="h-lane">LoomTrack</div>
            <div className="h-span"><div className="h-solid">Floor, office and buyer all know</div></div>
            <div className="h-span h-span-5"><p className="h-gain">Five days left to reroute the line, not to apologise.</p></div>
          </div>
        </div>
      </Container>
    </section>
  );
}
