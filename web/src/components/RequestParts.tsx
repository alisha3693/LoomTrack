import { fmtDate, fmtDateTime, num } from "../lib/format";
import { EVENT_TEXT, RequestDetailData, RequestStatus, statusLabel } from "../lib/requests";
import { Swatch } from "./ui";

export function RequestPill({ status, audience }: { status: RequestStatus; audience: "office" | "buyer" }) {
  const { text, tone } = statusLabel(status, audience);
  return <span className={`pill ${tone ? `pill-${tone}` : ""}`}>{text}</span>;
}

/** The request's content: colour, quantities, the date asked for. */
export function RequestSummary({ r }: { r: RequestDetailData }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="muted">
        {r.style}, <Swatch hex={r.colourHex} />
        {r.colour.toLowerCase()}
        {r.colourPantone ? ` (Pantone ${r.colourPantone})` : ""} · {num(r.totalQty)} pcs
      </div>
      <div className="faint small">{r.sizes.map((s) => `${s.size} ${num(s.qty)}`).join(" · ")}</div>
      <div className="small">
        Ex-factory asked for: <b>{fmtDate(r.exFactory, true)}</b> · PO {r.poNo}
      </div>
      {r.description && <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{r.description}</p>}
    </div>
  );
}

/** The history of the request, oldest first. `audience` decides who "you" is. */
export function RequestThread({ r, audience }: { r: RequestDetailData; audience: "office" | "buyer" }) {
  return (
    <ol className="stack" style={{ listStyle: "none", margin: 0, padding: 0, gap: 12 }}>
      {r.messages.map((m, i) => {
        const you = (audience === "buyer") === (m.author === "buyer");
        return (
          <li key={i} className="card card-pad stack" style={{ gap: 4, background: you ? "var(--sunken)" : undefined }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b style={{ fontWeight: 500 }}>{EVENT_TEXT[m.event](m.author, audience === "buyer" ? you : false)}</b>
              <span className="faint small">{fmtDateTime(m.at)}</span>
            </div>
            {m.proposedExFactory && <div className="small">Proposed ex-factory: <b>{fmtDate(m.proposedExFactory, true)}</b></div>}
            {m.body && <div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div>}
          </li>
        );
      })}
    </ol>
  );
}
