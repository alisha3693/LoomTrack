import { Container, Stitches } from "./primitives";

// The checkpoints and production stages of a real plan, on one sample order of 2,400 pieces.
const BEFORE = ["Fit sample", "Lab dip", "PP sample", "Fabric in-house", "Fabric inspection", "Trims"];
const ROWS = [
  { name: "Cutting", made: 2400 },
  { name: "Printing", made: 2400 },
  { name: "Stitching", made: 1368 },
  { name: "Washing", made: 410 },
  { name: "Finishing", made: 0 },
  { name: "Packing", made: 0 },
];
const NEEDED = 2400;

export default function StageSheet() {
  return (
    <section id="stages" className="h-band">
      <Container className="h-swatch">
        <div className="h-swatch-copy">
          <p className="h-mono">Made for knitwear</p>
          <h2>The plan, knitted row by row.</h2>
          <p className="h-lede">Each row is a production stage. Pieces made fill it in against pieces needed, so a thin row is visible weeks before a missed ship date.</p>
        </div>
        <div className="h-sheet">
          <div className="h-between h-sheet-top"><span className="h-scr-title">B-PO-88213 · Men's crew neck tee</span><span className="h-mono">{NEEDED.toLocaleString("en-IN")} pcs</span></div>
          <div className="h-chips">{BEFORE.map((b) => <span key={b} className="h-chip done">{b}</span>)}</div>
          <table>
            <caption className="sr-only">Pieces made at each production stage of a sample order</caption>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.name}>
                  <th scope="row">{r.name}</th>
                  <td><Stitches count={30} pct={(r.made / NEEDED) * 100} /></td>
                  <td className="h-count">{r.made.toLocaleString("en-IN")} / {NEEDED.toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="h-chips"><span className="h-chip">Final inspection (AQL)</span><span className="h-chip">Ex-factory · Fri 20 Nov</span></div>
        </div>
      </Container>
    </section>
  );
}
