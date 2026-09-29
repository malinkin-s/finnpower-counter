# Tasks

Detailed breakdown of [ROADMAP.md](ROADMAP.md). Architecture and the reasons
behind it are in [ARCHITECTURE.md](ARCHITECTURE.md); the facts that shaped the
plan are in [FINDINGS.md](FINDINGS.md).

Status of every task: **not started**, unless marked otherwise.

## Conventions

- **ID** — `S<stage>-<nn>` for the tracking system (stages 0–8), `R-<nn>` for
  research, `TB-<nn>` for test benches, `M-<nn>` for maintenance items from
  the audit, `D<stage>-<nn>` for machine-data stages A–F.
- **Size** — rough effort: **S** up to a day, **M** two to four days,
  **L** one to two weeks.
- **Done when** — acceptance criteria. A task is not done until they hold and
  the tests for it are in CI.
- One task, one pull request where practical.
- New code, comments, commit messages and documents are in English.

## Order at a glance

```
S0-01 ──► (gate) ──► S1 ──► S2 ──► S3 ──► S4
S0-02..06 ─────────────────► S2       S3 ──► S5
                                            S6 runs alongside S3–S5
                     S1 ──► S7 (directory, after R-03)
                     S3 ──► S8 (integration hub, after R-01/R-02)
TB-xx: built ahead of the stage that needs them
M-xx: any time, independent
```

- **S0-01 is a gate.** If Windows 7 cannot do what the client needs, the
  architecture is revisited before S1 starts.
- S0-02…S0-06 do not depend on the server and can start at once.
- S1 can start as soon as S0-01 passes; it does not need S0-02…06.

---

## Stage 0 — Checks and client groundwork

### S0-01 Windows 7 compatibility probe · L · gate

**Goal.** Prove on a real shop-floor PC that the client can do everything the
architecture expects of it.

**Scope.**
- A throw-away probe server (any machine, e.g. a VM): HTTPS with a
  self-signed certificate, one JSON endpoint, one SSE endpoint that emits an
  event every second.
- A probe client built with the same PyInstaller settings as the real
  `.exe` (Python 3.8.10, 32-bit), no third-party packages:
  1. HTTPS request with TLS 1.2 and certificate pinning by SHA-256
     fingerprint (reject any other certificate);
  2. read the SSE stream for a minute, survive a server restart, reconnect;
  3. DPAPI `CryptProtectData` / `CryptUnprotectData` round-trip via ctypes,
     machine and user scope;
  4. report everything into a text file.
- Run on the target PC (Windows 7 32-bit), and for comparison on a
  current Windows.

**Done when.** All four checks pass on the target PC, results are recorded in
FINDINGS.md (as PLN-xx), and the probe code is kept under `tools/probe/` for
re-runs.

**If it fails.** Record what failed; revisit ARCHITECTURE.md before S1.

### S0-02 Split `gui.py` into a `ui/` package · M

**Goal.** Make room for new windows without growing a monolith (PLN-08).

**Scope.** `ui/app.py` (start-up, crash hook), `ui/operator.py` (today's main
window), `ui/part_window.py`, `ui/widgets.py` (shared helpers). No behaviour
change. `app.py` and `app.spec` updated.

**Done when.** The application looks and behaves exactly as before; all tests
pass; the PyInstaller build runs.

### S0-03 Background executor · M

**Goal.** No I/O on the Tk main thread (PLN-07).

**Scope.**
- `client/worker.py`: a worker thread with a job queue; results delivered to
  Tk through `root.after()` polling; errors delivered as results, never
  raised in the worker.
- Move shift loading and the cross-check onto it; show a "loading…" state;
  ignore stale results if the user opened another folder meanwhile.

**Done when.** Loading a shift from a slow or unreachable network folder does
not freeze the window; unit tests cover the worker without Tk.

**Depends on.** S0-02.

### S0-04 Network modules back in the build · S

**Goal.** Let the `.exe` use HTTPS (PLN-05).

**Scope.** Remove `ssl`, `http`, `socket`, `email`, `urllib` from `excludes` in
`app.spec`; record the `.exe` size before and after.

**Done when.** The build runs on the target; size change noted in the PR.

