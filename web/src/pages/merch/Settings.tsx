import { Link } from "react-router-dom";
import { PageHeader } from "../../components/ui";
import { useMeta } from "./OfficeShell";

const PAGES = [
  { to: "/m/templates", title: "Plan templates", text: "The stages and timings every new order follows." },
  { to: "/m/units", title: "Units and capacity", text: "Pieces a day each unit can make, and what is booked." },
  { to: "/m/notifications", title: "Email and WhatsApp", text: "What is connected, what gets sent, and a test message." },
];

/** The setup pages in one place, so the sidebar can stay short. */
export default function Settings() {
  const meta = useMeta();
  const pages = meta?.canReset ? [...PAGES, { to: "/m/reset", title: "Reset test data", text: "Start again from an empty floor. Test machines only." }] : PAGES;
  return (
    <main className="page">
      <div className="stack" style={{ gap: 24 }}>
        <PageHeader title="Settings" sub="How LoomTrack plans, measures and reaches people." />
        <div className="settings-grid">
          {pages.map((p) => (
            <Link key={p.to} to={p.to} className="settings-card">
              <b>{p.title}</b>
              <span>{p.text}</span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
