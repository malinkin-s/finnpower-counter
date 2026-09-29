# Roadmap

**English** · [Русский](ROADMAP.ru.md)

Two directions:

1. **Production tracking system** — a server with a database, role-based
   sign-in, a production log, saved sessions, a supervisor web page,
   directory and ERP integration. The utility becomes the client at the
   operator's workstation. Stages 0–8 below; architecture in
   [ARCHITECTURE.md](ARCHITECTURE.md); integrations in
   [INTEGRATIONS.md](INTEGRATIONS.md); test benches in
   [TEST_BENCH.md](TEST_BENCH.md); task breakdown in [TASKS.md](TASKS.md).
2. **More data from the machine files** — which other fields are useful to
   an operator or a supervisor and which are not worth taking. Stages A–F.
   Based on the output of the NCeXpress FMS postprocessor.

The tracking system comes first: stages A–F add columns and calculations,
and the system decides where and to whom they are shown.

Status of everything below: **planned, not implemented.** Findings that
shaped this plan are in [FINDINGS.md](FINDINGS.md).

The project is open source and not tied to a particular shop. Everything
site-specific — shifts, operators, retention, directory, ERP — is configured
by the administrator.

---

## Production tracking system

### Scope

| # | Feature | Where | Stage |
|---|---|---|---|
| 1 | Save a session: user-given name plus save date and time | client + server | 5 |
| 2 | Production log: sheets, programs, parts, operator name | server | 3 |
| 3 | Operator identifies at start-up: name from a list plus PIN | client | 2 |
| 4 | Secure sign-in and user registration | server | 1, 2 |
| 5 | Data stored where the administrator decides | server | 1 |
| 6 | Roles: operator in the client, supervisor and admin in a browser | client + server | 1, 2 |
| 7 | Supervisor views production and writes nothing | web | 4 |
| 8 | Production export to CSV | web | 4 |
| 9 | Clients work concurrently, changes show up immediately | server + client | 3, 4 |
| 10 | Administrator settings: shifts, time format, retention, visibility | server | 1 |
| 11 | Sign-in with Active Directory accounts, roles from groups | server | 7 |
| 12 | Integration hub: pluggable, configurable ERP connectors (SyteLine, 1C, webhook, files) and an API for ERPs to read from | server | 8 |

### Decisions

- **Client and server**, not a shared network folder. The shared folder is
  the fallback if a server turns out to be impossible.
- **Server: Linux in Docker** as the primary platform, OS-agnostic code,
  tests on Windows too.
- **Supervisor and administrator use a browser**; only the operator runs the
  client.
- **Operator sign-in: name from a list plus PIN**, only from a registered
  workstation; the server limits attempts.
- **Protection**: TLS in transit, the server sets the author and time of each
  event, server disk encrypted by the OS, client-local files protected with
  DPAPI.
- **Offline, the client keeps working** and sends queued marks later.
- **A session is a named bookmark**; the production log is the single source
  of truth about marks.
- **Standalone mode stays**: without a server the utility works as today.
- **Site-specific settings belong to the administrator**: shift boundaries,
  time format, operators per workstation, retention, visibility.
- **Integrations are plugins** configured in the admin panel, never
  hard-wired; mapping between our data and the ERP's is data, not code.

### Stage 0. Checks and client groundwork

Nothing visible changes.

- On a shop-floor Windows 7 32-bit PC, in a PyInstaller build, check: HTTPS
  to a test server (`http.client` + `ssl`, TLS 1.2, self-signed certificate
  pinned by fingerprint), reading an SSE stream, DPAPI via ctypes. **If any
  of it fails, the client architecture is revisited before anything else.**
- Split `gui.py` into a `ui/` package.
- Background executor: all I/O off the main thread.
- Bring `ssl`, `http`, `socket`, `email`, `urllib` back into the build.

### Stage 1. Server skeleton

- FastAPI, SQLite, migrations; `docker compose up` brings everything up on a
  VM.
- Users and roles, password sign-in to the web panel, first-run setup (the
  first administrator).
- Workstations: creation, one-time registration code.
- Audit log of sign-ins and administrator actions.
- System settings: shift boundaries, time format, retention, visibility.
- CI: server tests on Linux and Windows.

### Stage 2. The client connects

- Client setup: server address and workstation registration code.
- Sign-in window: name from a list plus PIN. Offline sign-in for those who
  have signed in on this PC before.
- The operator window — today's, with the signed-in name and a connection
  indicator.
- Standalone mode when no server is configured.

### Stage 3. Production log

- Every mark and unmark is an event on the server; the server sets the author
  and receive time.
- Outbox for connection drops, resending without duplicates.
- Content-based task ID; marks are restored when the task is opened on any
  workstation.
- Event stream: a mark on one workstation shows up on the others at once.

### Stage 4. Supervisor page

- Production per operator, day, shift, task: sheets, programs, positions,
  pieces.
