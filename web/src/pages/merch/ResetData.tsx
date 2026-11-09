import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Skeleton, Toast, useApi } from "../../components/ui";
import { api } from "../../lib/api";
import { num, plural } from "../../lib/format";
import { useReloadMeta } from "./OfficeShell";

interface Preview {
  removes: { orders: number; supervisorUpdates: number; changeRequests: number; sentMessages: number };
  keeps: { requests: number; reopened: number; buyers: number; templates: number };
}

/** For testing only: back to an empty shop floor, with the buyers' requests still there to be accepted again. */
export default function ResetData() {
  const { data, error, reload } = useApi<Preview>("/api/m/reset");
  const reloadMeta = useReloadMeta();
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function reset(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ backup: string }>("/api/m/reset", { body: { confirm: typed } });
      setTyped("");
      setToast("Test data cleared. A copy of the old data was saved first.");
      void reload();
      reloadMeta();
      console.info("Backup:", r.backup);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <main className="page"><PageHeader title="Reset test data" /><div className="banner banner-error">{error}</div></main>;
  if (!data) return <main className="page"><PageHeader title="Reset test data" /><Skeleton rows={4} /></main>;
  const { removes: r, keeps: k } = data;

  return (
    <main className="page page-narrow">
      <PageHeader title="Reset test data" sub="Start testing again from nothing. This is for a test copy of LoomTrack, never for the one your buyers use." />
      <div className="stack" style={{ marginTop: 20 }}>
        <section className="card card-pad stack">
          <h2>What will be removed</h2>
          <ul className="stack" style={{ gap: 4, margin: 0, paddingLeft: 18 }}>
            <li>{plural(r.orders, "order")}, with their plans, supervisor updates ({num(r.supervisorUpdates)}), photos, delay notices, approvals, materials and files</li>
            <li>{plural(r.changeRequests, "change request")} on orders</li>
            <li>The record of {plural(r.sentMessages, "sent message")} and what the notifications pages show</li>
          </ul>
        </section>
        <section className="card card-pad stack">
          <h2>What stays</h2>
          <ul className="stack" style={{ gap: 4, margin: 0, paddingLeft: 18 }}>
            <li>{plural(k.requests, "request")} from buyers{k.reopened > 0 ? `. ${plural(k.reopened, "request")} that became an order go back to waiting for an answer, so you can accept again.` : "."} <Link to="/m/requests">See requests</Link></li>
            <li>{plural(k.buyers, "buyer")}, their sign-ins, your team, units and {plural(k.templates, "plan template")}</li>
          </ul>
        </section>
        <form className="card card-pad stack" onSubmit={reset}>
          <h2>Reset</h2>
          <p className="muted small" style={{ margin: 0 }}>A copy of the database is saved to the backend's data/backups folder first. Type <b>RESET</b> to go ahead.</p>
          <input className="input" aria-label="Type RESET to confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" placeholder="RESET" style={{ maxWidth: 220 }} />
          {err && <p className="error-text" role="alert">{err}</p>}
          <div><button className="btn btn-primary" disabled={busy || typed.trim() !== "RESET"}>Clear test data</button></div>
        </form>
      </div>
      <Toast message={toast} onDone={() => setToast(null)} />
    </main>
  );
}
