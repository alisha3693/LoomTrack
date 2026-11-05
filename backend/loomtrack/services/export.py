"""Weekly status workbook per buyer.

The buyer edition is built from the same allow-listed view the buyer link
uses; the internal edition adds status colour and projections for the office.
"""

from __future__ import annotations

import io
import sqlite3
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side

from ..util import iso_week
from .buyer_view import buyer_orders
from .orders import compute_projection

STATUS_FILL = {"green": "DCF2E3", "amber": "FBEBC8", "red": "F8D7D5"}


def weekly_workbook(db: sqlite3.Connection, buyer_id: int, today: str, audience: Literal["buyer", "internal"]) -> bytes:
    buyer = db.execute("SELECT name FROM buyers WHERE id = ?", (buyer_id,)).fetchone()
    if buyer is None:
        raise LookupError("Unknown buyer")

    wb = Workbook()
    ws = wb.active
    ws.title = f"Status {iso_week(today)}"
    ws.append([f"{buyer['name']} — weekly order status"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Week {iso_week(today)} · generated {today}"])
    ws["A2"].font = Font(color="666666")
    ws.append([])

    orders = buyer_orders(db, buyer_id, today)
    stage_names: list[str] = []
    for o in orders:
        for m in o["milestones"]:
            if m["kind"] == "stage" and m["name"] not in stage_names:
                stage_names.append(m["name"])

    header = ["PO", "Style", "Colour", "Qty", "Ex-factory", "Expected ex-factory"]
    if audience == "internal":
        header += ["Status", "Slack (working days)"]
    header += [f"{s} %" for s in stage_names] + ["Next milestone", "Notice"]
    ws.append(header)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.border = Border(bottom=Side(style="thin"))

    for o in orders:
        nxt = next((m for m in o["milestones"] if not m["actualDate"] and m["pct"] < 100), None)
        by_name = {m["name"]: m for m in o["milestones"]}
        expected = o["notice"]["expectedExFactory"] if o["notice"] else "On plan"
        row: list = [o["poNo"], o["style"], o["colour"], o["qty"], o["exFactory"], expected]
        status = None
        if audience == "internal":
            order = db.execute("SELECT * FROM orders WHERE id = ?", (o["id"],)).fetchone()
            p = compute_projection(db, order, today).p
            status = p.status
            row[5] = p.projected_ex_factory
            row += [p.status.upper(), p.slack_days]
        row += [by_name[n]["pct"] if n in by_name else "" for n in stage_names]
        row += [f"{nxt['name']} ({nxt['plannedDate']})" if nxt else "—", o["notice"]["message"] if o["notice"] else ""]
        ws.append(row)
        if status:
            ws.cell(row=ws.max_row, column=7).fill = PatternFill("solid", fgColor=STATUS_FILL[status])

    for i, col in enumerate(ws.iter_cols(min_row=4, max_row=4), start=1):
        letter = col[0].column_letter
        ws.column_dimensions[letter].width = 70 if i == len(header) else 22 if i <= 3 else 14

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
