import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Skeleton, Toast, useApi } from "../../components/ui";
import { api } from "../../lib/api";

interface Setup {
  publicUrl: string;
  email: { configured: boolean; from: string | null; host: string | null };
  whatsapp: { configured: boolean; language: string | null; webhookReady: boolean };
  last7days: Record<string, number>;
  events: { key: string; audience: "buyer" | "office"; when: string; whatsapp: string | null }[];
}

const COUNT_LABEL: [string, string][] = [["sent", "Sent"], ["delivered", "Delivered"], ["read", "Read"], ["failed", "Failed"], ["queued", "Waiting"], ["logged", "Recorded only"], ["skipped", "Not sent"]];

/** What is connected, a way to check it, and what the app sends. The keys themselves live in backend/.env, never here. */
export default function Notifications() {
  const { data } = useApi<Setup>("/api/m/notifications");
  const [toast, setToast] = useState<string | null>(null);
  if (!data) return <main className="page"><PageHeader title="Email and WhatsApp" /><Skeleton rows={4} /></main>;
  const counts = COUNT_LABEL.filter(([k]) => data.last7days[k]);

  return (
    <main className="page">
      <PageHeader title="Email and WhatsApp" sub="How LoomTrack reaches people outside the app. Until a channel is connected, messages are only recorded under Buyers, Sent messages." />
      <div className="stack" style={{ marginTop: 20 }}>
        <div className="grid-2">
          <Channel
            title="Email"
            on={data.email.configured}
            detail={data.email.configured ? `Sends from ${data.email.from} through ${data.email.host}.` : "Not connected. Add the SMTP settings to backend/.env and restart the server."}
            channel="email"
            placeholder="you@example.com"
            onDone={setToast}
          />
          <Channel
            title="WhatsApp"
            on={data.whatsapp.configured}
            detail={
              data.whatsapp.configured
                ? `Connected to the Meta Cloud API, templates in language “${data.whatsapp.language}”. ${data.whatsapp.webhookReady ? "Delivery reports and STOP replies are switched on." : "Delivery reports and STOP replies need LOOMTRACK_WA_VERIFY_TOKEN and LOOMTRACK_WA_APP_SECRET."}`
                : "Not connected. Submit the templates to Meta first, then add the WhatsApp settings to backend/.env."
            }
            channel="whatsapp"
            placeholder="+91 98765 43210"
            onDone={setToast}
          />
        </div>

        {counts.length > 0 && (
          <section className="card card-pad">
            <h2>Last 7 days</h2>
            <div className="row" style={{ gap: 28, marginTop: 8 }}>
              {counts.map(([k, label]) => <div key={k}><div className="big-num num">{data.last7days[k]}</div><div className="faint small">{label}</div></div>)}
            </div>
            <p className="faint small" style={{ margin: "10px 0 0" }}><Link to="/m/buyers?tab=sent">See every message</Link></p>
          </section>
        )}

        <section className="card table-scroll">
          <div className="card-pad" style={{ paddingBottom: 6 }}>
            <h2>What is sent</h2>
            <p className="faint small" style={{ margin: "2px 0 0" }}>Each event goes by email. Buyers who agreed to it also get the WhatsApp message named here. The wording is in docs/WHATSAPP_TEMPLATES.md, ready for Meta to review.</p>
          </div>
          <table className="table">
            <thead><tr><th style={{ paddingLeft: 20 }}>When</th><th>Goes to</th><th>WhatsApp template</th></tr></thead>
            <tbody>
              {data.events.map((e) => (
                <tr key={e.key}>
                  <td style={{ paddingLeft: 20 }}>{e.when}</td>
                  <td className="nowrap">{e.audience === "buyer" ? "The buyer's people" : "Merchandisers"}</td>
                  <td className="mono small">{e.whatsapp ?? <span className="faint">email only</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}

function Channel({ title, on, detail, channel, placeholder, onDone }: { title: string; on: boolean; detail: string; channel: "email" | "whatsapp"; placeholder: string; onDone: (m: string) => void }) {
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const test = async (e: FormEvent) => {
    e.preventDefault();
    setProblem(null);
    setBusy(true);
    try {
      const r = await api<{ message: string }>("/api/m/notifications/test", { body: { channel, to } });
      onDone(r.message);
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card card-pad stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{title}</h2>
        <span className={`pill ${on ? "pill-green" : ""}`}>{on ? "Connected" : "Not connected"}</span>
      </div>
      <p className="muted small" style={{ margin: 0 }}>{detail}</p>
      {on && (
        <form className="stack" onSubmit={test} style={{ gap: 8 }}>
          <label className="field">
            <span>Send a test to</span>
            <input className="input" type={channel === "email" ? "email" : "tel"} placeholder={placeholder} value={to} onChange={(e) => setTo(e.target.value)} required />
          </label>
          {problem && <p className="error-text" role="alert" style={{ margin: 0 }}>{problem}</p>}
          <div><button className="btn btn-sm" disabled={busy || !to.trim()}>{busy ? "Sending…" : "Send test"}</button></div>
        </form>
      )}
    </section>
  );
}