**Depends on.** S0-01 (confirms which modules are actually needed).

### S0-05 Client settings store · S

**Goal.** A place for per-machine settings: server URL, workstation
registration, standalone flag.

**Scope.** `client/settings.py`: an INI file in `%LOCALAPPDATA%\FinnPowerCounter`
(fallback next to the user profile on other OSes); secrets are not stored here
(they go through DPAPI in S2-02). Absent file = standalone mode.

**Done when.** Settings round-trip in tests; no settings file means the
utility behaves exactly as today.

### S0-06 GUI smoke tests · M

**Goal.** Close the GUI test gap (FND-17) before the GUI starts changing.

**Scope.** Tests that build the operator window under a virtual display
(Xvfb on Linux CI, a real desktop on the Windows runner), load the
`shift_ok` fixture, switch modes, toggle a mark, and check the table content.

**Done when.** The smoke tests run in CI on both runners.

**Depends on.** S0-02.

---

## Stage 1 — Server skeleton

### S1-01 Server package and deployment · M

**Scope.** `server/` with its own `pyproject.toml`; FastAPI app with
`/api/v1/health`; configuration via environment variables (data directory,
listen address); `Dockerfile` and `docker-compose.yml` with a volume for
data; a CI job running server tests on Linux and Windows.

**Done when.** `docker compose up` on a clean Linux VM serves the health
endpoint; the same code starts with `python -m fpc_server` on Windows.

**Depends on.** S0-01 passed.

### S1-02 Database schema v1 and migrations · M

**Scope.** SQLAlchemy Core tables `users`, `workstations`, `auth_sessions`,
`audit`; Alembic migrations; SQLite in WAL mode; database file inside the
configured data directory.

**Done when.** A fresh start creates the schema; migrations run up and down
in tests.

**Depends on.** S1-01.

### S1-03 Users, roles and permissions · M

**Scope.**
- Roles `operator`, `supervisor`, `admin`; a single permission table in
  `services/roles.py`; every route declares the permission it needs.
- Password and PIN hashes with `hashlib.scrypt`, per-user salt, parameters
  stored with the hash.
- First-run setup: a CLI command `fpc-server create-admin` (no web page
  reachable without an admin).
- An **authentication provider interface** with one implementation, `local`,
  so that LDAP (S7-02) plugs in without touching the rest.

**Done when.** Permission checks are covered by tests for every role and
route; hashes verify and reject correctly.

**Depends on.** S1-02.

### S1-04 Web sign-in for supervisor and admin · M

**Scope.** Sign-in page; server-side sessions with an HTTP-only, `Secure`,
`SameSite=Strict` cookie; CSRF protection on forms; lockout after N failed
attempts per user and per address; sign-out.

**Done when.** Tests cover success, wrong password, lockout, expiry, CSRF
rejection.

**Depends on.** S1-03.

### S1-05 Admin pages: users and workstations · M

**Scope.**
- Users: create, change role, block and unblock, set or reset PIN/password.
- Workstations: create, name, block; generate a one-time registration code
  (short-lived, single use).
- Operators per workstation: which operators may sign in where.

**Done when.** All actions work through the web page and are recorded in the
audit log (S1-07).

**Depends on.** S1-04.

### S1-06 TLS with a self-signed certificate · S

**Scope.** On first start, generate a key and a self-signed certificate into
the data directory unless the administrator supplies their own; show the
SHA-256 fingerprint on the admin page; HTTP only redirects to HTTPS or is
disabled.

**Done when.** The server serves HTTPS out of the box; the fingerprint shown
matches the certificate.

**Depends on.** S1-01.

### S1-07 Audit log · S

**Scope.** `audit` table: sign-ins, failed attempts, lockouts, every
administrator action; an admin page to view it with filters.

**Done when.** Each action from S1-04 and S1-05 leaves exactly one audit
entry.

**Depends on.** S1-02.

### S1-08 API contract and version handshake · S

**Scope.** `/api/v1/version` returns the server version and the minimum
supported client version; the OpenAPI description is exported into
`server/openapi.json` and checked in CI (the build fails if it is stale).

**Done when.** A change to any route shows up as a diff in `openapi.json`.

