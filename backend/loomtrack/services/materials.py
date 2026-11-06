"""What an order needs before it can be made: fabric, trims, packing.

Each line says what, who supplies it, where it stands (not ordered, ordered, received) and which
plan step needs it. The date it is needed by is read from that step each time, so it follows the plan
when a date is moved. domain/materials.py decides whether a line is on track, at risk or late.
"""

from __future__ import annotations

import sqlite3

from ..db import transaction
from ..domain.calendar import add_days
from ..domain.materials import material_risk, worst
from ..util import HttpError

KINDS = ("fabric", "trim", "packing")
_KIND_ORDER = {"fabric": 0, "trim": 1, "packing": 2}

# The standard list: (kind, name, unit, the plan step that needs it, then the steps to try if the plan has no such step).
PRESETS = [
    ("fabric", "Main fabric", "kg", "FAB", ("CUT", "STITCH")),
    ("fabric", "Rib / collar fabric", "kg", "FAB", ("CUT", "STITCH")),
    ("trim", "Sewing thread", "cones", "STITCH", ("CUT",)),
    ("trim", "Main label", "pcs", "STITCH", ("CUT",)),
    ("trim", "Care and size label", "pcs", "STITCH", ("CUT",)),
    ("trim", "Hangtag", "pcs", "PACK", ("FINISH", "STITCH")),
    ("packing", "Polybag", "pcs", "PACK", ("FINISH", "STITCH")),
    ("packing", "Carton", "pcs", "PACK", ("FINISH", "STITCH")),
]

_SELECT = """SELECT mt.*, m.planned_start, m.planned_date, s.kind AS step_kind, s.name_en AS step_name
             FROM order_materials mt
             LEFT JOIN milestones m ON m.order_id = mt.order_id AND m.code = mt.needed_for
             LEFT JOIN plan_steps s ON s.code = mt.needed_for"""


def _present(r: sqlite3.Row, today: str) -> dict:
    if r["planned_date"]:
        stage = r["step_kind"] == "stage"
        needed = (r["planned_start"] or r["planned_date"]) if stage else r["planned_date"]
        label = f"{r['step_name']} {'starts' if stage else 'is due'}"
    else:
        needed, label = r["needed_by"], "Needed by"
    risk = material_risk(status=r["status"], expected=r["expected_date"], received=r["received_date"], needed_by=needed, needed_label=label, today=today)
    return {
        "id": r["id"], "orderId": r["order_id"], "kind": r["kind"], "name": r["name"], "supplier": r["supplier"], "suppliedBy": r["supplied_by"],
        "qty": r["qty"], "unit": r["unit"], "status": r["status"], "orderedDate": r["ordered_date"], "expectedDate": r["expected_date"],
        "receivedDate": r["received_date"], "neededFor": r["needed_for"], "neededForName": r["step_name"], "neededBy": needed,
        "neededLabel": label, "note": r["note"], "updatedAt": r["updated_at"], "risk": risk,
    }


def _sorted(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: (_KIND_ORDER[i["kind"]], i["id"]))


def list_for_order(db: sqlite3.Connection, order_id: int, today: str) -> list[dict]:
    return _sorted([_present(r, today) for r in db.execute(f"{_SELECT} WHERE mt.order_id = ?", (order_id,))])


def summarise(items: list[dict]) -> dict:
    open_states = [i["risk"]["state"] for i in items if i["risk"]["state"] != "received"]
    return {
        "total": len(items), "received": len(items) - len(open_states),
        "late": open_states.count("late"), "atRisk": open_states.count("at_risk"),
        "worst": worst(open_states) or ("received" if items else None),
    }


def summaries_for_active_orders(db: sqlite3.Connection, today: str) -> dict[int, dict]:
    by_order: dict[int, list[dict]] = {}
    for r in db.execute(f"{_SELECT} JOIN orders o ON o.id = mt.order_id WHERE o.state = 'active'"):
        by_order.setdefault(r["order_id"], []).append(_present(r, today))
    return {oid: summarise(items) for oid, items in by_order.items()}


