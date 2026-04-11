# Changelog

All notable changes to agentlint are documented here.

## [0.6.0] — 2026-04-10

### Added
- **UX-01 `--fix` auto-fix flag** — applies deterministic fixes directly to instruction
  files without a separate editing step. Violations with a known replacement are marked
  `auto_fixable=True` and carry `fix_data = {"old_line", "new_line"}`. Three check
  families now emit auto-fixable violations: `AL-DEP*` (when `replacement:` is
  supplied in config), `AL-P*` (when `replacement:` is supplied in the forbidden-pattern
  entry), and `AL-S01` (always — matched secret text is replaced with `<REDACTED>`).
  The fixer preserves original line endings (`\n` / `\r\n`), handles multi-file
  batches, skips stale fixes (on-disk line changed since scan), and skips duplicate
  line-number collisions (first fix wins). `agentlint/fixer.py` is the new
  standalone fix engine imported lazily only when `--fix` is passed. 21 new tests.
- **CHECK-11 AL-D02 VS Code auto-discovery suppression** — skills under `.github/skills/`
  are automatically discovered by VS Code 1.99+ via XML `<skill>` injection and no longer
  trigger AL-D02 ("skill not referenced in dispatch"). Skills under `.github/instructions/`
  and other non-auto-discovered paths are unaffected. 4 new dispatch coverage tests updated.
- **CHECK-02 AL-DEP* deprecated pattern check** — `deprecated_patterns:` config list lets
  projects flag known-deprecated AI provider models, SDK methods, or API endpoints.
  Each entry supplies `pattern` (regex), `reason`, `replacement` (optional), `severity`
  (optional, default `warning`), and `id` (optional, default `AL-DEP<n>`). Runs on SKILL,
  DISPATCH, and DOCS files. Zero built-in patterns — entirely user-supplied. 12 new tests.
- **AL-V01 AST-based value extraction** — `_extract_constant_value_ast()` now
  uses Python's `ast` module for `.py` source files, correctly scoping constant
  lookups to the named class (`ClassName.ATTR`) or module level. Handles
  type-annotated assignments (`x: int = 42`), negative literals (`X = -1`),
  and deeply nested classes (`Outer.Inner.ATTR`). Falls back to regex when the
  AST cannot resolve the constant (syntax errors, non-numeric values) so no
  previously-passing file regresses. Non-Python source files continue to use
  the regex extractor.
- **AL-V01 negative number support** — `_NUMBER_RE` updated to `(?<!\w)(-?\d+…)`
  so negative values in docs (e.g. `-1`) are correctly extracted and compared
  against the source constant. 15 new tests.
- **AL-FRESH01 `freshness` check** — warns when instruction files contain dates older
  than a configurable threshold. Supports ISO-8601 (`2024-01-15`), slash-separated
  (`2024/01/15`), long named-month (`January 15, 2024`), short named-month
  (`Jan 15, 2024`), and day-first formats (`15 January 2024`). Future dates are never
  flagged. Lines inside fenced code blocks are skipped. Suppressible per-line with
  ``# agentlint: disable=AL-FRESH01``. Runs on SKILL, DISPATCH, and DOCS files.
  Disabled by default (`stale_days: 0`). 20 new tests.
