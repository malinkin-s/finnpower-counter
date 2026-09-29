# Findings

Results of the code audit and of the planning work that shaped
[ROADMAP.md](ROADMAP.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Each open
item links to the task that addresses it in [TASKS.md](TASKS.md).

---

## Audit — 2026-09-28

Security review, code review and a dead-code pass over the whole code base.
At the time: 218 tests passing, 6 skipped (they need the private dataset).

### Fixed

Fixed in [#2](https://github.com/malinkin-s/finnpower-counter/pull/2).

| ID | Severity | Finding | Where |
|---|---|---|---|
| FND-01 | High | Windows paths in crash reports were cut at the first space, leaking the rest of the path — including user names such as `Ivan Petrov\Desktop\...` — into a report meant for public issues | `report.py` |
| FND-02 | Medium | A crash before a shift was loaded (always the case for CLI crashes) left real program numbers in file names inside the report | `report.py` |
| FND-03 | Medium | If the cross-check failed while loading a new shift, the previous shift's marks were applied to the new one | `gui.py` |
| FND-04 | Medium | One unreadable `.nc` file prevented the whole shift from opening | `core/nc_parser.py` |
| FND-05 | Low | Typing `²` into the program search or the done field crashed (`isdigit` accepts it, `int()` does not) | `presentation.py`, `core/balance.py` |
| FND-06 | — | Dead code: `FONT_BIG`, `var_lang`, `status_at`, a redundant check in `_save_report`; duplicated `dimension()` helpers | `gui.py`, `core/` |
| FND-07 | — | Tests were not run in CI at all | `.github/workflows/` |

### Open

| ID | Severity | Finding | Where | Task |
|---|---|---|---|---|
| FND-08 | Low | The report scrubber replaces names as plain substrings: a short part name such as `1` or `10` also rewrites line numbers in the traceback. No leak, but the report becomes hard to read | `report.py` `Scrubber.text` | M-01 |
| FND-09 | Low | Switching the interface language resets the table sort | `gui.py` `_retranslate` → `_change_mode` | M-02 |
| FND-10 | Low | `--done 0` answers "matches several programs" instead of "shift not started" | `core/balance.py` `resolve_position` | M-03 |
| FND-11 | Low | CSV export writes part names as they are: a name starting with `=`, `+`, `-` or `@` is executed by Excel as a formula. Names come from CAM, so the risk is low | `presentation.py` `to_csv` | M-04, S4-04 |
| FND-12 | Low | Two reports saved within the same second overwrite each other | `report.py` `save` | M-05 |
| FND-13 | Low | On Linux, `PRG_1.nc` and `PRG_1.NC` in one folder produce the same table row ID and crash the table | `gui.py` `_refresh_table` | M-06 |
| FND-14 | Low | GitHub Actions are pinned by tag (`@v4`, `@v1`), not by commit SHA | `.github/workflows/` | M-07 |
| FND-15 | Low | On Linux the fallback report folder in `/tmp` has a predictable name. Irrelevant on the Windows target | `report.py` `reports_dir` | M-08 |
| FND-16 | — | `ProgramNest.number` and `reader.program_number` are computed but no logic or view uses them any more | `core/model.py`, `core/reader.py` | M-09 |
| FND-17 | — | The GUI has no tests; `gui.py` changes are only checked by compiling | `gui.py` | S0-06 |
| FND-18 | — | The `Claude Code Review` job finished in under a minute on #2 without a single comment. It may have found nothing, or it may not run properly (e.g. the `CLAUDE_CODE_OAUTH_TOKEN` secret). Needs a look at the job log | `.github/workflows/claude-code-review.yml` | M-10 |

---

## Planning — 2026-09-29

Facts found while planning the tracking system. Each one changed or
constrained a decision.

| ID | Finding | Consequence |
|---|---|---|
| PLN-01 | SQLite's own documentation warns that file locking on network file systems is unreliable and concurrent writes from several machines can corrupt the database | No shared database file on a network drive. Led first to a log-of-files design, then to a server |
| PLN-02 | The Python standard library has no symmetric cipher. Current `cryptography` releases are built with Rust, and current Rust toolchains no longer target Windows 7; older releases that would run are unmaintained | Application-level encryption on the client is expensive. With a server, TLS from the standard library covers data in transit |
| PLN-03 | Python 3.8 bundles its own OpenSSL, so TLS does not depend on Windows 7's own TLS stack | The client can speak modern TLS on Windows 7 — to be confirmed on a real machine (S0-01) |
| PLN-04 | Python 3.8 has been end-of-life since October 2024, and the OpenSSL it bundles is end-of-life too. The client is pinned to it by Windows 7 | Keep the client's network surface minimal: it talks only to its own server, pinned by certificate fingerprint. The server is not bound by this and uses a current Python |
| PLN-05 | `app.spec` excludes `ssl`, `http`, `socket`, `email` and `urllib` — the utility was built to be fully offline | They must come back into the build (S0-04); the `.exe` grows |
| PLN-06 | WebSocket is not in the standard library; Server-Sent Events are plain HTTP and can be read with `http.client` | Live updates use SSE |
| PLN-07 | Tk may only be used from the main thread | A background executor is required before any network I/O (S0-03) |
| PLN-08 | `gui.py` is a single ~790-line module that mixes layout and behaviour | Split it before adding sign-in, setup and other windows (S0-02) |
| PLN-09 | The previous roadmap stated that the utility "keeps no history and should not" | Reversed on purpose: history is kept on the server. Program files remain read-only |
| PLN-10 | Recording each operator's output is processing of personal data and may fall under labour and data-protection law | The project is open source and not tied to a shop: it provides retention and visibility settings (S1-09, S6-05), and compliance is the deployer's responsibility, stated in the documentation |
| PLN-11 | Code comments, docstrings and commit history are in Russian; the repository is now English-first | New code and documents in English; existing comments translated gradually (M-11) |
| PLN-12 | Infor SyteLine exposes a documented IDO REST API (load, update, invoke per IDO) and ION BODs, but has no public sandbox; cloud access goes through the ION API Gateway | The SyteLine connector is built against a mock (TB-04) and verified on a real instance later (R-01, Q-07) |
| PLN-13 | 1C:Enterprise can publish a standard OData v3 interface per infobase; 1C teams also commonly pull from external HTTP APIs with their own scheduled jobs | The integration hub supports both: an OData connector and a generic event feed (S8-04, S8-08) |
| PLN-14 | NC files carry no order or job number (`CUSTOMER` and `Order ID` are empty in the files analysed) | ERP integration needs mapping tables maintained by the administrator (S8-03) |