**Depends on.** S1-01.

### S1-09 System settings · M

**Scope.** An admin page and a settings table for everything the
administrator configures:
- shift boundaries (any number of shifts, crossing midnight allowed);
- time format (24-hour or 12-hour) and date format for pages and exports;
- data retention period for production events;
- who may see individual operators' figures (supervisors, admins only, or
  totals only).

**Done when.** Each setting is applied everywhere it matters and covered by
tests; changes are audited (S1-07).

**Depends on.** S1-04.

---

## Stage 2 — The client connects

### S2-01 API client · M

**Scope.** `client/api.py` on `http.client` + `ssl`: certificate pinning by
fingerprint, timeouts, JSON in and out, a small error model (offline, auth
failed, forbidden, too old, server error); version handshake on connect
(S1-08).

**Done when.** Tested against a real test server started in CI; pinning
rejects a different certificate.

**Depends on.** S0-01, S0-04, S1-08.

### S2-02 DPAPI wrapper · S

**Scope.** `client/dpapi.py`: protect and unprotect bytes via ctypes; a
non-Windows fallback for development and tests that is clearly marked as
insecure.

**Done when.** Round-trip tests on the Windows CI runner.

**Depends on.** S0-01.

### S2-03 Workstation registration · M

**Scope.**
- Server: `POST /api/v1/workstations/register` exchanges a one-time code for
  a workstation key.
- Client: a setup window — server address and code; stores the key
  (DPAPI) and the certificate fingerprint (S0-05).

**Done when.** A code works once and expires; a registered workstation shows
up as active on the admin page.

**Depends on.** S1-05, S2-01, S2-02.

### S2-04 Operator sign-in · M

**Scope.**
- Server: list of operators allowed on a workstation; PIN sign-in only with
  a valid workstation key; attempt limit and lockout; a token bound to the
  workstation, expiring at a configured time.
- Client: sign-in window (name from a list, PIN pad usable with gloves);
  signed-in name shown in the operator window; sign-out.

**Done when.** A PIN is rejected from an unregistered workstation; lockout
works; tests on both sides.

**Depends on.** S2-03.

### S2-05 Offline sign-in · M

**Scope.** After an online sign-in the client stores a PIN verifier (scrypt)
under DPAPI; if the server is unreachable, those operators can sign in
locally; the session is flagged "offline" until the server confirms it.

**Done when.** Sign-in works with the server stopped, only for operators who
signed in on this PC before.

**Depends on.** S2-04.

### S2-06 Connection indicator and standalone mode · S

**Scope.** Indicator in the operator window: connected, offline (with the
outbox size from S3-03), standalone. With no server configured, no sign-in
window appears and nothing is sent.

**Done when.** All three states are visible and covered by GUI smoke tests.

**Depends on.** S0-06, S2-04.

---

## Stage 3 — Production log

### S3-01 Task identity · S

**Scope.** A stable ID of a shift task: SHA-256 over sorted `.nc` names and
their contents, in `core/`; independent of the folder path and line endings.

**Done when.** Same files in different folders give the same ID; any content
change gives a different one.

### S3-02 Server: tasks and events · M

**Scope.** Tables `tasks`, `events`; `POST /api/v1/events` accepts a batch,
idempotent by event `id`; the server sets `operator`, `workstation`,
`received_at`; `GET /api/v1/tasks/{id}` returns the current marks (last event
per program in receive order).

**Done when.** Resending a batch changes nothing; an event cannot name
another operator.

**Depends on.** S1-02, S2-04.

### S3-03 Client: marks become events, outbox · M

**Scope.** Each mark or unmark writes an event to a persistent outbox
(DPAPI-protected file); the worker sends batches with back-off; the outbox
survives restarts.

**Done when.** With the server stopped, marks queue up; after it starts they
arrive exactly once.

**Depends on.** S0-03, S3-01, S3-02.

### S3-04 Restore marks on open · S

**Scope.** Opening a task asks the server for its marks and applies them;
offline, the local cache is used and the window says so.

**Done when.** A task marked on one workstation opens with the same marks on
another.

**Depends on.** S3-02, S3-03.

