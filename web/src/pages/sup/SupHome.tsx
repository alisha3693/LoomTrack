import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { addDaysIso } from "../../lib/format";
import { Link } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useLang } from "../../lib/i18n";
import { fmtDate, fmtDateTime, num } from "../../lib/format";
import { outbox } from "../../lib/outbox";
import { Progress, Swatch } from "../../components/ui";
import { InstallBanner } from "../Install";
import { SupHeader } from "./SupHeader";
import { useSupData } from "./useSupData";

/** Shown once on each phone, the first time a supervisor signs in. */
function Welcome({ userId }: { userId: number }) {
  const { t } = useLang("ta");
  const key = `lt.welcome.${userId}`;
  const [shown, setShown] = useState(() => {
    try {
      return localStorage.getItem(key) !== "1";
    } catch {
      return false;
    }
  });
  if (!shown) return null;
  const done = () => {
    try {
      localStorage.setItem(key, "1");
    } catch {
      /* ignore */
    }
    setShown(false);
  };
  return (
    <section className="card card-pad stack welcome" aria-label={t("welcomeTitle")}>
      <h2>{t("welcomeTitle")}</h2>
      <ol className="install-steps">
        <li>{t("welcome1")}</li>
        <li>{t("welcome2")}</li>
        <li>{t("welcome3")}</li>
      </ol>
      <button className="btn btn-primary btn-block" onClick={done}>{t("gotIt")}</button>
    </section>
  );
}

/** Only on a test machine: step the whole app to another date, to see the next day's tasks. */
function TestDate({ onChanged }: { onChanged: () => void }) {
  const [clock, setClock] = useState<{ allowed: boolean; today: string; testDate: string | null; realToday: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => api<NonNullable<typeof clock>>("/api/s/clock").then(setClock).catch(() => setClock(null));
  useEffect(() => { void load(); }, []);
  if (!clock?.allowed) return null;
  async function set(date: string | null) {
    setError(null);
    try {
      await api("/api/s/clock", { method: "PUT", body: { date } });
      await load();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section className="card card-pad stack" style={{ gap: 8 }} aria-label="Test date">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <b style={{ fontWeight: 500 }}>Test date</b>
        <span className="faint small">{clock.testDate ? "set by hand" : "real date"}</span>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        <button className="btn btn-sm" onClick={() => void set(addDaysIso(clock.today, -1))} aria-label="Previous day">←</button>
        <input type="date" className="input input-sm" value={clock.today} aria-label="App date" onChange={(e) => e.target.value && void set(e.target.value)} />
        <button className="btn btn-sm" onClick={() => void set(addDaysIso(clock.today, 1))} aria-label="Next day">→</button>
        {clock.testDate && <button className="btn btn-sm btn-ghost" onClick={() => void set(null)}>Real date ({fmtDate(clock.realToday)})</button>}
      </div>
      <span className="faint small">Everyone using this test copy sees the same date. It is a test tool and is not on the live site.</span>
      {error && <div className="banner banner-error">{error}</div>}
    </section>
  );
}

export default function SupHome() {
  const { user, signOut } = useAuth();
  const { lang, setLang, t } = useLang("ta");
  const { data, queue, online, queuedQty, refresh, refreshQueue, flush } = useSupData();
  const waiting = queue.filter((q) => !q.error);
  const failed = queue.filter((q) => q.error);
  const today = data?.today;

  return (
    <div className="phone">
      <SupHeader title={user?.name ?? ""} sub={user?.unit_name ?? ""} lang={lang} setLang={setLang} />
      <main className="phone-body">
        {user && <Welcome userId={user.id} />}
        <InstallBanner />
        <TestDate onChanged={() => void refresh()} />
        {!online && <div className="banner banner-warn">{t("offline")}</div>}
        {waiting.length > 0 && (
          <button className="queue-chip" style={{ border: 0, alignSelf: "flex-start", cursor: "pointer" }} onClick={() => void flush()}>
            ⟳ {waiting.length} {t("waiting")}
          </button>
        )}
        {failed.map((f) => (
          <div key={f.id} className="banner banner-error">
            <b>{f.label}</b> · {num(f.qty)} — {t("failed")}: {f.error}
            <div style={{ marginTop: 6 }}>
              <button className="btn btn-sm" onClick={() => outbox.remove(f.id).then(refreshQueue)}>{t("discard")}</button>
            </div>
          </div>
        ))}

        <h2 style={{ marginTop: 4 }}>{t("myOrders")}{today ? ` · ${fmtDate(today, true)}` : ""}</h2>

        {data && data.stages.length === 0 && <div className="card card-pad muted">{t("nothingToday")}</div>}
        {data?.stages.map((s) => {
          const done = s.done + queuedQty(s.milestone_id);
          const todayQty = s.today_qty + (today ? queuedQty(s.milestone_id, today) : 0);
          const pct = Math.min(100, Math.round((done / s.qty_total) * 100));
          return (
            <Link key={s.milestone_id} to={`/s/update/${s.milestone_id}`} className="card stage-card">
              <div className="top">
                <div style={{ minWidth: 0 }}>
                  <div className="faint small">{s.order_no} · {s.po_no} · {s.style}, <Swatch hex={s.colour_hex} />{s.colour}</div>
                  <div className="stage-name">{lang === "ta" ? s.name_ta : s.name_en}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="faint small">{t("todayEntered")}</div>
                  <b className={todayQty ? "t-green" : "faint"} title={todayQty ? undefined : t("notYet")}>{todayQty ? num(todayQty) : "—"}</b>
                </div>
              </div>
              <div style={{ marginTop: 12 }}><Progress pct={pct} /></div>
              <div className="meta">
                <span className="num">{num(done)} {t("of")} {num(s.qty_total)}</span>
                <span>{t("dueBy")} {fmtDate(s.planned_date)}</span>
              </div>
              <div className="meta">
                {s.target_per_day - todayQty > 0
                  ? <span className="num">{t("leftToday")}: <b>{num(s.target_per_day - todayQty)}</b></span>
                  : <span className="num t-green"><b>✓ {t("targetDone")}</b></span>}
                {s.ready !== null && (
                  <span className="faint">{num(Math.max(0, s.ready - queuedQty(s.milestone_id)))} {t("readyFrom")} {lang === "ta" ? s.upstream_name_ta : s.upstream_name_en}</span>
                )}
              </div>
            </Link>
          );
        })}

        <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
          <span className="faint small">{data ? `${t("lastSync")} ${fmtDateTime(data.at.replace("T", " ").slice(0, 16))}` : ""}</span>
          <button className="btn btn-ghost btn-sm" onClick={signOut}>{t("signOut")}</button>
        </div>
      </main>
    </div>
  );
}
