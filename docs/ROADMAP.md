# Roadmap

**English** · [Русский](ROADMAP.ru.md)

Which other data the machine files contain, what is useful to an operator or
a supervisor, and what is not worth taking. Based on the output of the
NCeXpress FMS postprocessor. The task breakdown is in [TASKS.md](TASKS.md).

Status of everything below: **planned, not implemented.**

The utility stays standalone: read-only, no network, no history. Growing it
into a production tracking system — server, sign-in, production log,
supervisor page, ERP integration — is a separate project,
**[Nestrack](https://github.com/malinkin-s/nestrack)**, which reuses this parser. Parser improvements made here
reach Nestrack too.

---

## Already used

| Field | Source | Purpose |
|---|---|---|
| `SHEET_COUNT` | `.nc` | Number of sheets, the run multiplier |
| `PART_NAME`, `QUANTITY` | `.nc`, `PART_DATA` block | Part and quantity per sheet |
| `X_DIM`, `Y_DIM` | `.nc` | Sheet size |
| `NUMBER OF SHEETS`, `SHEET SIZE X/Y` | `.fms`, `#GENERAL` | Cross-check |
| `#RSCUT`, `#COMPONENTS` | `.fms` | Two independent views for the cross-check |

## Proposals

### 1. Time to the end of the shift task

**Data:** `TOTAL TIME per SHEET` × `NUMBER OF SHEETS` for each program.

**For:** the supervisor first, the operator second.

**Why:** the sum over unfinished programs forecasts the end of the task. It
answers two working questions: will the shift close the task, and what will
be handed over to the next shift.

**Caveat:** this is the CAM estimate, not a measurement. Real time differs
because of sheet loading, jams, tool changes and downtime. Show it as a
guide, not a promise.

### 2. Weight of finished parts

**Data:** `PART WEIGHT` from `#COMPONENTS`, times the quantity.

**For:** the operator.

**Why:** weight goes into shipping documents and limits how a pallet is
filled by the container's capacity.

**Caveat:** CAM computes weight from geometry and density. It differs from
actual weighing by a few per cent.

### 3. Material and thickness

**Data:** `MATERIAL`, `THICKNESS` from `#GENERAL`.

**Why:** in a uniform task it matters little, but in a mixed shift it is the
main thing that keeps pallets and positions from being mixed up. A column in
the programs view plus a material filter.

**Cost:** two fields next to those already parsed. The cheapest useful item.

### 4. Part dimensions

**Data:** `PART_X_DIM` / `PART_Y_DIM` from `.nc`, `Size` from `#RSCUT`.

**Why:** to recognise a part in a stack and decide what to pack it in.

**Where:** in the position window, not the main table — it already has six
columns.

### 5. Sheet consumption

**Data:** already parsed, nothing new to compute.

**Why:** the sheet total over completed programs is the metal used; over
unfinished ones, what is still needed.

### 6. What will close a position

**Data:** already available, plus the time from item 1.

**Why:** for an open position show not only the last program but how many
programs remain before it and roughly how long that is. "2 programs left,
about 40 minutes" directly serves the shift-handover scenario the utility was
built for.

### 7. Forming and bending flag

**Data:** `FORMING`, `BENDING MODE`.

**Why it might matter:** "this part goes to bending" is exactly the
downstream process whose requirements make a complete set necessary.

**First:** find out whether these fields are filled in your CAM. If they are
always zero, drop the item.

### 8. Order and customer

**Data:** `CUSTOMER`, `ASSEMBLY` in `#COMPONENTS`, the `Order ID` column in the
setup sheet.

**Status:** empty in the files analysed. Whether they are filled depends on
how the particular CAM is used.

**Why it might matter:** grouping by order would be stronger than any other
item, because completeness is checked per order, not per shift.

**Sensible approach:** read the fields and show the column only when they are
not empty. Cheap and harmless.

### 9. Automatic detection of executed programs

**Status: deferred.**

The machine control software keeps its own records: a program queue with the
number of sheets done, and data-collection logs with a line per processed
sheet. The fact of execution could be taken from there instead of manual
marks.

Feasible, but it needs access to the machine's file system and answers that
can only be found on site: can the shop-floor PC reach the folder, does the
queue match the shift task, do the file names match.

**Side effect on the model:** such sources give the number of sheets done,
not just "program fully done". That changes how production is counted and
will need a core change.

Manual marking stays in any case: the source may be unavailable, and the
utility must work without it.

## Not worth taking

**Sheet usage efficiency (`SHEET USAGE EFFICIENCY`).** The operator has no
influence on nesting — the CAM engineer does it. The figure does not lead to
any action at the workstation.

**Hits, travel distance, tool changes.** These are about punch wear and
machine time. To be useful they need a cumulative per-tool counter across
shifts, i.e. stored history. The utility keeps no history and should not;
stored history belongs to [Nestrack](https://github.com/malinkin-s/nestrack), where this item can be revisited
— but only if the shop actually tracks tool wear.

**Machine setup parameters** — clamps, stroke, acceleration, speed,
unloading, addresses. The operator sees them on the control during setup.

**Service fields** — internal IDs, addresses, angles, subprogram counts,
program size, file names and generation date.

**Tool list (`#TOOLS`).** Needed during setup, but the operator opens the
setup sheet with a double click, and the same list is there in readable form
with sizes and stations.

## Order of work

**Stage A.** Material and thickness, sheet consumption, part dimensions in
the position window. The data is already parsed nearby.

**Stage B.** Extend the fixture generator: different time per sheet,
different materials and thicknesses, weights, forming flag. Without it the
following stages cannot be tested.

**Stage C.** Time: estimate per program, forecast to the end of the task,
"what will close the position".

**Stage D.** Weight per position and per program, export to the route sheet.

**Stage E.** Forming and bending, order and customer — shown only when
filled.

**Stage F.** Automatic detection of executed programs. In Nestrack it would
be another source of production events next to manual marks.

## Selection principle

A field gets into the utility if it answers a question the operator or the
supervisor asks during a shift, and if the answer changes what they do.
Everything else is data for the CAM engineer and the setter; it belongs in
the CAM system and the setup sheet, not in a completion tracker.
