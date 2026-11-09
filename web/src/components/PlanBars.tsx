/** A time-and-action chart: the plan drawn against the days left to ex-factory, the way buyers and merchandisers read it.
 *  Production stages are bars, milestones are diamonds, and the right edge is ex-factory. */

export interface BarStep {
  key: string;
  name: string;
  kind: "stage" | "milestone";
  start: number | null; // days before ex-factory a stage starts
  end: number; // days before ex-factory it ends
  due?: string; // text shown for the due date, when a real date is known
}

const pct = (n: number, span: number) => `${(100 * (span - n)) / span}%`;

export function leadTime(steps: BarStep[]): number {
  return steps.reduce((m, s) => Math.max(m, s.start ?? s.end), 0);
}

export function PlanBars({ steps, compact = false }: { steps: BarStep[]; compact?: boolean }) {
  const span = Math.max(1, leadTime(steps));
  const ordered = [...steps].sort((a, b) => b.end - a.end || (b.start ?? b.end) - (a.start ?? a.end));
  // A tick every 10 days (every 20 when the plan is long), so the scale reads without a ruler.
  const every = span > 80 ? 20 : 10;
  const ticks: number[] = [];
  for (let d = Math.floor(span / every) * every; d > 0; d -= every) if (d / span > 0.18) ticks.push(d); // the last one would sit under the Ex-factory label

  return (
    <div className={`tna${compact ? " tna-compact" : ""}`} role="table" aria-label="Plan timeline">
      <div className="tna-axis" role="row">
        <span className="tna-name" role="columnheader">Step</span>
        <div className="tna-track" role="columnheader" aria-label="Days before ex-factory">
          {ticks.map((d) => <span key={d} className="tna-tick" style={{ left: pct(d, span) }}>{d}</span>)}
          <span className="tna-tick tna-tick-end" style={{ left: "100%" }}>Ex-factory</span>
        </div>
        {!compact && <span className="tna-due" role="columnheader">Due</span>}
      </div>
      {ordered.map((s) => {
        const label = s.kind === "stage"
          ? `${s.name}: starts ${s.start} days before ex-factory, ends ${s.end} days before`
          : `${s.name}: ${s.end === 0 ? "on the ex-factory day" : `${s.end} days before ex-factory`}`;
        return (
          <div key={s.key} className="tna-row" role="row" title={label}>
            <span className={`tna-name${s.kind === "milestone" ? " tna-ms" : ""}`} role="cell">{s.name}</span>
            <div className="tna-track" role="cell" aria-label={label}>
              {ticks.map((d) => <i key={d} className="tna-grid" style={{ left: pct(d, span) }} aria-hidden="true" />)}
              {s.kind === "stage" && s.start != null
                ? <b className="tna-bar" style={{ left: pct(s.start, span), width: `${(100 * (s.start - s.end)) / span}%` }} />
                : <b className="tna-dot" style={{ left: pct(s.end, span) }} />}
            </div>
            {!compact && <span className="tna-due" role="cell">{s.due ?? ""}</span>}
          </div>
        );
      })}
    </div>
  );
}
