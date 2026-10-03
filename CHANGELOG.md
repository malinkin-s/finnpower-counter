# Changelog

Versions follow [Semantic Versioning](https://semver.org/). Releases are
tagged `vX.Y.Z`; install a release with

```bash
pip install "git+https://github.com/malinkin-s/finnpower-counter@vX.Y.Z"
```

## 0.2.0 — unreleased

The first tagged release.

### Added
- Installable package (`pyproject.toml`) with `finnpower-counter` and
  `finnpower-counter-gui` commands. The parser (`finnpower_counter.core`) and
  the view helpers (`finnpower_counter.presentation`) import without Tk, so
  other projects — [Nestrack](https://github.com/malinkin-s/nestrack) — can
  depend on them.
- A test that keeps `core` and `presentation` free of GUI and network
  imports.
- CI on Windows with Python 3.8 x86 and on Linux with a current Python,
  including installing the built package.

### Fixed
- Crash reports: Windows paths with spaces and program names in file names
  are now fully anonymised (#2).
- One unreadable `.nc` file no longer prevents the whole shift from opening;
  an unreadable setup report is skipped in the cross-check (#2).
- Marks from the previous shift no longer carry over if the cross-check
  fails while a new shift is loading (#2).
- Typing `²` into the program search or the done field no longer crashes
  (#2).

## 0.1.0

Initial version, used on the shop floor before releases were tagged.