- Live updates without clicking.
- CSV export (`;`, UTF-8 with BOM — like today's positions export).

### Stage 5. Sessions

- "Save session" in the client: the user types a name, the save date and time
  are added; stored on the server.
- Session list: open and continue; compare with the moment of saving.

### Stage 6. Operations

- PIN reset, blocking and unblocking users and workstations.
- Scheduled backups and restore checks.
- Server installation guide for IT; running as a Windows service.
- Client notification about a new version.
- Data retention job.

### Stage 7. Directory

- Supervisor and administrator sign-in with Active Directory accounts
  (LDAPS); roles from domain groups.
- Operators may be linked to domain accounts; sign-in at the machine stays
  name + PIN.
- Optional browser single sign-on (Kerberos).

### Stage 8. Integration hub

- Connector plugins configured in the admin panel: connection profiles,
  secrets, test button, routing of event types.
- Integration outbox: retries, idempotency, dead letters, delivery log.
- Mapping tables: parts to items, tasks to jobs, operators to employees.
- Integration API: tokens, event feed by cursor, reference-data upload.
- Built-in connectors: webhook, file drop, Infor SyteLine (IDO REST),
  1C (OData). Research first, against a mock ERP until a real one is
  available.

---

## More data from the machine files

Which other data the machine files contain, what is useful to an operator or
a supervisor, and what is not worth taking. The sections "Already used",
"Proposals", "Not worth taking" and "Order of work" below belong to this
direction.

### Already used

| Field | Source | Purpose |
|---|---|---|
| `SHEET_COUNT` | `.nc` | Number of sheets, the run multiplier |
| `PART_NAME`, `QUANTITY` | `.nc`, `PART_DATA` block | Part and quantity per sheet |
| `X_DIM`, `Y_DIM` | `.nc` | Sheet size |
| `NUMBER OF SHEETS`, `SHEET SIZE X/Y` | `.fms`, `#GENERAL` | Cross-check |
| `#RSCUT`, `#COMPONENTS` | `.fms` | Two independent views for the cross-check |

### Proposals

#### 1. Time to the end of the shift task

**Data:** `TOTAL TIME per SHEET` × `NUMBER OF SHEETS` for each program.

**For:** the supervisor first, the operator second.

**Why:** the sum over unfinished programs forecasts the end of the task. It
answers two working questions: will the shift close the task, and what will
be handed over to the next shift.

**Caveat:** this is the CAM estimate, not a measurement. Real time differs
because of sheet loading, jams, tool changes and downtime. Show it as a
guide, not a promise.

#### 2. Weight of finished parts

**Data:** `PART WEIGHT` from `#COMPONENTS`, times the quantity.

**For:** the operator.

**Why:** weight goes into shipping documents and limits how a pallet is
filled by the container's capacity.

**Caveat:** CAM computes weight from geometry and density. It differs from
actual weighing by a few per cent.

#### 3. Material and thickness

**Data:** `MATERIAL`, `THICKNESS` from `#GENERAL`.

**Why:** in a uniform task it matters little, but in a mixed shift it is the
main thing that keeps pallets and positions from being mixed up. A column in
the programs view plus a material filter.

**Cost:** two fields next to those already parsed. The cheapest useful item.

#### 4. Part dimensions

**Data:** `PART_X_DIM` / `PART_Y_DIM` from `.nc`, `Size` from `#RSCUT`.

**Why:** to recognise a part in a stack and decide what to pack it in.

**Where:** in the position window, not the main table — it already has six
columns.

#### 5. Sheet consumption

**Data:** already parsed, nothing new to compute.

**Why:** the sheet total over completed programs is the metal used; over
unfinished ones, what is still needed.

#### 6. What will close a position

**Data:** already available, plus the time from item 1.

**Why:** for an open position show not only the last program but how many
programs remain before it and roughly how long that is. "2 programs left,
about 40 minutes" directly serves the shift-handover scenario the utility was
built for.

#### 7. Forming and bending flag

**Data:** `FORMING`, `BENDING MODE`.

**Why it might matter:** "this part goes to bending" is exactly the
downstream process whose requirements make a complete set necessary.

**First:** find out whether these fields are filled in your CAM. If they are
always zero, drop the item.

#### 8. Order and customer

**Data:** `CUSTOMER`, `ASSEMBLY` in `#COMPONENTS`, the `Order ID` column in the
setup sheet.

**Status:** empty in the files analysed. Whether they are filled depends on
how the particular CAM is used.

**Why it might matter:** grouping by order would be stronger than any other
item, because completeness is checked per order, not per shift.

**Sensible approach:** read the fields and show the column only when they are
not empty. Cheap and harmless.

#### 9. Automatic detection of executed programs

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

### Not worth taking

**Sheet usage efficiency (`SHEET USAGE EFFICIENCY`).** The operator has no
influence on nesting — the CAM engineer does it. The figure does not lead to
any action at the workstation.

**Hits, travel distance, tool changes.** These are about punch wear and
machine time. To be useful they need a cumulative per-tool counter across
shifts, i.e. stored history. The utility used to keep no history; with the
production log (stage 3) it will, and this item can be revisited — but only
if the shop actually tracks tool wear.

**Machine setup parameters** — clamps, stroke, acceleration, speed,
unloading, addresses. The operator sees them on the control during setup.

**Service fields** — internal IDs, addresses, angles, subprogram counts,
program size, file names and generation date.

**Tool list (`#TOOLS`).** Needed during setup, but the operator opens the
setup sheet with a double click, and the same list is there in readable form
with sizes and stations.

### Order of work

Tracking system stages 0–8 first, then the machine-data stages.

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

**Stage F.** Automatic detection of executed programs. With the production
log it is simply another source of events next to manual marks.

### Selection principle

A field gets into the utility if it answers a question the operator or the
supervisor asks during a shift, and if the answer changes what they do.
Everything else is data for the CAM engineer and the setter; it belongs in
the CAM system and the setup sheet, not in a completion tracker.
