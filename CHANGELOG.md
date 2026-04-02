# Changelog

All notable changes to agentlint are documented here.

## [Unreleased] — pre-release additions (2026-04-02)

### Added
- **Windsurf adapter** — detects and lints `.windsurfrules` (DISPATCH) and
  `.windsurf/rules/*.md` (SKILL) files. `--adapter windsurf` and auto-detection both
  supported. (`agentlint/adapters/windsurf.py`)
- **`--format sarif`** — emits SARIF 2.1.0 JSON for direct ingestion by GitHub Code
  Scanning and other SAST platforms. (`agentlint/report.py`, `agentlint/cli.py`)
- **AL-F01 fuzzy suggestions** — when a referenced file path is not found on disk, the
  fix hint now checks for similarly-named files using `difflib.get_close_matches` and
  suggests the closest match (e.g. `Did you mean 'src/utils/validator.ts'?`).
  (`agentlint/checks/file_references.py`)
- 10 new tests covering all three features above (`tests/test_cli.py`,
  `tests/test_file_references.py`). Test count: 51 → 67 → 77.

### Fixed
- **UnicodeEncodeError on Windows** — `✖` and `⚠` characters in the text output caused a
  crash on Windows terminals using cp1252 encoding. Fixed with `io.TextIOWrapper` fallback
  in `cli.py`.
- **Raw traceback on invalid `.agentlint.yml`** — a malformed config file produced a full
  Python stack trace instead of a friendly error message. Fixed with `try/except
  yaml.YAMLError` in `config.py`.

### Changed
- PyPI distribution name changed from `agentlint` to `agentlint-cli` (the name `agentlint`
  was already registered on PyPI by an unrelated package). Python module name, CLI binary,
  and import paths are unchanged.
- `action.yml` adapter description updated to include `windsurf`.
- `action.yml` format description updated to include `sarif`.
- `.pre-commit-hooks.yaml` description updated to mention Windsurf.

---

## [0.1.0-rc] — pre-release fixes (found during internal audit, 2026-04-01)

### Fixed
- **BUG-01** `--adapter cursor` (or any explicit adapter) on a repo that does not match that
  adapter's `detect()` heuristics now exits with code 2 instead of silently scanning 0 files
  and exiting 0. (`agentlint/cli.py`)
- **BUG-02** AL-F01 no longer fires on file-path strings that appear inside fenced code
  blocks (` ``` … ``` `). (`agentlint/checks/file_references.py`)
- **BUG-04** `templates/SKILL_HEALTH_CHECK.md` is now bundled inside the `agentlint/`
  package directory so `--init` works after `pip install`. (`agentlint/__init__.py`)
- **BUG-05** Removed dead `_CHECK_REGISTRY` list and the misleading
  `skill-dispatch-coverage` toggle key from `Config.checks`. (`agentlint/config.py`)
- **BUG-06** `--config /path/to/custom.yml` now loads the specified file directly via
  `Config._from_file()`. (`agentlint/cli.py`, `agentlint/config.py`)
- **action.yml / CLI mismatch** Added `--fail-on-warnings` as an explicit CLI flag.

### Changed
- README CLI reference block updated to match current `--help` output.
- README grade table rewritten with accurate descriptions from the scoring formula.

### Added
- `LICENSE` file (MIT).
- `tests/test_file_references.py` — 11 tests for AL-F01.
- `tests/test_cli.py` — 13 integration tests covering all exit codes and flags.
- `tests/test_report.py` — 25 tests for `format_text()`, `format_json()`, and `grade()`.

---

## [0.1.0] — 2026-04-01

### Added
- **AL-D01** Detect skill paths in dispatch table that don't exist on disk.
- **AL-D02** Detect skill files on disk that are missing from the dispatch table.
- **AL-F01** Detect source-file references in skill files that don't exist on disk.
- **AL-N01** Detect threshold/percentage numbers in skill files without a source pointer,
  with look-back awareness for table rows and blockquotes.
- **AL-T01** Detect overlapping trigger descriptions between skills using Jaccard similarity.
- **AL-P01** (built-in default) Detect hardcoded test counts.
- Configurable forbidden patterns via `.agentlint.yml`.
- **GitHub Copilot adapter** — parses `copilot-instructions.md` + `.github/skills/**/SKILL.md`.
- **Cursor adapter** — parses `.cursorrules` + `.cursor/rules/*.mdc`.
- Auto-detection: both adapters can be active simultaneously.
- `--format json` for CI dashboards and PR annotations.
- A–F health grade based on violation density.
- `--init` flag copies `SKILL_HEALTH_CHECK.md` behavioral test template.
- Pre-commit hook support (`.pre-commit-hooks.yaml`).
- GitHub Action wrapper (`action.yml`).