### S3-05 Live event stream · M

**Scope.** Server: `GET /api/v1/stream` (SSE) broadcasts new events to
subscribers, with `Last-Event-ID` resume. Client: a stream reader thread that
updates the open task live and reconnects with back-off.

**Done when.** A mark on one client appears on another within a couple of
seconds; a dropped connection resumes without losing events.

**Depends on.** S3-02, S0-03.

### S3-06 Offline conflicts · S

**Scope.** When events for the same program from different workstations
cross while one side is offline, flag them for the supervisor instead of
silently picking one.

**Done when.** The conflict case is covered by a test and visible via the
API.

**Depends on.** S3-02.

---

## Stage 4 — Supervisor page

### S4-01 Production totals · M

**Scope.** Queries over events: per operator, day, shift, task — sheets,
programs, positions, pieces; only the effective event per program counts.

**Done when.** Totals match a hand-computed fixture.

**Depends on.** S3-02, S4-02.

### S4-02 Shift definition · S

**Scope.** Events are assigned to a shift by `received_at`, using the shift
boundaries configured by the administrator (S1-09).

**Done when.** Night shifts that cross midnight count as one shift; changing
the boundaries recomputes the totals.

**Depends on.** S1-09.

### S4-03 Supervisor page · M

**Scope.** Server-rendered page: filters (dates, operator, task), tables of
totals, drill-down to programs; live updates via `EventSource` on the S3-05
stream.

**Done when.** A mark made on the floor shows up on the page without a
reload.

**Depends on.** S4-01, S3-05, S1-04.

### S4-04 CSV export · S

**Scope.** Export of the current page view; `;` separator, UTF-8 with BOM;
dates and times in the configured format (S1-09); cells starting with `=`,
`+`, `-`, `@` are escaped (FND-11).

**Done when.** The file opens correctly in a Russian-locale Excel; formula
injection is covered by a test.

**Depends on.** S4-03.

---

## Stage 5 — Sessions

### S5-01 Server: bookmarks · S

**Scope.** Table `bookmarks`; API to create, list (own), open; stores name,
author, task ID and path, marks at save time, timestamp.

**Done when.** Users see only their own bookmarks; tests cover it.

**Depends on.** S3-02.

### S5-02 Client: save and open sessions · M

**Scope.** "Save session" dialog: the user types a name, the save date and
time are added (shown as `2026-09-29 14:30 — <name>`); session list; opening
restores the task and shows what changed since saving.

**Done when.** A session saved on one workstation opens on another.

**Depends on.** S5-01, S3-04.

---

## Stage 6 — Operations

### S6-01 Backups · M

**Scope.** Scheduled online backups with SQLite's backup API into a
configured folder, retention policy, a documented restore procedure and a
test that restores a backup.

**Done when.** A restore drill passes in CI.

**Depends on.** S1-02.

### S6-02 Installation guide · S

**Scope.** `docs/SERVER.md`: Docker on Linux, running as a Windows service,
ports, certificate, backups, upgrades. Written for an IT department.

**Depends on.** S1-01, S1-06, S6-01.

### S6-03 Client update notice · S

**Scope.** On connect, if the client is older than the latest release the
server knows of, show a notice with the version; if older than the minimum,
refuse to send data and say why.

**Depends on.** S1-08, S2-01.

### S6-04 Security review before rollout · M

**Scope.** Review of the server and client before the first shop-floor use:
authentication, session handling, permission table, TLS setup, logging of
personal data, dependency audit of the server.

**Done when.** Findings are recorded in FINDINGS.md and blocking ones fixed.

**Depends on.** S1–S5.

### S6-05 Data retention · S

**Scope.** A scheduled job removes or anonymises production events older
than the configured retention period (S1-09); the audit log keeps a record
of each run.

**Depends on.** S1-09, S3-02.

---

## Stage 7 — Directory (Active Directory)

