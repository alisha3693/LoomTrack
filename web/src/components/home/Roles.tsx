import { KeyboardEvent, ReactNode, useRef, useState } from "react";
import { Progress } from "../ui";
import { Container, Head, ORDERS } from "./primitives";

function SupervisorScreen() {
  return (
    <div className="h-win narrow">
      <div className="h-between"><span className="h-scr-title">Murugan</span><span className="h-chip h-ta">தமிழ்</span></div>
      <p className="h-small h-ta">என் ஆர்டர்கள்</p>
      <div className="h-box"><b>B-PO-88213</b><p className="h-small h-ta">தையல் · 57%</p><div className="h-bar-gap"><Progress pct={57} tone="green" /></div></div>
      <div className="h-box"><b>C-PO-0488</b><p className="h-small h-ta">பிரிண்டிங் · 31%</p><div className="h-bar-gap"><Progress pct={31} tone="amber" /></div></div>
      <div className="h-between h-box"><span className="h-small">3 reports on this phone</span><span className="h-mono">Waiting for signal</span></div>
      <span className="h-fake k wide h-ta">இன்றைய பதிவு</span>
    </div>
  );
}

const PLAN = [
  ["Cutting", "Fri 23 Oct", "Fri 23 Oct", false],
  ["Stitching", "Sat 7 Nov", "Mon 9 Nov", true],
  ["Packing", "Mon 9 Nov", "Wed 11 Nov", true],
  ["Ex-factory", "Thu 12 Nov", "Sat 14 Nov", true],
] as const;

function MerchandiserScreen() {
  return (
    <div className="h-win">
      <div className="h-between"><span className="h-scr-title">B-PO-88240 · Plan and delay</span><span className="h-dot h-red">Late</span></div>
      <div>
        <div className="h-plan head"><span className="h-mono">Stage</span><span className="h-mono">Planned</span><span className="h-mono">Expected</span></div>
        {PLAN.map(([stage, planned, expected, late]) => (
          <div key={stage} className="h-plan"><span>{stage}</span><span>{planned}</span><span className={late ? "h-red" : ""}>{expected}</span></div>
        ))}
      </div>
      <div className="h-box"><span className="h-mono">Draft for the buyer</span><p className="h-draft">Order may leave on Sat 14 Nov instead of Thu 12 Nov. Reason: machine breakdown.</p></div>
      <div className="h-acts"><span className="h-fake k">Confirm &amp; send to buyer</span><span className="h-fake">Dismiss</span></div>
    </div>
  );
}

function BuyerScreen() {
  return (
    <div className="h-win">
      <div className="h-between"><span className="h-scr-title">Your orders</span><span className="h-mono">Company B (UK)</span></div>
      {ORDERS.map((o) => (
        <div key={o.po} className="h-box">
          <div className="h-between"><b>{o.po}</b><span className="h-small">{o.due}</span></div>
          <p className="h-small">{o.style}</p>
          <div className="h-between h-small h-bar-label h-bar-top"><span>{o.stage}</span><span>{o.pct}%</span></div>
          <Progress pct={o.pct} tone={o.tone} />
        </div>
      ))}
    </div>
  );
}

const ROLES: { id: string; name: string; line: string; title: string; points: string[]; screen: ReactNode }[] = [
  {
    id: "supervisors", name: "Supervisors", line: "On the line, in Tamil",
    title: "Report the day in seconds, in Tamil.",
    points: ["Pieces made and a photo, from the phone", "Speak a note instead of typing it", "Works with no signal and sends when it returns"],
    screen: <SupervisorScreen />,
  },
  {
    id: "merchandisers", name: "Merchandisers", line: "In the office, in control",
    title: "Turn a request into a plan, and keep every promise visible.",
    points: ["Plan from templates you control", "Every date change is kept, with its reason", "Nothing reaches the buyer until you confirm it"],
    screen: <MerchandiserScreen />,
  },
  {
    id: "buyers", name: "Buyers", line: "Anywhere, without chasing",
    title: "Follow every order without chasing anyone.",
    points: ["Send a request with colours and quantities", "See progress on each order, any time", "Hear about a delay as soon as the office confirms it"],
    screen: <BuyerScreen />,
  },
];

export default function Roles() {
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const role = ROLES[active];

  function onKey(e: KeyboardEvent) {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (active + step + ROLES.length) % ROLES.length;
    setActive(next);
    tabs.current[next]?.focus();
  }

  return (
    <section id="roles" className="h-roles">
      <Container>
        <Head
          eyebrow="Who it is for"
          title="One order. Three doors."
          lede="Each person sees only what they need, in the language and on the device they already use."
        />
        <div className="h-tabs" role="tablist" aria-label="Who it is for" onKeyDown={onKey}>
          {ROLES.map((r, i) => (
            <button
              key={r.id}
              ref={(el) => { tabs.current[i] = el; }}
              type="button"
              role="tab"
              id={`tab-${r.id}`}
              aria-selected={i === active}
              aria-controls="role-panel"
              tabIndex={i === active ? 0 : -1}
              className={`h-tab ${i === active ? "sel" : ""}`}
              onClick={() => setActive(i)}
            >
              <b>{r.name}</b><span>{r.line}</span>
            </button>
          ))}
        </div>
        <div className="h-pane" role="tabpanel" id="role-panel" aria-labelledby={`tab-${role.id}`}>
          <div className="h-pane-copy">
            <h3>{role.title}</h3>
            <ul>{role.points.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
          <div className="h-pane-screen" aria-hidden="true">{role.screen}</div>
        </div>
      </Container>
    </section>
  );
}
