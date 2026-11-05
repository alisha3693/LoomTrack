import { Link } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useLang } from "../../lib/i18n";
import { fmtDate, fmtDateTime, num } from "../../lib/format";
import { outbox } from "../../lib/outbox";
import { Progress } from "../../components/ui";
import { SupHeader } from "./SupHeader";
import { useSupData } from "./useSupData";

export default function SupHome() {
  const { user, signOut } = useAuth();
  const { lang, setLang, t } = useLang("ta");
  const { data, queue, online, queuedQty, refreshQueue, flush } = useSupData();
  const waiting = queue.filter((q) => !q.error);
  const failed = queue.filter((q) => q.error);
  const today = data?.today;

  return (
    <div className="phone">
      <SupHeader title={user?.name ?? ""} sub={user?.unit_name ?? ""} lang={lang} setLang={setLang} />
      <main className="phone-body">
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
                  <div className="faint small">{s.po_no} · {s.style}, {s.colour}</div>
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