- **`stale_days` config field** — integer threshold in days for AL-FRESH01 (default 0).
- **AL-CONF01 `semantic_conflict` check** — warns when two instruction files contain
  contradictory directives about the same subject (e.g. one says "always use tabs",
  another says "never use tabs"). Uses polarity word extraction (always/never, use/avoid,
  must/must not, prefer/don't, etc.) + token-prefix matching so "tabs" matches "tabs for
  indentation". Cross-file only — same-file contradictions are intentionally skipped.
  Suppressible per-line with ``# agentlint: disable=AL-CONF01``. Zero-config. 29 tests.
- **AL-DUP01 `duplicate_content` check** — warns when two instruction files of the same
  role (SKILL–SKILL or DISPATCH–DISPATCH) share ≥ 85 % Jaccard similarity on character
  3-grams. Threshold controlled by `duplicate_threshold` in `.agentlint.yml` (default
  0.85). Set to 0 to disable. Zero-config by default. 25 new tests.
- **`duplicate_threshold` config field** — float 0.0–1.0, default 0.85, powers AL-DUP01.
- **AL-D05 `dispatch_coverage` extension** — errors when two or more SKILL files share
  the same effective name (`name` frontmatter or parent directory name). Fires even
  when no dispatch file is present. Zero-config.
- **AL-LEN01 `min_content` check** — warns when a SKILL file's estimated token count
  falls below `min_content_tokens` (default 10). Catches accidentally empty stub files.
  Set `min_content_tokens: 0` to disable. Config-driven.
- **AL-ENC01 `encoding_check` check** — errors when any instruction or docs file
  contains non-UTF-8 bytes. Reports approximate line number from byte offset.
  Zero-config — runs on SKILL, DISPATCH, and DOCS files.
- **AL-FM01 `frontmatter_schema` check** — warns when a SKILL file is missing one or
  more keys listed in `required_frontmatter` in `.agentlint.yml`. Disabled by default
  (empty list). Config-driven.
- **`min_content_tokens` config field** — integer threshold for AL-LEN01 (default 10).
- **`required_frontmatter` config field** — list of required YAML frontmatter keys
  for SKILL files. Powers AL-FM01.
- **CopilotAdapter: `.github/instructions/*.md` support** — VS Code 1.99+ per-file
  instruction format. Files are collected as SKILL role.
- **ClaudeCodeAdapter: nested `CLAUDE.md` collection** — `<subdir>/CLAUDE.md` files
  anywhere under the project root are collected as SKILL role.
- **GeminiAdapter: nested `GEMINI.md` collection** — `<subdir>/GEMINI.md` files
  anywhere under the project root are collected as SKILL role.
- **Adapter unit tests** — `tests/test_cursor.py`, `tests/test_windsurf.py`,
  `tests/test_aider.py`, `tests/test_continue.py` (10 tests each), and
  `tests/test_copilot.py` (10 tests). All five previously untested adapters now have
  isolated unit test coverage.
- **`action.yml` version pinning** — new `version` input (default `"0.6.0"`) lets CI
  consumers pin `instruction-lint` to a specific release for reproducibility.
- **`action.yml` config input** — new optional `config` input passes `--config <path>`
  to the CLI when set.
- 173 new tests. Test count: 361 → 534.
- 24 additional regression tests covering all bug-fix scenarios. Test count: 534 → 572.

### Fixed
- **`.pre-commit-hooks.yaml` file-type filter** — `types: [markdown]` changed to
  `types_or: [markdown, yaml]` so the hook also fires on YAML instruction files
  (e.g. `.aider.conf.yml`).

### Improved
- **`checks/_utils.py`** — shared `_CODE_FENCE_RE` regex extracted from five
  duplicate definitions across `file_references`, `dead_anchors`, `vague_instructions`,
  `value_extraction`, and `number_sourcing`.
- **`forbidden_patterns.py`** — all patterns are now compiled once before the file
  loop instead of once per file per pattern.
- **`number_sourcing.py`** — `_sourced()` helper is now defined once per file
  (above the line iteration loop) instead of being redefined on every line.
- **`cli.py` error message** — "no adapter detected" message now lists Claude Code
  and Gemini paths alongside the existing adapters.
- **`cli.py` severity override** — two identical inline severity-override loops
  extracted into a single `_apply_severity_overrides()` helper.
- **`models.py` adapter comment** — stale literal corrected to list all seven adapters.

## [0.5.0] — 2026-04-08

### Added
- **AL-D03 `circular_refs` check** — detects circular reference cycles between
  instruction files (DISPATCH and SKILL roles) by building a directed backtick-path
  graph and running DFS cycle detection. A cycle such as DISPATCH → SKILL-A →
  DISPATCH is reported as an error on the entry file. Fires at ERROR severity.
  Zero-config — runs automatically on every scan.
- **AL-D04 `role_coverage` check** — verifies that every role declared in
  `required_roles` config has at least one SKILL file whose `name` frontmatter
  or parent directory name matches. Fires at ERROR severity. Config-driven via
  `required_roles: [role-a, role-b]` in `.agentlint.yml`.
- **`required_roles` config field** — list of role names that must have SKILL
  file coverage. Powers the new AL-D04 check.
- **`--baseline PATH` flag** — suppress violations already recorded in a baseline
  JSON file. Suppression count is reported to stderr. Pairs with `--update-baseline`
  to snapshot the current set of violations and exit 0.
- **`--update-baseline PATH` flag** — snapshot current violations to a JSON baseline
  file and exit 0. Replaces any existing baseline at that path.
- **`--format html` output** — `agentlint --format html` produces a self-contained
  `agentlint-report.html` page with grade badge, summary stats, per-file violation
  groups, severity filter buttons, and automatic dark mode via `prefers-color-scheme`.
- **`agentlint --init` config wizard** — after installing the SKILL_HEALTH_CHECK.md
  template, probes `src/`, `app/`, `docs/`, and `README.md` to generate a tailored
  `.agentlint.yml`. Never overwrites an existing config file.
- 42 new tests. Test count: 262 → 304.

### Fixed
- **AL-INV01 false positives on conditional-availability lines** — negation matching is now
  positional: a `_NEG_BEFORE_RE` hit only counts when the negation phrase ends *before*
  the backtick path starts; a `_NEG_AFTER_RE` hit only counts when it starts *after* the
  path ends. Eliminates false positives on lines like
  `"If the tool is not available, use \`scripts/test.sh\`"`. 2 regression tests added.
- **AL-F02 double-hyphen anchor slugs** — `_to_slug()` now replaces each whitespace
  character individually (`[\s_]` → `-`) rather than collapsing runs (`[\s_]+` → `-`).
  Headings like `## Testing & Validation` now correctly produce `#testing--validation`
  (matching GitHub's anchor algorithm), eliminating false positives on `&`-containing
  headings. 1 regression test added.
- 3 regression tests added. Test count: 304 → 307.
- **AL-Q01 false positives on qualified concise phrases** — `\bbe\s+concise\b`
  narrowed to `\bbe\s+concise(?!\s*,|\s+but\b)` so phrases like
  `"be concise but descriptive"` and `"be concise, keyword-rich"` no longer fire
  when a same-line qualifier follows. Standalone `"Be concise."` still fires.
  Confirmed by stress test against `anthropics/claude-cookbooks` and
  `continuedev/continue`. 3 regression tests added. Test count: 307 → 310.

### Documented
- **SARIF → GitHub inline PR annotations** — README documents three integration
  patterns: (A) GitHub Code Scanning SARIF upload with `permissions: security-events: write`,
  (B) lightweight JSON → `::error/warning` workflow-command script (no GHAS required),
  (C) reviewdog SARIF adapter. Baseline suppression CI recipe also documented.
- **CLI reference updated** — `--format html`, `--baseline PATH`, `--update-baseline PATH`
  flags and updated `--init` description added to README.

## [0.4.0] — 2026-04-07

> **Note:** v0.4.0 was an intermediate development version. It was not released to PyPI — all features listed below shipped as part of the v0.5.0 PyPI release.

### Added
- **Claude Code adapter** — detects and lints `CLAUDE.md` (DISPATCH), `.claude/agents/*.md`
  (SKILL), and `.claude/commands/*.md` (SKILL). Claude Code is now the sixth supported
  assistant alongside GitHub Copilot, Cursor, Windsurf, Aider, and Continue.dev.
- **Gemini CLI adapter** — detects and lints `GEMINI.md` (DISPATCH) and
  `.gemini/rules/*.md` (SKILL). Gemini CLI is now the seventh supported assistant.
- **AL-S01 `secret_detection` check** — flags lines in instruction files and extra-path
  docs that appear to contain real credentials: AWS access keys, GitHub tokens (classic
  and fine-grained PAT), OpenAI keys (standard and project-scoped), Anthropic keys, JWTs,
  PEM private key blocks, and high-entropy hex assignments. Fires at WARNING severity;
  suppresses common placeholder strings (`your-…`, `example`, `<TOKEN>`, etc.).
  Zero-config — runs automatically on every scan.
- **AL-INV01 `inverse_claims` check** — flags documentation lines that make a
  negative existence claim about a path ("there is no `X`", "does not have `X`",
  "`X` is not implemented") while the backtick-referenced path actually exists on disk.
  Fires at WARNING severity. Zero-config. Source: EU Compliance Pipeline feedback-v3 §4.
- **AL-F02 `dead_anchors` check** — flags `[text](#section)` links where the target
  anchor does not correspond to any heading in the same file. Uses GitHub-style anchor
  slug generation. Fires at WARNING severity. Zero-config — runs on SKILL, DISPATCH,
  and DOCS files.
- **AL-N02 `number_sourcing` extension** — extends AL-N01 to also detect written-out
  percentage claims (`"40 percent"`, `"30 per cent"`) without a source pointer.
  Same lookback and source-marker logic as AL-N01. Zero-config.
- **AL-Q01 `vague_instructions` check** — flags structurally vague phrases that give
  the AI agent no actionable criterion: "write clean code", "follow best practices",
  "be helpful", "make sure it works", "use common sense", and 30+ similar patterns.
  Fires at WARNING severity. Suppressible with inline `# agentlint: disable=AL-Q01`.
  Zero-config — runs on SKILL and DISPATCH files.
- **AL-TOK01 `token_budget` check** — warns when an instruction file's estimated
  token count (approximated as `len(content) / 4`) exceeds the configured budget.
  Opt-in via `token_budget: N` in `.agentlint.yml`. Runs on SKILL and DISPATCH files.
- **`agentlint` PyPI alias package** (`agentlint-alias/`) — a stub wheel named `agentlint`
  that declares `instruction-lint>=0.4.0` as its sole dependency. Allows users to
  `pip install agentlint` and get the correct package.
- **UX-06: `ignore_paths` reason field** — each `ignore_paths` entry now optionally accepts
  a dict with `path:` and `reason:` keys (`{ path: "archive/", reason: "generated" }`).
  Plain string entries continue to work. The `reason` value is for self-documentation only.
- **`tree_diagram_fenced: true` config flag (CHECK-07)** — extends `tree_diagram_paths`
  to also scan ASCII tree diagrams (` ├── ` / ` └── ` lines) inside ` ``` ` code fences.
  Disabled by default; requires `tree_diagram_paths: true` to have any effect.
  File-path references (`app/…`, `src/…`) inside fences remain unscanned.
- 104 new tests (+55 this session: Gemini: 8, AL-N02: 7, AL-F02: 15, AL-Q01: 15,
  AL-TOK01: 11, inverse claims: 12). Test count: 158 → 262.

### Documented
- **AL-E01 format:** README now explicitly states that AL-E01 parses both `KEY=value`
  and `export KEY=value` (bash-style) formats, and that `# comment` lines are ignored.
- **`tree_diagram_paths` / `tree_diagram_fenced` flags:** README config example now
  documents both flags with inline notes explaining the fence-scanning behaviour.
- **AL-V01 regex ceiling:** README now documents that AL-V01 uses regex extraction,
  not AST. Computed expressions, class properties, and runtime-only values will not
  be resolved; only simple scalar assignments are reliably extracted.

## [0.3.0] — 2026-04-04

### Added
- **AL-V01 `value_extraction` check** — validates that documented numeric values match
  their referenced source constants. When a source annotation includes a constant path
  (e.g. `(Source: agents/notification_agent.py:NotificationConfig.minimum_risk_score)`),
  agentlint resolves the file, extracts the constant's current value via regex, and
  reports a mismatch as an error. Source-only annotations without a constant path
  (e.g. `(Source: constants.py)`) are unchanged — AL-N01 continues to handle those.
  Runs on instruction files and `extra_paths` documentation files.
- **AL-G01 `ground_truth_files` check** — verifies documentation values against
  authoritative JSON or YAML files (no subprocess execution). Supports two modes:
  `value_match` (extract scalar, validate against doc pattern) and `no_stale_refs`
  (extract list of valid IDs, flag references outside the list via `ref_pattern`).
  Configured via `ground_truth_files` rules in `.agentlint.yml`.
- **AL-F01 `tree_diagram_paths`** — opt-in config flag (`tree_diagram_paths: true`)
  that enables detection of missing filenames inside ASCII tree diagrams
  (`├──` / `└──` prefixed lines). Fuzzy suggestions are included when available.
- **JSON output `scanned_files`** — `--format json` now includes a `scanned_files`
  list alongside the existing `files_scanned` count, making CI audit logs actionable.
- 34 new tests (value extraction: 14, ground truth: 15, coverage: 5). Test count: 121 → 155.

### Fixed
- `Severity()` crash on malformed `severity` values in `forbidden_patterns`, `config_parity`,
  and `consistency_groups` config rules — now falls back to `ERROR` instead of raising
  `ValueError`. Three regression tests added (test count: 155 → 158).
- Removed dead `instruction_dirs` and `dispatch_files` config fields that were declared,
  parsed, and stored but never read by any adapter or check. Any YAML with these keys
  is silently ignored (no behaviour change).
- Documented `number_source_lookback` in the README config example.

### Changed
- AL-V01 is wired into both `_UNIQUE_CHECKS` (instruction files) and `_DOCS_CHECKS`
  (extra_paths docs), so value annotations are validated across all scanned content.
- AL-G01 is wired into `_STANDALONE_CHECKS`, running from config alone (no file
  inputs required).
- `LintResult` gains an optional `scanned_files: list[str]` field (default `[]`)
  for backwards-compatible JSON consumers.

---

## [0.2.0] — 2026-04-04

### Added
- **`extra_paths` config key** — glob patterns for additional documentation files
  (e.g. `docs/**/*.md`) to scan with AL-P* (forbidden patterns) and AL-F01 (file
  references). Files matched by `extra_paths` are tagged with the new `Role.DOCS` role
  and de-duplicated against adapter-collected files.
- **AL-E01 `config_parity` check** — verifies that every key in a source config file
  (e.g. `.env`) also appears in its template (e.g. `.env.example`). Configured via
  `config_parity` rules in `.agentlint.yml`. Supports `exclude_keys` for intentional
  omissions.
- **AL-C01 `consistency_groups` check** — extracts a regex capture group from multiple
  files and flags any file whose value disagrees with the consensus. Configured via
  `consistency_groups` rules in `.agentlint.yml`.
- **`Role.DOCS` enum value** — new instruction-file role for general documentation
  collected via `extra_paths`.
- 24 new tests (config parity, consistency groups, extra paths integration).
  Test count: 97 → 121.

### Changed
- AL-F01 (file references) now also runs against `Role.DOCS` files (previously
  `Role.SKILL` only).
- Exit-code 2 guard now skips when standalone checks (AL-E01, AL-C01) produce
  violations, so config-only runs report findings instead of falsely claiming
  "no files found".

### Fixed
- 4 pre-existing ruff lint findings in test files (unused imports, unused variable).
- Codebase-wide formatting pass via `ruff format` (20 files).

---

## [0.1.1] — 2026-04-02

### Added
- **Aider adapter** — detects and lints `.aider.conf.yml` (DISPATCH) and `.aider/rules/*.md`
  (SKILL) files. `--adapter aider` and auto-detection both supported.
- **Continue.dev adapter** — detects and lints `.continuerules` (DISPATCH) and
  `.continue/rules/*.md` (SKILL) files. `--adapter continue` and auto-detection both
  supported.
- **`--watch` mode** — re-lints automatically on every file save using `watchdog`.
  Install with `pip install 'instruction-lint[watch]'`.
- **`--format badge`** — generates a shields.io-style `agentlint-badge.svg` grade badge
  written to the scanned directory root.
- **`severity_overrides` config key** — re-classify any check ID from error→warning or
  warning→error in `.agentlint.yml`.
- **GitHub issue templates** — bug report and feature request forms added to
  `.github/ISSUE_TEMPLATE/`.
- **Discord community** — server at https://discord.gg/f5jQD5mtYj, badge in README.
- **README adapter table** — expanded to show Monolithic/Modular columns for all 5
  supported assistants.
- **GitHub Action inputs table** — documented `path`, `format`, `adapter`,
  `fail-on-warnings` with examples including SARIF Code Scanning.
- 20 new tests (adapters, badge, severity overrides, watch). Test count: 77 → 97.

### Changed
- `--format` now accepts `badge` in addition to `text`, `json`, `sarif`.
- `--adapter` now accepts `aider` and `continue` in addition to `copilot`, `cursor`,
  `windsurf`, `auto`.
- No-adapter-detected message lists all 5 supported file patterns.

### Added (from earlier pre-release, promoted to 0.1.1)
- **Windsurf adapter** — detects and lints `.windsurfrules` (DISPATCH) and
  `.windsurf/rules/*.md` (SKILL) files. `--adapter windsurf` and auto-detection both
  supported. (`agentlint/adapters/windsurf.py`)
- **`--format sarif`** — emits SARIF 2.1.0 JSON for direct ingestion by GitHub Code
  Scanning and other SAST platforms. (`agentlint/report.py`, `agentlint/cli.py`)
- **AL-F01 fuzzy suggestions** — when a referenced file path is not found on disk, the
  fix hint now checks for similarly-named files using `difflib.get_close_matches` and
  suggests the closest match (e.g. `Did you mean 'your-project/utils/validator.ts'?`).
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
- PyPI distribution name changed from `agentlint` to `instruction-lint` (the name `agentlint`
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
