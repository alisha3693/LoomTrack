# Run-rate delay projection

Code: [`backend/loomtrack/domain/runrate.py`](../backend/loomtrack/domain/runrate.py) · Tests: [`backend/tests/test_runrate.py`](../backend/tests/test_runrate.py) · See it for every order: `python -m loomtrack.explain`

The goal from the brief: *warnings two weeks early, not two days*, with the maths shown. The projection is plain arithmetic on the supervisors' daily numbers. No AI is involved, so anyone can check it.

## Inputs
- The order quantity and planned ex-factory date.
- The production stages in process order (cutting → printing → stitching → washing → finishing → packing), each with a planned start and end from the TNA template.
- Each stage's daily output, as entered by supervisors.
- A working-day calendar: Monday–Saturday, minus listed holidays.

## Per stage
| Quantity | How |
|---|---|
| done / remaining | sum of daily entries; remaining = order qty − done |
| as-of day | today if today's number is in, else the previous working day (a morning view doesn't punish a day not yet worked) |
| working days left | working days after as-of, up to the planned end |
| **required / day** | remaining ÷ working days left (none once the planned end has passed) |
| **run rate / day** | pieces in the last 7 working days ÷ working days in that window; the window never starts before the stage's first entry |
| own finish | as-of + ⌈remaining ÷ run rate⌉ working days |
| projected finish | the later of own finish and (upstream projected finish + 1 working day) |
| slip | working days from planned end to projected finish |

**No numbers yet:** a stage uses its planned rate (order qty ÷ planned working days), starting at its planned start.

**Starved stages:** if less than one day's planned work is waiting from an unfinished upstream stage, the stage's measured rate reflects the upstream's pace, not its own capacity. The planned rate is used instead, and the upstream chain still limits it. If a real queue is waiting (e.g. 5,400 cut panels sitting at a slow printer), the slow rate is the stage's own and counts against it.

## Per order
- **Projected ex-factory** = planned ex-factory moved by the last stage's slip. This keeps the plan's buffer for final inspection and loading.
- **Red:** projected ex-factory is after the planned one.
- **Amber:** a stage is behind its plan but the buffer still covers ex-factory, or a TNA milestone (e.g. PP approval) is overdue.
- **Green:** otherwise.
- **Key stage** (shown on the board): the worst-slipping stage that is slow on its own numbers, i.e. the root cause rather than a stage merely waiting on it.

## Worked example: D-PO-1112 (synthetic sample order), 5 Nov 2026
6,500 long-sleeve tees, ex-factory Thu 26 Nov. The stitching plan ends Fri 6 Nov.

- Stitching done 3,900 → remaining **2,600**
- Today's number is not in yet, so the as-of day is Wed 4 Nov. Working days left to the planned end: Thu 5 and Fri 6 Nov = **2**
- Required: 2,600 ÷ 2 = **1,300 pcs/day**
- Run rate, 7-day average: **371.3 pcs/day**
- Own finish: ⌈2,600 ÷ 371.3⌉ = ⌈7.002⌉ = 8 working days after 4 Nov → Fri 13 Nov, **6 working days late**
- Finishing and packing at planned capacity absorb it → projected ex-factory Thu 26 Nov = planned → **amber**

On the board: *Stitching is 6 working days behind plan; the buffer still covers ex-factory. Need 1,300 pcs/day for 2 days, making 371 pcs/day (7-day average).*
(`npm run explain` prints these numbers for every order. The seeded date is 5 Nov 2026.)

## The early warning in action: C-PO-0488
Printing (job work) is at 3,100 / 10,000, its planned end (21 Oct) long gone, and is making 443 pcs/day: 6,900 ÷ 442.9 = 15.6, so 16 working days, ending Mon 23 Nov. The chain pushes ex-factory to Mon 30 Nov against Sat 28 Nov. That shows up **on 5 Nov, 23 days before ex-factory**: three weeks to add a second print unit, not two days to beg for air freight.

## Known limits
- A 7-day average reacts to a bad week in about a week. A weighted average is an easy change if the client wants faster reaction.
- Assumes stages can overlap (pipelined production), with 1 working day of lag after the upstream stage finishes.
- Does not model capacity shared between orders on the same line. The capacity check at acceptance (services/capacity.py) does look at what is booked on a unit, but it is a separate calculation and does not change this projection.
