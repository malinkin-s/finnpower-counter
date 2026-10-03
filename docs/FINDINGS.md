# Findings

Results of the code audit of finnpower-counter. Each open item links to the
task that addresses it in [TASKS.md](TASKS.md).

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
| FND-11 | Low | CSV export writes part names as they are: a name starting with `=`, `+`, `-` or `@` is executed by Excel as a formula. Names come from CAM, so the risk is low | `presentation.py` `to_csv` | M-04 |
| FND-12 | Low | Two reports saved within the same second overwrite each other | `report.py` `save` | M-05 |
| FND-13 | Low | On Linux, `PRG_1.nc` and `PRG_1.NC` in one folder produce the same table row ID and crash the table | `gui.py` `_refresh_table` | M-06 |
| FND-14 | Low | GitHub Actions are pinned by tag (`@v4`, `@v1`), not by commit SHA | `.github/workflows/` | M-07 |
| FND-15 | Low | On Linux the fallback report folder in `/tmp` has a predictable name. Irrelevant on the Windows target | `report.py` `reports_dir` | M-08 |
| FND-16 | — | `ProgramNest.number` and `reader.program_number` are computed but no logic or view uses them any more | `core/model.py`, `core/reader.py` | M-09 |
| FND-17 | — | The GUI has no tests; `gui.py` changes are only checked by compiling | `gui.py` | U-03 |
| FND-18 | — | The `Claude Code Review` job finished in under a minute on #2 without a single comment. It may have found nothing, or it may not run properly (e.g. the `CLAUDE_CODE_OAUTH_TOKEN` secret). Needs a look at the job log | `.github/workflows/claude-code-review.yml` | M-10 |

---

## Planning — 2026-09-29

Planning findings for the production tracking system moved with it to
[Nestrack's FINDINGS.md](https://github.com/malinkin-s/nestrack/blob/main/docs/FINDINGS.md).
