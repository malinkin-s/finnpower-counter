# Tasks

Planned work on finnpower-counter, broken down from [ROADMAP.md](ROADMAP.md);
the audit behind the maintenance items is in [FINDINGS.md](FINDINGS.md).

Status of every task: **not started**, unless marked otherwise.

The production tracking system that grew out of this utility —
client–server, supervisor page, ERP integration — is a separate project,
[Nestrack](https://github.com/malinkin-s/nestrack), with its own tasks.

## Conventions

- **ID** — `U-<nn>` for the utility, `P-<nn>` for packaging work Nestrack
  depends on, `M-<nn>` for maintenance items from the audit,
  `D<stage>-<nn>` for machine-data stages A–F.
- **Size** — rough effort: **S** up to a day, **M** two to four days,
  **L** one to two weeks.
- **Done when** — acceptance criteria. A task is not done until they hold and
  the tests for it are in CI.
- One task, one pull request where practical.
- New code, comments, commit messages and documents are in English.

---

## Utility

### U-01 Split `gui.py` into a `ui/` package · M

**Goal.** `gui.py` is a single ~790-line module mixing layout and behaviour;
split it before it grows further.

**Scope.** `ui/app.py` (start-up, crash hook), `ui/operator.py` (main
window), `ui/part_window.py`, `ui/widgets.py` (shared helpers). No behaviour
change. `app.py` and `app.spec` updated.

**Done when.** The application looks and behaves exactly as before; all tests
pass; the PyInstaller build runs.

**Depends on.** U-03 (tests first, so the split is checked).

### U-02 Load shifts in the background · M

**Goal.** Opening a shift folder on a slow or unreachable network share must
not freeze the window: Tk may only be used from the main thread.

**Scope.** A worker thread with a job queue; results delivered to Tk through
`root.after()` polling; shift loading and the cross-check run on it; a
"loading…" state; stale results ignored if another folder was opened
meanwhile.

**Done when.** Loading from an unreachable share leaves the window
responsive; the worker is unit-tested without Tk.

**Depends on.** U-01.

### U-03 GUI smoke tests · M

**Goal.** Close the GUI test gap (FND-17).

**Scope.** Tests that build the main window under a virtual display (Xvfb on
Linux CI, a real desktop on the Windows runner), load the `shift_ok` fixture,
switch modes, toggle a mark, and check the table content.

**Done when.** The smoke tests run in CI on both runners.

---

## Packaging for Nestrack

[Nestrack](https://github.com/malinkin-s/nestrack) reuses this parser instead of copying it (its tasks X-01,
X-02).

### P-01 Installable package with tagged releases · S

**Scope.** `pyproject.toml`; the package installs without the GUI being a
required import; releases tagged `vX.Y.Z` with a changelog; installing from a
tag documented in the README.

**Done when.** `pip install git+https://github.com/malinkin-s/finnpower-counter@vX.Y.Z`
works on Python 3.8 and a current Python; `finnpower_counter.core` imports
without Tk.

### P-02 Keep the core free of GUI and network imports · S

**Scope.** A CI check that `finnpower_counter.core` and
`finnpower_counter.presentation` import nothing from `tkinter`, `socket`,
`http` or `ssl`.

**Done when.** The check fails the build on a violation.

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
| M-11 | L | Translate code comments and docstrings to English, module by module, alongside other changes | English-first repository |

---

## Machine-data stages A–F

Details and reasoning in [ROADMAP.md](ROADMAP.md). Parser changes here also
reach [Nestrack](https://github.com/malinkin-s/nestrack), which depends on this parser.

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
