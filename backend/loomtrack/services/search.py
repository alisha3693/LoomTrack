"""One search box for the office: orders, requests and buyers by what people actually type (PO, our number, style, colour, buyer)."""

from __future__ import annotations

import sqlite3

LIMIT = 6


def _like(text: str) -> str:
    """The text as a LIKE pattern that matches it literally."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search(db: sqlite3.Connection, q: str) -> dict:
    q = " ".join((q or "").split())[:60]
    if len(q) < 2:
        return {"orders": [], "requests": [], "buyers": []}
    pat = _like(q)
    orders = db.execute(
        """SELECT o.id, o.po_no, o.order_no, o.style, o.colour, o.state, o.status, b.name AS buyer
           FROM orders o JOIN buyers b ON b.id = o.buyer_id
           WHERE o.po_no LIKE ?1 ESCAPE '\\' OR o.order_no LIKE ?1 ESCAPE '\\' OR o.style LIKE ?1 ESCAPE '\\'
              OR o.colour LIKE ?1 ESCAPE '\\' OR b.name LIKE ?1 ESCAPE '\\'
           ORDER BY (o.state = 'active') DESC, o.ex_factory LIMIT ?2""",
        (pat, LIMIT),
    ).fetchall()
    requests = db.execute(
        """SELECT r.id, r.request_no, r.po_no, r.style, r.kind, r.status, b.name AS buyer
           FROM order_requests r JOIN buyers b ON b.id = r.buyer_id
           WHERE r.po_no LIKE ?1 ESCAPE '\\' OR r.request_no LIKE ?1 ESCAPE '\\' OR r.style LIKE ?1 ESCAPE '\\' OR b.name LIKE ?1 ESCAPE '\\'
           ORDER BY r.updated_at DESC LIMIT ?2""",
        (pat, LIMIT),
    ).fetchall()
    buyers = db.execute("SELECT id, name, country FROM buyers WHERE name LIKE ?1 ESCAPE '\\' ORDER BY name LIMIT ?2", (pat, LIMIT)).fetchall()
    return {
        "orders": [{"id": o["id"], "poNo": o["po_no"], "orderNo": o["order_no"], "style": o["style"], "colour": o["colour"],
                    "state": o["state"], "status": o["status"], "buyer": o["buyer"]} for o in orders],
        "requests": [{"id": r["id"], "requestNo": r["request_no"], "poNo": r["po_no"], "style": r["style"], "kind": r["kind"],
                      "status": r["status"], "buyer": r["buyer"]} for r in requests],
        "buyers": [dict(b) for b in buyers],
    }
