"""Seed a fresh database:  python -m loomtrack.seed

The first three orders are the brief's sample data (PO, buyer, style, qty,
ex-factory, current stage and qty done exactly as given). Everything else —
the other orders, buyer D, daily history, notes, people — is synthetic, so
the board shows a realistic mix.

Daily history is generated backwards from "today" at a steady rate so the
run-rate engine has something to average. Set LOOMTRACK_TODAY=2026-11-05 to
reproduce the documented demo exactly.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import uuid
from dataclasses import dataclass, field

from . import config
from .ai.classifier import classify_by_keywords, classify_note, ai_status
from .config import CALENDAR
from .db import SCHEMA, open_db, transaction
from .domain.tna import plan_from_template
from .security import hash_secret, new_token
from .services.orders import next_order_no, refresh_all_active
from .services import materials
from .services.templates import load_template

BUYERS = [
    ("Company B (UK)", "United Kingdom"),
    ("Company C (Germany)", "Germany"),
    ("Company D (Netherlands)", "Netherlands"),  # synthetic
]

# Demo sign-ins for the buyers' own people (buyer, name, email, password).
BUYER_LOGINS = [
    ("Company B (UK)", "Hannah Clarke", "hannah@companyb.example", "buyer1234"),
    ("Company C (Germany)", "Jonas Weber", "jonas@companyc.example", "buyer1234"),
]

UNIT1, UNIT2, UNIT3 = "Unit 1 · Avinashi Road", "Unit 2 · Tiruppur North", "Unit 3 · Palladam"
PRINTER, WASHER = "Sri Murugan Prints (job work)", "Velan Garment Wash (job work)"
UNITS = [(UNIT1, "own", None), (UNIT2, "own", None), (UNIT3, "own", None), (PRINTER, "subcontract", "printing"), (WASHER, "subcontract", "washing")]
SUBCONTRACTOR = {"printing": PRINTER, "washing": WASHER}
# Pieces a day each of our units can stitch (demo figures).
CAPACITY = {UNIT1: 1400, UNIT2: 1300, UNIT3: 1200}

USERS = [
    ("Priya S.", "merchandiser", "priya@companya.in", "loom1234", None, "en"),
    ("Arun K.", "merchandiser", "arun@companya.in", "loom1234", None, "en"),
    ("Murugan", "supervisor", "9840000001", "1111", UNIT1, "ta"),
    ("Lakshmi", "supervisor", "9840000002", "2222", UNIT2, "ta"),
    ("Selvi", "supervisor", "9840000003", "3333", UNIT3, "ta"),
    ("Ravi (Sri Murugan Prints)", "supervisor", "9840000004", "4444", PRINTER, "ta"),
    ("Velan (Garment Wash)", "supervisor", "9840000005", "5555", WASHER, "ta"),
]


@dataclass
class Stage:
    done: int
    rate: float  # recent pieces per working day
    today: bool = False  # has today's number already come in?
    notes: list[str] = field(default_factory=list)  # oldest first; the newest lands on the newest day


@dataclass
class Order:
    po: str
    buyer: str
    style: str
    colour: str
    ex_factory: str
    unit: str
    template: str
    sizes: list[tuple[str, int]]
    stages: dict[str, Stage]
    pending_milestones: tuple[str, ...] = ()  # deliberately left not done (overdue TNA items)
    synthetic: bool = False


ORDERS = [
    # --- Sample data from the brief -----------------------------------------------
    Order("B-PO-88213", "Company B (UK)", "Men's crew neck tee", "Navy", "2026-11-20", UNIT1, "basic",
          [("S", 2000), ("M", 3600), ("L", 3600), ("XL", 2000), ("XXL", 800)],
          {"CUT": Stage(12000, 1300),
           "STITCH": Stage(6800, 700, today=True, notes=["இரண்டு மெஷின் பழுது, மெக்கானிக் வர மதியம் ஆனது",
                                                        "இன்று 8 ஆட்கள் லீவு, அதனால் உற்பத்தி குறைவு"])}),
    Order("B-PO-88240", "Company B (UK)", "Men's polo", "White", "2026-11-12", UNIT2, "basic",
          [("S", 1200), ("M", 2400), ("L", 2400), ("XL", 1400), ("XXL", 600)],
          {"CUT": Stage(8000, 1100), "STITCH": Stage(8000, 800),
           "FINISH": Stage(5200, 650, today=True, notes=["ஷேட் வித்தியாசம் வந்தது, 300 பீஸ் ரீவொர்க் செய்கிறோம்"]),
           "PACK": Stage(3000, 900, today=True, notes=["கார்ட்டன் பெட்டி இன்னும் வரவில்லை"])}),
    Order("C-PO-0488", "Company C (Germany)", "Kids printed tee", "Yellow", "2026-11-28", UNIT1, "printed",
          [("2-3Y", 1800), ("4-5Y", 2400), ("6-7Y", 2400), ("8-9Y", 2000), ("10-11Y", 1400)],
          {"CUT": Stage(8500, 950),
           "PRINT": Stage(3100, 520, notes=["பிரிண்டிங் யூனிட்டில் கரண்ட் இல்லை, ஜெனரேட்டர் டீசல் தீர்ந்தது"]),
           "STITCH": Stage(1200, 600)}),
    # --- Synthetic orders -------------------------------------------------------------
    Order("B-PO-88277", "Company B (UK)", "Ladies vest top", "Black", "2026-11-25", UNIT3, "basic",
          [("XS", 1000), ("S", 2200), ("M", 2800), ("L", 2000), ("XL", 1000)],
          {"CUT": Stage(9000, 1200), "STITCH": Stage(7600, 820, today=True, notes=["எல்லாம் சரியாக நடக்கிறது"]),
           "FINISH": Stage(3000, 700)}, synthetic=True),
    Order("B-PO-88301", "Company B (UK)", "Men's henley", "Grey marl", "2026-12-10", UNIT2, "basic",
          [("S", 900), ("M", 1800), ("L", 1800), ("XL", 1100), ("XXL", 400)],
          {"CUT": Stage(2400, 600)}, synthetic=True),
    Order("C-PO-0495", "Company C (Germany)", "Kids hoodie, garment washed", "Washed blue", "2026-11-18", UNIT3, "washed",
          [("4-5Y", 1200), ("6-7Y", 1400), ("8-9Y", 1400), ("10-11Y", 1000)],
          {"CUT": Stage(5000, 800), "STITCH": Stage(5000, 600),
           "WASH": Stage(2200, 420, notes=["வாஷிங் கெமிக்கல் தாமதம், நாளை முதல் சரியாகும்"]),
           "FINISH": Stage(1500, 400)}, synthetic=True),
    Order("C-PO-0502", "Company C (Germany)", "Kids shorts set", "Navy / white", "2026-12-05", UNIT2, "printed",
          [("2-3Y", 1400), ("4-5Y", 2000), ("6-7Y", 2000), ("8-9Y", 1600)],
          {"CUT": Stage(1500, 500)}, pending_milestones=("PP",), synthetic=True),
    Order("D-PO-1107", "Company D (Netherlands)", "Organic cotton tee", "Ecru", "2026-12-15", UNIT1, "basic",
          [("S", 3000), ("M", 4500), ("L", 4500), ("XL", 3000)], {}, synthetic=True),
    Order("D-PO-1112", "Company D (Netherlands)", "Long-sleeve tee", "Olive", "2026-11-26", UNIT3, "basic",
          [("S", 1300), ("M", 2000), ("L", 2000), ("XL", 1200)],
          {"CUT": Stage(6500, 900), "STITCH": Stage(3900, 380)}, synthetic=True),
]


# Fabric on each demo order: type, composition, GSM, note.
FABRIC = {
    "B-PO-88213": ("Single jersey", "100% cotton, combed", 180, "Bio-washed"),
    "B-PO-88240": ("Pique", "100% cotton", 220, None),
    "C-PO-0488": ("Single jersey", "100% cotton", 160, "Print-ready, OEKO-TEX"),
    "B-PO-88277": ("Single jersey", "95% cotton, 5% elastane", 190, None),
    "B-PO-88301": ("Slub jersey", "100% cotton", 170, None),
    "C-PO-0495": ("Fleece, brushed back", "80% cotton, 20% polyester", 280, "Garment washed"),
    "C-PO-0502": ("Single jersey", "100% cotton", 150, None),
    "D-PO-1107": ("Single jersey", "100% organic cotton (GOTS)", 180, "Certified mill, longer lead time"),
    "D-PO-1112": ("Rib 1x1", "95% cotton, 5% elastane", 200, None),
}

# Where a demo material stands when it is not simply "arrived in time": (status, ordered, expected, received).
STOCK_OVERRIDES = {
    ("B-PO-88240", "Carton"): ("ordered", "2026-10-28", "2026-11-04", None),          # the floor note says the cartons have not come
    ("B-PO-88301", "Sewing thread"): ("ordered", "2026-11-03", "2026-11-20", None),   # arrives after stitching starts
    ("B-PO-88301", "Main label"): ("not_ordered", None, None, None),                 # not ordered and stitching starts soon
    ("D-PO-1107", "Main fabric"): ("ordered", "2026-10-27", "2026-11-20", None),     # organic cotton: arrives after the plan wants it
    ("D-PO-1107", "Rib / collar fabric"): ("ordered", "2026-10-27", "2026-11-12", None),
}


def _stock_up(db, order_id: int, po: str, today: str, user_id: int) -> None:
    """Give a demo order its materials. Fabric is in once cutting has begun; trims and packing are in once the step that uses them has started."""
    materials.add_standard(db, order_id, user_id, today)
    yesterday = CALENDAR.prev_working_day(today)
    plan = {r["code"]: r for r in db.execute("SELECT code, planned_start, planned_date FROM milestones WHERE order_id = ?", (order_id,))}
    cutting = db.execute(
        "SELECT 1 FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id WHERE m.order_id = ? AND m.code = 'CUT'", (order_id,)
    ).fetchone()
    with transaction(db):
        for m in db.execute("SELECT id, kind, name, needed_for FROM order_materials WHERE order_id = ?", (order_id,)).fetchall():
            step = plan.get(m["needed_for"])
            needed = (step["planned_start"] or step["planned_date"]) if step else None
            if m["kind"] == "fabric":
                arrived = bool(cutting) or (step is not None and step["planned_date"] < today)
                state = ("received", None, None, min(step["planned_date"], yesterday)) if arrived else ("ordered", None, step["planned_date"], None)
            else:
                if needed is not None and needed < today:
                    state = ("received", None, None, CALENDAR.shift_working_days(needed, -2))
                elif needed is not None and needed <= CALENDAR.shift_working_days(today, 20):
                    state = ("ordered", None, max(CALENDAR.shift_working_days(needed, -3), CALENDAR.next_working_day(today)), None)
                else:
                    state = ("not_ordered", None, None, None)
            status, ordered, expected, received = STOCK_OVERRIDES.get((po, m["name"]), state)
            db.execute(
                "UPDATE order_materials SET status = ?, ordered_date = ?, expected_date = ?, received_date = ? WHERE id = ?",
                (status, ordered or (CALENDAR.shift_working_days(expected, -10) if status == "ordered" and expected else None), expected, received, m["id"]),
            )
        materials.sync_fabric_milestone(db, order_id, user_id, undo=False)


def _jitter(key: str) -> float:
    """Deterministic ±15% so the same seed gives the same history."""
    return 0.85 + hashlib.sha1(key.encode()).digest()[0] / 255 * 0.3


def _history(total: int, rate: float, end: str, key: str) -> list[tuple[str, int]]:
    """Split `total` into daily entries ending on `end`, newest first."""
    out, d, left = [], end, total
    while left > 0:
        q = min(left, round(rate * _jitter(f"{key}:{d}")))
        out.append((d, q))
        left -= q
        d = CALENDAR.prev_working_day(d)
    return out


def _placeholder_photo(name: str, label: str) -> str:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
  <rect width="640" height="480" fill="#e9e7e2"/>
  <g fill="none" stroke="#b9b4aa" stroke-width="2"><path d="M220 140 l60 -30 h80 l60 30 l40 70 l-50 25 l-20 -35 v175 h-140 v-175 l-20 35 l-50 -25z"/></g>
  <text x="320" y="420" font-family="sans-serif" font-size="20" fill="#6b665d" text-anchor="middle">{html.escape(label)}</text>
  <text x="320" y="450" font-family="sans-serif" font-size="14" fill="#8e897f" text-anchor="middle">placeholder · seed data</text>
</svg>"""
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = config.UPLOAD_DIR / name
    path.write_text(svg, encoding="utf-8")
    return str(path)


