import { Link } from "react-router-dom";
import { BuyerOrder, orderChip, seenKey } from "../lib/buyer";
import { fmtDate, num } from "../lib/format";
import { unseen } from "../lib/seen";
import { Progress, Swatch } from "./ui";

/** One order as a line a buyer can scan: what it is, when it ships, how far along it is, and anything new on it. */
export default function BuyerOrderRow({ token, o }: { token: string; o: BuyerOrder }) {
  const chip = orderChip(o);
  const newReply = o.lastMessage?.author === "merchandiser" && unseen(seenKey(token, o.id), o.lastMessage.at);
  return (
    <Link to={`/b/${token}/orders/${o.id}`} className="order-row">
      <div style={{ minWidth: 0 }}>
        <div className="t">{o.poNo}</div>
        <div className="muted small">{o.style}, <Swatch hex={o.colourHex} />{o.colour.toLowerCase()} · {num(o.qty)} pcs</div>
      </div>
      <div className="nowrap">
        <div className="faint small">{o.state === "shipped" ? "Shipped" : "Ex-factory"}</div>
        <b className="num">{fmtDate(o.exFactory, true)}</b>
        {o.notice && <div className="small t-red num">Expected {fmtDate(o.notice.expectedExFactory)}</div>}
      </div>
      <div>
        <div className="row small" style={{ justifyContent: "space-between", marginBottom: 4 }}><span className="faint">Packed</span><b className="num">{o.overallPct}%</b></div>
        <Progress pct={o.overallPct} tone={o.overallPct >= 100 ? "green" : ""} />
      </div>
      <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
        {newReply && <span className="pill pill-amber" title="Your merchandiser wrote to you">New reply</span>}
        <span className={`pill ${chip.tone ? `pill-${chip.tone}` : ""}`}>{chip.text}</span>
      </div>
    </Link>
  );
}