def for_buyer(db: sqlite3.Connection, order_id: int) -> list[dict]:
    """What the buyer may see: the name and whether it has arrived. No supplier, quantity, dates or lateness."""
    return [
        {"name": r["name"], "kind": r["kind"], "suppliedBy": r["supplied_by"], "received": r["status"] == "received", "receivedDate": r["received_date"]}
        for r in db.execute("SELECT * FROM order_materials WHERE order_id = ? ORDER BY id", (order_id,))
    ]


# --- Changes ------------------------------------------------------------------------------------------


def _order(db: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    o = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if o is None:
        raise HttpError(404, "Order not found")
    return o


def _require_active(o: sqlite3.Row) -> None:
    if o["state"] != "active":
        raise HttpError(409, f"This order is {o['state']}; its materials can no longer be changed")


def _step_codes(db: sqlite3.Connection, order_id: int) -> set[str]:
    return {r["code"] for r in db.execute("SELECT code FROM milestones WHERE order_id = ?", (order_id,))}


def _clean(db: sqlite3.Connection, order_id: int, v: dict, today: str) -> dict:
    """Validate a whole line (after merging a change onto the current one) and make its dates agree with its status."""
    v = dict(v)
    v["name"] = (v.get("name") or "").strip()
    if not v["name"]:
        raise HttpError(400, "Say what it is")
    for k in ("supplier", "unit", "note"):
        v[k] = (v.get(k) or "").strip() or None
    if v["kind"] not in KINDS:
        raise HttpError(400, "Unknown kind")
    if v["status"] not in ("not_ordered", "ordered", "received") or v["supplied_by"] not in ("us", "buyer"):
        raise HttpError(400, "Unknown status or supplier")
    if v["needed_for"] and v["needed_for"] not in _step_codes(db, order_id):
        raise HttpError(400, "This order's plan has no such step")
    if not v["needed_for"] and not v["needed_by"]:
        raise HttpError(400, "Say which step needs it, or the date it is needed by")
    if v["status"] == "not_ordered":
        v["ordered_date"] = v["expected_date"] = v["received_date"] = None
    elif v["status"] == "ordered":
        v["received_date"] = None
        v["ordered_date"] = v["ordered_date"] or today
    else:
        v["received_date"] = v["received_date"] or today
        if v["received_date"] > today:
            raise HttpError(400, "A received date cannot be in the future")
        v["expected_date"] = v["expected_date"] or None
    if v["ordered_date"] and v["expected_date"] and v["expected_date"] < v["ordered_date"]:
        raise HttpError(400, "It cannot arrive before it was ordered")
    return v


_COLUMNS = ("kind", "name", "supplier", "supplied_by", "qty", "unit", "status", "ordered_date", "expected_date", "received_date", "needed_for", "needed_by", "note")


def add(db: sqlite3.Connection, order_id: int, user_id: int, fields: dict, today: str) -> int:
    _require_active(_order(db, order_id))
    base = {"supplied_by": "us", "status": "not_ordered", "needed_for": None, "needed_by": None, "qty": None, "ordered_date": None, "expected_date": None, "received_date": None}
    v = _clean(db, order_id, {**base, **fields}, today)
    with transaction(db):
        mid = db.execute(
            f"INSERT INTO order_materials (order_id, {', '.join(_COLUMNS)}, updated_by) VALUES (?, {', '.join('?' * len(_COLUMNS))}, ?)",
            (order_id, *(v[c] for c in _COLUMNS), user_id),
        ).lastrowid
        sync_fabric_milestone(db, order_id, user_id, undo=False)
    return mid


def update(db: sqlite3.Connection, material_id: int, user_id: int, changes: dict, today: str) -> int:
    """Returns the order id. `changes` holds only the fields that were sent."""
    cur = db.execute("SELECT * FROM order_materials WHERE id = ?", (material_id,)).fetchone()
    if cur is None:
        raise HttpError(404, "Material not found")
    _require_active(_order(db, cur["order_id"]))
    v = _clean(db, cur["order_id"], {**{c: cur[c] for c in _COLUMNS}, **changes}, today)
    with transaction(db):
        db.execute(
            f"UPDATE order_materials SET {', '.join(f'{c} = ?' for c in _COLUMNS)}, updated_at = datetime('now'), updated_by = ? WHERE id = ?",
            (*(v[c] for c in _COLUMNS), user_id, material_id),
        )
        sync_fabric_milestone(db, cur["order_id"], user_id, undo=cur["status"] == "received" and v["status"] != "received")
    return cur["order_id"]


def remove(db: sqlite3.Connection, material_id: int, user_id: int) -> int:
    cur = db.execute("SELECT * FROM order_materials WHERE id = ?", (material_id,)).fetchone()
    if cur is None:
        raise HttpError(404, "Material not found")
    _require_active(_order(db, cur["order_id"]))
    with transaction(db):
        db.execute("DELETE FROM order_materials WHERE id = ?", (material_id,))
        sync_fabric_milestone(db, cur["order_id"], user_id, undo=False)
    return cur["order_id"]


def add_standard(db: sqlite3.Connection, order_id: int, user_id: int, today: str) -> int:
    """Add the usual fabric, trims and packing that this order does not have yet. Returns how many were added."""
    o = _order(db, order_id)
    _require_active(o)
    codes = _step_codes(db, order_id)
    have = {r["name"].lower() for r in db.execute("SELECT name FROM order_materials WHERE order_id = ?", (order_id,))}
    added = 0
    with transaction(db):
        for kind, name, unit, step, fallback in PRESETS:
            if name.lower() in have:
                continue
            code = next((c for c in (step, *fallback) if c in codes), None)
            db.execute(
                """INSERT INTO order_materials (order_id, kind, name, unit, needed_for, needed_by, updated_by) VALUES (?,?,?,?,?,?,?)""",
                (order_id, kind, name, unit, code, None if code else add_days(o["ex_factory"], -30), user_id),
            )
            added += 1
    return added


def add_main_fabric(db: sqlite3.Connection, order_id: int, user_id: int, ex_factory: str, step_codes: set[str], fabric: dict) -> None:
    """When an order is created with a fabric on it, it starts with a "Main fabric" line to track.
    Call inside the transaction that creates the order."""
    if not any(fabric.get(k) for k in ("type", "composition", "gsm")):
        return
    detail = ", ".join(x for x in (fabric.get("type"), fabric.get("composition"), f"{fabric['gsm']} GSM" if fabric.get("gsm") else None) if x)
    code = next((c for c in ("FAB", "CUT", "STITCH") if c in step_codes), None)
    db.execute(
        "INSERT INTO order_materials (order_id, kind, name, unit, needed_for, needed_by, note, updated_by) VALUES (?,?,?,?,?,?,?,?)",
        (order_id, "fabric", "Main fabric", "kg", code, None if code else add_days(ex_factory, -30), detail, user_id),
    )


def sync_fabric_milestone(db: sqlite3.Connection, order_id: int, user_id: int, undo: bool) -> None:
    """Fabric arriving is the "Fabric in-house" milestone. Once every fabric line is received that milestone
    is marked done on the latest receipt date; if a received fabric line is taken back, the mark is removed.
    Both go into the date history. Call inside a transaction."""
    fabric = db.execute("SELECT status, received_date FROM order_materials WHERE order_id = ? AND kind = 'fabric'", (order_id,)).fetchall()
    ms = db.execute("SELECT id, actual_date FROM milestones WHERE order_id = ? AND code = 'FAB'", (order_id,)).fetchone()
    if not fabric or ms is None:
        return
    everything_in = all(f["status"] == "received" for f in fabric)
    if everything_in and ms["actual_date"] is None:
        new, reason = max(f["received_date"] for f in fabric), "Marked done: all fabric received (materials)"
    elif undo and not everything_in and ms["actual_date"] is not None:
        new, reason = None, "Unmarked: a fabric line is no longer marked received (materials)"
    else:
        return
    db.execute("UPDATE milestones SET actual_date = ? WHERE id = ?", (new, ms["id"]))
    db.execute(
        "INSERT INTO date_changes (order_id, milestone_id, field, old_value, new_value, reason, changed_by) VALUES (?,?,?,?,?,?,?)",
        (order_id, ms["id"], "actual_date", ms["actual_date"], new, reason, user_id),
    )