Design in [INTEGRATIONS.md](INTEGRATIONS.md#active-directory).

### S7-01 LDAP settings · S

**Scope.** Admin page for the directory: server, LDAPS or StartTLS, CA
certificate, service account (stored as a secret), base DN, user filter;
**Test connection** button.

**Depends on.** R-03, S1-09.

### S7-02 LDAP authentication provider · M

**Scope.** Supervisor and administrator sign-in with domain credentials via
`ldap3`; a user record is created on first sign-in; local accounts keep
working, at least one local administrator always remains.

**Done when.** Sign-in works against the bench domain (TB-03); wrong
password and disabled domain accounts are rejected.

**Depends on.** S1-03, S7-01.

### S7-03 Group → role mapping · S

**Scope.** Admin table mapping domain groups to roles; roles re-evaluated at
every sign-in; removing a user from the group removes access.

**Depends on.** S7-02.

### S7-04 Link operators to domain accounts · S

**Scope.** Optional link between an operator record and a domain account for
identity and ERP employee mapping; sign-in at the machine stays name + PIN.

**Depends on.** S7-02.

### S7-05 Browser single sign-on · M · optional

**Scope.** Kerberos/SPNEGO sign-in for the web pages on domain-joined PCs.

**Depends on.** S7-02.

---

## Stage 8 — Integration hub

Design in [INTEGRATIONS.md](INTEGRATIONS.md#integration-hub).

### S8-01 Hub core · L

**Scope.** Connector registry (built-ins plus the `fpc_server.connectors`
entry-point group); connection profiles; settings models rendered as admin
forms with validation and **Test connection**; secrets encrypted with the
server master key; enable, disable, delete.

**Done when.** A dummy connector installed as a separate package appears in
the panel, can be configured and tested, and its secrets never appear in
pages, logs or backups in clear text.

**Depends on.** S1-05, S1-07.

### S8-02 Integration outbox and delivery · M

**Scope.** Outgoing messages stored before delivery; routing by event type
and filters; retries with back-off; idempotency keys; dead-letter list and
manual retry; delivery log and a status tile per connection.

**Done when.** With the target down for an hour, messages are delivered
exactly once afterwards (scenario T-10).

**Depends on.** S8-01, S3-02.

### S8-03 Mapping tables · M

**Scope.** Parts → items, tasks → jobs, operators → employees, workstations
→ work centres; editing in the panel, CSV import and export, pre-fill from a
connector's `pull_reference`; an "unmapped" list; messages wait until mapped.

**Depends on.** S8-01.

### S8-04 Integration API · M

**Scope.** Scoped API tokens managed in the panel; event feed by cursor;
reference-data upload (jobs, items); webhook subscriptions; all documented in
the OpenAPI description.

**Done when.** An external script can read every event exactly once by
cursor across restarts.

**Depends on.** S1-08, S3-02.

### S8-05 Webhook connector · S

**Scope.** POST to a configurable URL with an admin-edited payload template
and preview; authentication methods from INTEGRATIONS.md.

**Depends on.** S8-02.

### S8-06 File-drop connector · S

**Scope.** CSV or XML files written to a configured folder, one per batch,
atomically; optional import of reference data from files.

**Depends on.** S8-02, S8-03.

### S8-07 Infor SyteLine connector · L

**Scope.** Pull jobs, routings and items through the IDO REST API; push
completed quantities as job transactions per job operation; on-premises
token and ION API (`.ionapi`) authentication.

**Done when.** Scenario T-09 passes against ERP-MOCK; verified against a real
instance when one is available.

**Depends on.** R-01, S8-02, S8-03, TB-04.

### S8-08 1C OData connector · L

**Scope.** Read catalogs (items, employees) and create production-output
documents through the published OData interface; which document is agreed
per site.

**Depends on.** R-02, S8-02, S8-03.

### S8-09 Connector developer guide · S

**Scope.** `docs/CONNECTORS.md`: the interface, settings models, testing
against the bench, packaging as a plugin; an example connector in the
repository.

**Depends on.** S8-01.

---

## Research

| ID | Size | Question | Output |
|---|---|---|---|
| R-01 | M | Infor SyteLine: confirm IDO names and properties for jobs, routings, items and job transactions; authentication on premises and via ION; which transaction the site would use for punching output | A verified section in INTEGRATIONS.md; the ERP-MOCK contract |
| R-02 | M | 1C: OData publishing, which catalogs and documents carry items, employees and production output in 1C:ERP; how a 1C scheduled job would read our event feed | A verified section in INTEGRATIONS.md |
| R-03 | S | Active Directory: LDAPS requirements, service account rights, group layout, whether operators have domain accounts | A verified section in INTEGRATIONS.md |

---

## Test benches

Layout and scenarios in [TEST_BENCH.md](TEST_BENCH.md).

| ID | Size | Task | Needed by |
|---|---|---|---|
| TB-01 | S | `bench/docker-compose.yml` with profiles per bench configuration; SRV-LIN setup notes | S1 |
| TB-02 | S | Windows VM checklist `bench/windows.md` (WS-W7, WS-W10, SRV-WIN) | S0-01 |
| TB-03 | S | Samba AD DC container with test users and groups | S7 |
| TB-04 | M | ERP-MOCK: IDO REST imitation of jobs, routings, items; records job transactions; built from R-01 | S8-07 |
| TB-05 | S | Toxiproxy between clients and the server, with scripted fault scenarios | S3 |
| TB-06 | S | Samba share with synthetic shift folders from `tools/make_fixtures.py` | S2 |

---

## Maintenance — from the audit

Small, independent; can be done at any time.

| ID | Size | Task | Finding |
|---|---|---|---|
| M-01 | S | Report scrubber: replace names only at word boundaries, never inside `line N` | FND-08 |
| M-02 | S | Keep the table sort when the language is switched | FND-09 |
| M-03 | S | `--done 0` means "shift not started" | FND-10 |
| M-04 | S | Escape formula-like cells in the positions CSV export | FND-11 |
| M-05 | S | Unique report file names (add milliseconds or a counter) | FND-12 |
| M-06 | S | Table row IDs by position, not by program name | FND-13 |
| M-07 | S | Pin GitHub Actions by commit SHA | FND-14 |
| M-08 | S | Private report folder on Linux (`mkdtemp`-style permissions) | FND-15 |
| M-09 | S | Decide on `ProgramNest.number`: remove it or give it a use | FND-16 |
| M-10 | S | Check the `Claude Code Review` job log and its secret | FND-18 |
| M-11 | L | Translate code comments and docstrings to English, module by module, alongside other changes | PLN-11 |

---

## Machine-data stages A–F

Broken down further when the tracking system reaches stage 4. Details and
reasoning in [ROADMAP.md](ROADMAP.md#more-data-from-the-machine-files).

| ID | Size | Task |
|---|---|---|
| DA-01 | S | Material and thickness: parse, show a column in the programs view, filter |
| DA-02 | S | Sheet consumption: done and remaining sheets |
| DA-03 | S | Part dimensions in the position window |
| DB-01 | M | Fixture generator: time per sheet, materials, thicknesses, weights, forming flag |
| DC-01 | M | Time estimate per program and to the end of the task |
| DC-02 | S | "What will close this position": programs and time left |
| DD-01 | M | Weight per position and per program, route-sheet export |
| DE-01 | S | Forming and bending, order and customer — shown only when filled |
| DF-01 | L | Research on site: executed programs from the machine control's queue and logs |

---

## Open questions

| ID | Question | Status |
|---|---|---|
| Q-01 | Where does the server run? | **Resolved for development:** a local VM (TEST_BENCH.md). Deployment stays site-specific; S6-02 documents Linux and Windows |
| Q-02 | Shift boundaries | **Resolved:** configured by the administrator, including the time format (S1-09) |
| Q-03 | Operators and workstations | **Resolved:** configured by the administrator (S1-05) |
| Q-04 | Retention and visibility of production data | **Resolved:** configured by the administrator (S1-09, S6-05); directory integration likely (stage 7) |
| Q-05 | Personal data and local law | **Resolved:** the project is open source and not tied to a particular shop. It provides retention and visibility settings; compliance is the responsibility of whoever deploys it, as stated in the documentation |
| Q-06 | PIN length and lockout policy | Open — default proposed in S2-04, configurable in S1-09 |
| Q-07 | Access to a real SyteLine instance for verification | Open — until then, ERP-MOCK (TB-04) |
| Q-08 | Which ERPs besides SyteLine and 1C are worth a built-in connector | Open |
