"""Print the run-rate maths for every order:  python -m loomtrack.explain"""

from . import config
from .db import open_db
from .services.orders import compute_projection


def main() -> None:
    db = open_db(config.DB_FILE)
    today = config.today()
    for o in db.execute("SELECT * FROM orders WHERE state = 'active' ORDER BY ex_factory").fetchall():
        p = compute_projection(db, o, today).p
        print(f"\n{o['po_no']}  {p.status.upper():<5} ex-factory {o['ex_factory']} → projected {p.projected_ex_factory} (slack {p.slack_days})")
        for s in p.stages:
            req = "-" if s.required_per_day is None else f"{s.required_per_day:.0f}"
            flag = " (upstream)" if s.constrained_by_upstream else ""
            print(
                f"  {s.code:<6} {s.done:>6}/{o['qty_total']:<6} plan {s.planned_start}→{s.planned_end}  "
                f"need {req:>5}/d  rate {s.run_rate:>5.0f}/d {s.rate_basis}{flag}  finish {s.projected_finish} slip {s.slip_days:+d}"
            )
        for r in p.reasons:
            print(f"   · {r}")


if __name__ == "__main__":
    main()
