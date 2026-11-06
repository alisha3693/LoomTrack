import { fmtDate, fmtDateTime, num } from "../lib/format";
import { EVENT_TEXT, RequestDetailData, RequestStatus, statusLabel } from "../lib/requests";
import { Swatch } from "./ui";

export function RequestPill({ status, audience }: { status: RequestStatus; audience: "office" | "buyer" }) {
  const { text, tone } = statusLabel(status, audience);
  return <span className={`pill ${tone ? `pill-${tone}` : ""}`}>{text}</span>;
}

/** The request's content: colour, quantities, the date asked for. */
export function RequestSummary({ r }: { r: RequestDetailData }) {
  if (r.kind === "amendment") return <AmendmentSummary r={r} />;
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

/** A change to an existing order: while it is open, what it says now beside what is asked for. */
function AmendmentSummary({ r }: { r: RequestDetailData }) {
  const c = r.change;
  const now = new Map((c?.current.sizes ?? []).map((s) => [s.size, s.qty]));
  const asked = new Map(r.sizes.map((s) => [s.size, s.qty]));
  const sizes = [...new Set([...now.keys(), ...asked.keys()])];
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="muted">Change to PO {r.poNo} · {r.style}{c ? ` · ${c.orderNo}` : r.orderNo ? ` · ${r.orderNo}` : ""}</div>
      {c ? (
        <table className="table">
          <thead><tr><th /><th>Now</th><th>Asked for</th></tr></thead>
          <tbody>
            <tr>
              <td>Ex-factory</td>
              <td>{fmtDate(c.current.exFactory, true)}</td>
              <td>{c.dateChanged ? <b>{fmtDate(r.exFactory, true)}</b> : <span className="faint">unchanged</span>}</td>
            </tr>
            {sizes.map((s) => (
              <tr key={s}>
                <td>{s}</td>
                <td className="num">{num(now.get(s) ?? 0)}</td>
                <td className="num">{(now.get(s) ?? 0) === (asked.get(s) ?? 0) ? <span className="faint">{num(asked.get(s) ?? 0)}</span> : <b>{num(asked.get(s) ?? 0)}</b>}</td>
              </tr>
            ))}
            <tr><td><b style={{ fontWeight: 500 }}>Total</b></td><td className="num">{num(c.current.totalQty)}</td><td className="num"><b>{num(r.totalQty)}</b></td></tr>
          </tbody>
        </table>
      ) : (
        <div className="small">Ex-factory {fmtDate(r.exFactory, true)} · {r.sizes.map((s) => `${s.size} ${num(s.qty)}`).join(" · ")}</div>
      )}
      {r.description && <p style={{ margin: 0, whiteSpace: "pre-wrap" }}><b style={{ fontWeight: 500 }}>Reason:</b> {r.description}</p>}
    </div>
  );
}
