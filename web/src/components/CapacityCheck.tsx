import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { UnitFit, Verdict } from "../lib/fabric";
import { fmtDate, num } from "../lib/format";

const LABEL: Record<Verdict, { text: string; tone: "green" | "amber" | "red" | "" }> = {
  fits: { text: "Room to spare", tone: "green" },
  tight: { text: "Tight", tone: "amber" },
  over: { text: "Over capacity", tone: "red" },
  no_window: { text: "No time", tone: "red" },
  unknown: { text: "Capacity not set", tone: "" },
};

export interface PlanCheck {
  lateSteps: { name: string; due: string; workingDaysLate: number }[];
  worstDaysLate: number;
  lastStepDue: string | null;
  earliestCleanExFactory: string | null;
}
type Checked = { stitching: { name: string } | null; stages: { process: string; name: string }[]; units: UnitFit[]; plan?: PlanCheck };

/** Does this verdict need the merchandiser to say they want the order anyway? */
export const blocks = (v: Verdict | undefined) => v === "over" || v === "no_window";

/**
 * Stitching capacity of each of our units for an order of this size, shipping on this date, planned from this template.
 * Shows the maths: what is already booked in those days, what this order adds, what the unit can do.
 */
export default function CapacityCheck({
  qty, exFactory, templateKey, unitId, onPickUnit, onSelected, onUseDate, onPlan,
}: {
  qty: number;
  exFactory: string;
  templateKey: string;
  unitId: string;
  onPickUnit?: (id: string) => void;
  onSelected?: (unit: UnitFit | null) => void;
  onUseDate?: (date: string) => void;
  onPlan?: (plan: PlanCheck | null) => void;
}) {
  const [data, setData] = useState<Checked | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (!(qty > 0) || !exFactory || !templateKey) return setData(null);
    let live = true;
    const t = setTimeout(() => {
      api<Checked>("/api/m/capacity/check", { body: { qty, exFactory, templateKey } })
        .then((r) => live && setData(r))
        .catch((e) => live && (setData(null), setError((e as Error).message)));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [qty, exFactory, templateKey]);

  const chosen = data?.units.find((u) => String(u.unitId) === unitId) ?? null;
  useEffect(() => {
    onSelected?.(chosen);
  }, [chosen?.unitId, chosen?.verdict]); // eslint-disable-line react-hooks/exhaustive-deps

  const plan = data?.plan ?? null;
  useEffect(() => {
    onPlan?.(plan);
  }, [plan?.lateSteps.length, plan?.worstDaysLate]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!data) return null;
  const late = plan && plan.lateSteps.length > 0 ? (
    <div className="banner banner-warn stack" role="alert" style={{ gap: 6 }}>
      <b>The plan would already be behind when the order is made</b>
      <span>
        On {fmtDate(exFactory, true)} this plan has {plan.lateSteps.length} step{plan.lateSteps.length === 1 ? "" : "s"} due before today, up to {plan.worstDaysLate} working days ago.
        The order would show a behind-plan warning straight away.
      </span>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {plan.lateSteps.map((l) => <li key={l.name}>{l.name}: was due {fmtDate(l.due, true)} ({l.workingDaysLate} working days ago)</li>)}
      </ul>
      {plan.earliestCleanExFactory && (
        <span className="row" style={{ gap: 8 }}>
          With no step already late, the earliest ex-factory is <b>{fmtDate(plan.earliestCleanExFactory, true)}</b>.
          {onUseDate && <button type="button" className="btn btn-sm" onClick={() => onUseDate(plan.earliestCleanExFactory!)}>Propose this date</button>}
        </span>
      )}
    </div>
  ) : null;
  if (data.stages.length === 0) return <>{late}<p className="faint small" style={{ margin: 0 }}>This plan has no production stage of ours, so capacity is not checked.</p></>;

  return (
    <section className="stack" style={{ gap: 10 }} aria-label="Capacity check">
      {late}
      <div>
        <b style={{ fontWeight: 500 }}>Capacity check</b> <span className="faint small">on {data.stages.map((x) => x.name.toLowerCase()).join(", ")}, for {num(qty)} pcs shipping {fmtDate(exFactory, true)}</span>
      </div>
      <div className="stack" style={{ gap: 6 }}>
        {data.units.map((u) => {
          const l = LABEL[u.verdict];
          const selected = String(u.unitId) === unitId;
          return (
            <button
              type="button"
              key={u.unitId}
              className="card card-pad"
              disabled={!onPickUnit}
              onClick={() => onPickUnit?.(String(u.unitId))}
              aria-pressed={selected}
              style={{ textAlign: "left", cursor: onPickUnit ? "pointer" : "default", borderColor: selected ? "var(--ink)" : undefined }}
            >
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b style={{ fontWeight: 500 }}>{u.name}</b>
                <span className={`pill ${l.tone ? `pill-${l.tone}` : ""}`}>
                  {l.text}{u.utilisation !== null ? ` · ${Math.round(u.utilisation * 100)}%` : ""}
                </span>
              </div>
              {u.utilisation !== null && (
                <div className={`progress ${l.tone}`} style={{ marginTop: 8 }} aria-hidden="true">
                  <i style={{ width: `${Math.min(100, Math.round(u.utilisation * 100))}%` }} />
                </div>
              )}
            </button>
          );
        })}
      </div>

      {chosen && (
        <div className="stack small" style={{ gap: 6 }}>
          <div className="muted">{chosen.summary}</div>
          {chosen.windowStart && chosen.windowEnd && (
            <div className="faint">
              {chosen.limitingStage}: needs about {num(chosen.requiredPerDay)} a day; {chosen.name} can {chosen.verb} {num(chosen.capacity)} a day.
            </div>
          )}
          {chosen.stages.length > 1 && (
            <ul className="reasons" style={{ margin: 0 }} aria-label="Every stage checked">
              {chosen.stages.map((st) => {
                const t = LABEL[st.verdict];
                return (
                  <li key={st.process}>
                    {st.stage}: <span className={t.tone ? `t-${t.tone}` : "faint"}>{st.verdict === "unknown" ? "capacity not set, not checked" : `${t.text} · ${Math.round((st.utilisation ?? 0) * 100)}%`}</span>
                    {st.capacity ? <span className="faint"> ({num(st.capacity)} a day)</span> : null}
                  </li>
                );
              })}
            </ul>
          )}
          {chosen.overlapping.length > 0 && (
            <div className="faint">
              Also stitching in those days: {chosen.overlapping.map((o) => `${o.poNo} (${num(o.qtyLeft)} left)`).join(", ")}
            </div>
          )}
          {blocks(chosen.verdict) && (
            chosen.earliest ? (
              <div className="row" style={{ gap: 8 }}>
                <span>
                  The first ship date this unit could take it: <b>{fmtDate(chosen.earliest.exFactory, true)}</b> ({Math.round(chosen.earliest.utilisation * 100)}% booked).
                </span>
                {onUseDate && <button type="button" className="btn btn-sm" onClick={() => onUseDate(chosen.earliest!.exFactory)}>Propose this date</button>}
              </div>
            ) : (
              <div className="t-red">
                No ship date in the next four months fits. The plan allows {chosen.workingDays} working days for {chosen.limitingStage.toLowerCase()}, in which {chosen.name} can make at most {num(chosen.possible)} pieces. Split the order, use a plan with a longer stitching step, or choose a unit with more capacity.
              </div>
            )
          )}
        </div>
      )}
    </section>
  );
}