# Demo swatches for the seeded colours (approximate screen colours, not dye specs).
COLOUR_HEX = {"Navy": "#1F2A44", "White": "#FFFFFF", "Yellow": "#F2C400", "Black": "#111111", "Grey marl": "#9CA3AF",
              "Washed blue": "#6F8FB3", "Ecru": "#E8DCC4", "Olive": "#6B7041"}


async def seed(db, today: str) -> None:
    # The append-only trails refuse deletes; lift that for the reset and restore it from the schema afterwards.
    for trigger in ("date_changes_no_delete", "request_messages_no_delete", "order_messages_no_delete"):
        db.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    for t in ["attachments", "request_messages", "request_sizes", "order_requests", "order_messages", "date_changes", "outbox_messages", "warnings",
              "issue_reasons", "photos", "daily_updates", "order_materials", "milestones", "order_sizes", "orders", "sessions", "users", "units", "buyers"]:
        db.execute(f"DELETE FROM {t}")
    db.executescript(SCHEMA)

    buyer_id = {name: db.execute("INSERT INTO buyers (name, country, link_token) VALUES (?,?,?)", (name, country, new_token())).lastrowid for name, country in BUYERS}
    unit_id = {name: db.execute("INSERT INTO units (name, kind, process, daily_capacity) VALUES (?,?,?,?)", (name, kind, proc, CAPACITY.get(name))).lastrowid for name, kind, proc in UNITS}
    supervisor_of: dict[int, int] = {}
    merch_id = None
    for name, role, login, secret, unit, lang in USERS:
        uid = db.execute(
            "INSERT INTO users (name, role, login, secret_hash, unit_id, lang) VALUES (?,?,?,?,?,?)",
            (name, role, login, hash_secret(secret), unit_id.get(unit), lang),
        ).lastrowid
        if unit:
            supervisor_of[unit_id[unit]] = uid
        merch_id = merch_id or (uid if role == "merchandiser" else None)

    for buyer, name, email, secret in BUYER_LOGINS:
        db.execute("INSERT INTO users (name, role, login, secret_hash, lang, buyer_id) VALUES (?,?,?,?,?,?)",
                   (name, "buyer", email, hash_secret(secret), "en", buyer_id[buyer]))

    to_classify: list[tuple[str, str]] = []
    yesterday = CALENDAR.prev_working_day(today)

    with transaction(db):
        for o in ORDERS:
            t = load_template(db, o.template)
            qty = sum(q for _, q in o.sizes)
            own = unit_id[o.unit]
            order_id = db.execute(
                "INSERT INTO orders (order_no, po_no, buyer_id, style, colour, colour_hex, qty_total, ex_factory, unit_id, template_key, merchandiser_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (next_order_no(db, today), o.po, buyer_id[o.buyer], o.style, o.colour, COLOUR_HEX.get(o.colour), qty, o.ex_factory, own, t.key, merch_id),
            ).lastrowid
            for n, (size, q) in enumerate(o.sizes, start=1):
                db.execute("INSERT INTO order_sizes (order_id, seq, size, qty) VALUES (?,?,?,?)", (order_id, n, size, q))
            fab = FABRIC[o.po]
            db.execute("UPDATE orders SET fabric_type = ?, fabric_composition = ?, fabric_gsm = ?, fabric_note = ? WHERE id = ?", (*fab, order_id))
            materials.add_main_fabric(db, order_id, merch_id, o.ex_factory, {i.code for i in t.items}, {"type": fab[0], "composition": fab[1], "gsm": fab[2]})

            for p in plan_from_template(CALENDAR, t, o.ex_factory):
                it = p.item
                unit = (unit_id[SUBCONTRACTOR[it.process]] if it.process in SUBCONTRACTOR else own) if it.kind == "stage" else None
                ms_done = it.kind == "milestone" and it.code != "EXF" and p.planned_date < today and it.code not in o.pending_milestones
                ms_id = db.execute(
                    "INSERT INTO milestones (order_id, seq, code, planned_start, planned_date, actual_date, unit_id) VALUES (?,?,?,?,?,?,?)",
                    (order_id, p.seq, it.code, p.planned_start, p.planned_date, p.planned_date if ms_done else None, unit),
                ).lastrowid

                s = o.stages.get(it.code) if it.kind == "stage" else None
                if not s or not s.done:
                    continue
                # A finished stage finished on (or before) its plan; a running one ends today or yesterday.
                end = min(p.planned_date, yesterday) if s.done >= qty else (today if s.today else yesterday)
                for i, (day, q) in enumerate(_history(s.done, s.rate, end, f"{o.po}:{it.code}")):
                    upd = str(uuid.uuid4())
                    note = s.notes[len(s.notes) - 1 - i] if i < len(s.notes) else None
                    db.execute(
                        "INSERT INTO daily_updates (id, milestone_id, user_id, work_date, qty, note_text, note_source, received_at) VALUES (?,?,?,?,?,?,?,?)",
                        (upd, ms_id, supervisor_of[unit], day, q, note, "text" if note else None, f"{day} 18:{10 + i % 40:02d}:00"),
                    )
                    if note:
                        db.execute("INSERT INTO issue_reasons (update_id) VALUES (?)", (upd,))
                        to_classify.append((upd, note))
                    if i < 2:  # a placeholder floor photo on the two most recent days of each stage
                        path = _placeholder_photo(f"seed-{o.po}-{it.code}-{i}.svg", f"{o.style} · {it.name_en} · {day}")
                        db.execute("INSERT INTO photos (update_id, path, mime) VALUES (?,?,?)", (upd, path, "image/svg+xml"))

        # One audited planned-date change: the buyer agreed a later window.
        henley = db.execute("SELECT id FROM orders WHERE po_no = 'B-PO-88301'").fetchone()["id"]
        db.execute(
            "INSERT INTO date_changes (order_id, field, old_value, new_value, reason, changed_by, changed_at) VALUES (?,?,?,?,?,?,?)",
            (henley, "ex_factory", "2026-12-05", "2026-12-10", "Buyer moved the ship window (email from Company B sourcing, 21 Oct)", merch_id, "2026-10-21 11:42:00"),
        )

    for r in db.execute("SELECT id, po_no FROM orders").fetchall():
        _stock_up(db, r["id"], r["po_no"], today, merch_id)

    # Classify seeded notes exactly the way live notes are classified.
    use_model = (await ai_status())["mode"] == "ollama"
    for upd, note in to_classify:
        error = None
        try:
            r = await classify_note(note) if use_model else classify_by_keywords(note)
        except Exception as e:
            r, error = classify_by_keywords(note), str(e)[:300]
        db.execute(
            "UPDATE issue_reasons SET ai_category = ?, ai_translation = ?, ai_confidence = ?, ai_source = ?, ai_error = ?, final_category = ?, classified_at = datetime('now') WHERE update_id = ?",
            (r.category, r.translation, r.confidence, r.source, error, r.category, upd),
        )

    refresh_all_active(db, today)

    # Demo: the polo's delay has already been confirmed and sent to Company B.
    w = db.execute(
        "SELECT w.id, w.buyer_message, o.buyer_id, o.id AS order_id, o.po_no FROM warnings w JOIN orders o ON o.id = w.order_id WHERE o.po_no = 'B-PO-88240' AND w.state = 'pending'"
    ).fetchone()
    if w:
        db.execute("UPDATE warnings SET state = 'confirmed', decided_by = ?, decided_at = datetime('now') WHERE id = ?", (merch_id, w["id"]))
        db.execute(
            "INSERT INTO outbox_messages (buyer_id, order_id, channel, subject, body) VALUES (?,?,?,?,?)",
            (w["buyer_id"], w["order_id"], "email", f"Production update: {w['po_no']}", w["buyer_message"]),
        )


def main() -> None:
    today = config.today()
    db = open_db(config.DB_FILE)
    status = asyncio.run(ai_status())
    print(f"Seeding for {today} · AI: {status.get('model') or 'keyword fallback'} {('(' + status['reason'] + ')') if 'reason' in status else ''}")
    asyncio.run(seed(db, today))

    print(f"\n{'PO':<12} {'status':<7} {'ex-factory':<11} projected")
    for r in db.execute("SELECT po_no, status, ex_factory, projected_ex_factory FROM orders ORDER BY CASE status WHEN 'red' THEN 0 WHEN 'amber' THEN 1 ELSE 2 END, ex_factory"):
        print(f"{r['po_no']:<12} {r['status']:<7} {r['ex_factory']:<11} {r['projected_ex_factory']}")
    print("\nBuyer links (open on the web app):")
    for r in db.execute("SELECT name, link_token FROM buyers"):
        print(f"  {r['name']:<26} /b/{r['link_token']}")
    print("\nLogins: priya@companya.in / loom1234 (merchandiser) · 9840000001 / 1111 (supervisor, Unit 1) · hannah@companyb.example / buyer1234 (buyer) · more in README")


if __name__ == "__main__":
    main()
