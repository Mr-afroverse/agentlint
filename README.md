# agentlint

[![CI](https://github.com/Mr-afroverse/agentlint/actions/workflows/ci.yml/badge.svg)](https://github.com/Mr-afroverse/agentlint/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/instruction-lint)](https://pypi.org/project/instruction-lint/)
[![Python](https://img.shields.io/pypi/pyversions/instruction-lint)](https://pypi.org/project/instruction-lint/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?logo=discord&logoColor=white)](https://discord.gg/f5jQD5mtYj)

**The ESLint of AI coding assistant instructions.**

Audit, validate, and keep your GitHub Copilot skills, Cursor rules, and agent instruction files consistent with your actual codebase.

---

## Why

AI coding assistants are only as good as their instructions. Instruction files drift silently:

- A skill references a file that was renamed six months ago.
- A threshold is hardcoded in a SKILL.md but the constant changed in source code.
- Two skills have overlapping triggers — the agent picks randomly.
- A skill was added to disk but never wired into the dispatch table.

None of this gets caught by `markdownlint` or `yamllint`. These are **codebase-aware problems** that require **codebase-aware checks**.

---

## Quick start

```bash
pip install instruction-lint
cd your-project
agentlint
```

> **Note:** `pip install agentlint` also works — it's a thin alias package that installs `instruction-lint`. Both names install the same `agentlint` CLI binary.

Or as a **pre-commit hook** (recommended — runs on every commit, zero maintenance):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Mr-afroverse/agentlint
    rev: v0.6.0
    hooks:
      - id: agentlint
```

---

## What it checks

| ID | Check | Severity | Zero-config |
|----|-------|----------|-----------|
| AL-D01 | Skill path in dispatch table → exists on disk | Error | ✓ |
| AL-D02 | Skill file on disk → referenced in dispatch table | Error | ✓ |
| AL-D03 | No circular references between instruction files | Error | ✓ |
| AL-D04 | Every required role has at least one SKILL file | Error | — |
| AL-D05 | No two SKILL files share the same effective name | Error | ✓ |
| AL-F01 | Source-file paths in skill files → exist on disk | Warning | ✓ |
| AL-F02 | Internal anchor links (`#section`) → heading exists in same file | Warning | ✓ |
| AL-N01 | Threshold numbers → have a source pointer | Warning | ✓ |
| AL-N02 | Written percentage claims (`N percent`) → have a source pointer | Warning | ✓ |
| AL-T01 | Trigger descriptions → no significant overlap | Warning | ✓ |
| AL-P* | Forbidden patterns (built-in defaults + configurable) | Error | ✓ |
| AL-S01 | Credentials / secrets leaked in instruction files | Warning | ✓ |
| AL-INV01 | Negative existence claims about paths that actually exist on disk | Warning | ✓ |
| AL-Q01 | Vague instructions without actionable criteria | Warning | ✓ |
| AL-TOK01 | Instruction file exceeds configured token budget | Warning | — |
| AL-E01 | `.env` vs `.env.example` key parity | Error | — |
| AL-C01 | Cross-file value consistency groups | Error | — |
| AL-V01 | Documented numeric values → match source constants | Error | ✓ |
| AL-G01 | Documentation values → match ground-truth JSON/YAML | Error | — |
| AL-LEN01 | SKILL file content meets minimum token threshold | Warning | ✓ |
| AL-ENC01 | Instruction files are valid UTF-8 | Error | ✓ |
| AL-FM01 | SKILL files contain all required frontmatter keys | Warning | — |
| AL-DUP01 | No two SKILL (or DISPATCH) files are near-duplicates of each other | Warning | ✓ |
| AL-CONF01 | No contradictory directives across instruction files | Warning | ✓ |
| AL-FRESH01 | Dates in instruction files are not older than configured threshold | Warning | — |
| AL-DEP* | Deprecated AI provider patterns (models, SDK methods, endpoints) | Warning | — |

AL-D01, AL-D02, AL-D03, AL-D05, AL-F01, AL-F02, AL-N01, AL-N02, AL-T01, AL-P*, AL-S01, AL-INV01, AL-Q01, AL-ENC01, AL-DUP01, AL-CONF01, and AL-LEN01 work out of the box. AL-D04, AL-TOK01, AL-FM01, AL-FRESH01, AL-DEP*, AL-E01, AL-C01, AL-V01, and AL-G01 are config-driven — add rules in `.agentlint.yml` to activate them.

---

## Supported assistants

| Assistant | Monolithic File | Modular Rules Directory | Format Detected |
|-----------|:---:|:---:|----------------|
| **GitHub Copilot** | ✓ | ✓ | `.github/copilot-instructions.md` + `.github/instructions/*.md` (VS Code 1.99+) + `.github/skills/**/SKILL.md` |
| **Cursor** | ✓ | ✓ | `.cursorrules` + `.cursor/rules/*.mdc` |
| **Windsurf** | ✓ | ✓ | `.windsurfrules` + `.windsurf/rules/*.md` |
| **Aider** | ✓ | ✓ | `.aider.conf.yml` + `.aider/rules/*.md` |
| **Continue.dev** | ✓ | ✓ | `.continuerules` + `.continue/rules/*.md` |
| **Claude Code** | ✓ | ✓ | `CLAUDE.md` + `<subdir>/CLAUDE.md` (per-directory) + `.claude/agents/*.md` + `.claude/commands/*.md` + `.claude/rules/*.md` |
| **Gemini CLI** | ✓ | ✓ | `GEMINI.md` + `<subdir>/GEMINI.md` (per-directory) + `.gemini/rules/*.md` |

Multiple formats can be active at once. `agentlint` auto-detects which are present.

---

## Example output

```
[agentlint] 2 error(s), 1 warning(s) across 8 file(s).  Grade: C

  .github/skills/gps-scorer/SKILL.md
    ✖ [AL-D02]:1  Skill `gps-scorer` is not referenced in the dispatch file.
      Fix → Add an entry for `.github/skills/gps-scorer/SKILL.md` in the dispatch table.

  .github/copilot-instructions.md
    ✖ [AL-D01]:14  Skill path not found on disk: `.github/skills/old-scorer/SKILL.md`
      Fix → Create the file or correct the path in the dispatch table.

  .github/skills/eudr-standards/SKILL.md
    ⚠ [AL-N01]:48  Threshold number without source pointer: `| GREEN ≥ 90% |`
      Fix → Add '(Source: constants.py)' or a regulatory article reference.

  docs/ARCHITECTURE.md
    ✖ [AL-V01]:31  Documented value `25` ≠ source `NotificationConfig.minimum_risk_score` = `30` in `your-project/agents/config.py`
      Fix → Update the value to `30` or correct the source.
```

> **AL-V01 source annotation format:** Add a constant path to your `(Source:)` annotation to enable value validation:
> ```
> Notification threshold: 30  (Source: <your_module>/agents/config.py:NotificationConfig.minimum_risk_score)
> ```
> agentlint resolves the file, extracts the constant's current value, and errors if they disagree. Plain `(Source: file.py)` annotations (without `:constant`) are handled by AL-N01 as before.

> **AL-V01 note:** For Python files, extraction uses a full AST parse with class-scope awareness — it correctly resolves module-level constants, class attributes, type-annotated assignments (`THRESHOLD: int = 30`), and simple negative literals (`DEFAULT_SCORE = -1`). Regex extraction is used as a fallback for non-Python files (YAML, JSON, TypeScript, etc.). Computed expressions (`X = BASE * 0.9`), class properties, and runtime-only values cannot be extracted in any language — annotate simple scalar assignments for reliable results.

---

## Health scoring

Every run produces a **grade** (A–F) based on error and warning density across scanned files. Use it to track skill health over time in your CI dashboard.

```
Grade: A  → no violations, or up to 2 warnings per file
Grade: B  → up to 3–4 warnings per file, or 1 error in a large repo
Grade: C  → 6 warnings per file, or 1 error per small file
Grade: D  → 2 errors per file, or many warnings
Grade: F  → 3+ errors per file, or high combined density
```

The score formula is `100 − (errors_per_file × 20) − (warnings_per_file × 5)`. Grades A–F map to score bands 90 / 80 / 70 / 60 / below 60.

Pipe `--format json` into your CI annotation step:

```bash
agentlint --format json | tee agentlint-report.json
```

Or emit **SARIF** for GitHub Code Scanning:

```bash
agentlint --format sarif | tee agentlint.sarif
```

---

## Configuration

`agentlint` works with zero config. Add `.agentlint.yml` to extend or override defaults:

```yaml
# .agentlint.yml

# Add project-specific forbidden patterns (extends built-in defaults)
forbidden_patterns:
  - id: MY001
    pattern: '\b8-stage pipeline\b'
    reason: "Pipeline has 7 stages — this count will drift."
    fix: "Use '7-stage' and add a pointer to orchestrator.py."
    severity: error

# How many lines above a number agentlint looks for a source pointer (default 15)
number_source_lookback: 10

# Adjust trigger-overlap sensitivity (0.0–1.0, default 0.5)
trigger_overlap_threshold: 0.6

# Add extra source-root directories for file-reference resolution
source_roots: [".", "src", "backend"]

# Add project-specific source markers (extends built-in list)
source_markers:
  - "my_constants\\.py"
  - "REGULATORY_GATES"

# Disable specific checks
checks:
  trigger-overlap: false

# Re-classify individual check severity ("error" | "warning")
severity_overrides:
  AL-N01: error    # promote number-sourcing from warning to error
  AL-T01: warning  # demote trigger-overlap from default to warning

# Fail the run when warnings are present (default: only errors fail)
fail_on_warnings: true

# Paths to skip (substring match on the file path).
# Each entry is either a plain string (blanket ignore) or a dict.
# Dict entries support an optional "checks" list for per-check suppression:
# the file is still collected and all OTHER checks run on it.
ignore_paths:
  - "archive/"
  - path: "docs/health/"
    reason: "health-check docs are generated and always stale"
  - path: "CHANGELOG.md"
    checks: ["dead-anchors"]
    reason: "Illustrative examples trigger AL-F02 false positives"

# ── v0.2 features ────────────────────────────────────────────

# Glob patterns for extra documentation files to scan with AL-P* and AL-F01
extra_paths:
  - "docs/**/*.md"
  - "*.md"

# .env vs .env.example key parity (AL-E01)
config_parity:
  - source: ".env"
    template: ".env.example"
    severity: error

# AL-E01 parses both `KEY=value` and `export KEY=value` (bash-style) formats.
# Lines starting with `#` are treated as comments and ignored in both files.

# Cross-file value consistency groups (AL-C01)
consistency_groups:
  - id: test-count
    pattern: '\b(\d+)\s+passed'
    files: ["README.md", "CONTRIBUTING.md", "docs/RELEASE.md"]
    severity: error

# ── v0.3 features ────────────────────────────────────────────

# Validate documented numbers against their source constants (AL-V01)
# Works automatically on any file with (Source: file.py:CONSTANT) annotations.
# No config required — the annotation format is the trigger.

# Ground-truth file checks (AL-G01)
# value_match mode: scalar from JSON/YAML must match doc pattern
ground_truth_files:
  - id: TEST-COUNT
    json_file: "logs/test_results.json"  # written by CI
    json_path: "passed"
    doc_pattern: '\b(\d+) passed'
    files: ["README.md", "DEPLOYMENT_GUIDE.md"]
    reason: "Test count in docs must match pytest output"
    severity: error

  # no_stale_refs mode: list from JSON must include every referenced ID
  - id: ACTIVE-SOURCES
    json_file: "config/sources_production.json"
    json_path: "sources[*].id"
    mode: "no_stale_refs"
    ref_pattern: '\b([\w-]+-(?:news|feed|monitor))\b'
    files: ["**/*.md"]
    reason: "Source IDs in docs must exist in sources_production.json"
    severity: warning

# Opt-in: check filenames inside ASCII tree diagrams for AL-F01
# Only scans bare prose trees (├──/└── lines) — code fences are skipped by default.
tree_diagram_paths: true

# Opt-in: also scan tree diagrams inside ``` code fences (requires tree_diagram_paths: true)
tree_diagram_fenced: true

# AL-TOK01: warn when a SKILL or DISPATCH file exceeds this estimated token count.
# Token count is approximated as len(content) / 4 (OpenAI heuristic). 0 = disabled.
token_budget: 2000

# AL-LEN01: warn when a SKILL file has fewer than this many estimated tokens.
# Default 10. Set to 0 to disable.
min_content_tokens: 20

# AL-DUP01: Jaccard similarity threshold for near-duplicate detection (0.0–1.0).
# Files with similarity >= threshold are flagged. Default 0.85. Set to 0 to disable.
duplicate_threshold: 0.9

# AL-D04: role names that must each have at least one SKILL file.
# Role is matched against skill `name` frontmatter or parent directory name.
required_roles:
  - "gps-scorer"
  - "code-reviewer"

# AL-FM01: required frontmatter keys for SKILL files. Empty list = disabled.
required_frontmatter:
  - name
  - description

# AL-DEP*: deprecated AI provider patterns (model names, SDK methods, endpoints).
deprecated_patterns:
  - pattern: "gpt-4-0613"
    reason: "Model deprecated by OpenAI."
    replacement: "gpt-4o"
  - pattern: "openai\\.ChatCompletion\\.create"
    reason: "openai v0.x API — removed in v1.0."
    replacement: "client.chat.completions.create"
    severity: error

# AL-FRESH01: warn when dates in instruction files are older than this many days.
# 0 = disabled (default).
stale_days: 180
```

### Replace built-in forbidden patterns entirely

```yaml
forbidden_patterns_mode: replace
forbidden_patterns:
  - id: PROJ001
    pattern: '\blegacy_mode\b'
    reason: "legacy_mode was removed in v2."
    fix: "Delete the flag entirely."
    severity: error
```

### Check keys reference

Every check can be toggled in `.agentlint.yml` with `checks: {key: false}`. The full set of valid keys:

| Config key | Check ID(s) | Notes |
|---|---|---|
| `dispatch-coverage` | AL-D01, AL-D02, AL-D05 | Skill path / dispatch table consistency |
| `circular-refs` | AL-D03 | No circular backtick-path reference chains |
| `role-coverage` | AL-D04 | Required roles have at least one SKILL file |
| `file-references` | AL-F01 | Source-file paths exist on disk |
| `dead-anchors` | AL-F02 | Internal `#heading` anchors resolve |
| `number-sourcing` | AL-N01, AL-N02 | Threshold numbers and percentages have source pointers |
| `value-extraction` | AL-V01 | Documented constants match source code values |
| `trigger-overlap` | AL-T01 | No two SKILLs share effectively the same trigger |
| `forbidden-patterns` | AL-P* | Built-in + custom forbidden pattern matches |
| `deprecated-patterns` | AL-DEP* | Deprecated AI provider models / SDK methods |
| `secret-detection` | AL-S01 | No credentials or tokens in instruction files |
| `inverse-claims` | AL-INV01 | Negative existence claims about paths that exist |
| `vague-instructions` | AL-Q01 | Vague directives without actionable criteria |
| `semantic-conflict` | AL-CONF01 | Contradictory directives across files |
| `duplicate-content` | AL-DUP01 | Near-duplicate SKILL or DISPATCH files |
| `encoding-check` | AL-ENC01 | Files are valid UTF-8 |
| `frontmatter-schema` | AL-FM01 | Required frontmatter keys present |
| `min-content` | AL-LEN01 | Files meet minimum token threshold |
| `token-budget` | AL-TOK01 | Files stay within maximum token budget |
| `freshness` | AL-FRESH01 | Dates are not older than configured threshold |
| `config-parity` | AL-E01 | `.env` / `.env.example` key parity |
| `consistency-groups` | AL-C01 | Cross-file value consistency groups |
| `ground-truth` | AL-G01 | Values match ground-truth JSON/YAML |

All checks default to **on**. Config-driven checks (AL-D04, AL-TOK01, AL-FM01, AL-FRESH01, AL-DEP*, AL-E01, AL-C01, AL-G01) require additional config keys to produce violations — toggling them without that config has no effect.

---

## Layer 2: Behavioral testing

The checks above are **static** — they analyse files without running the agent. To test whether your skills actually fire correctly and produce sound guidance, use the included behavioral test sheet:

```bash
agentlint --init   # copies SKILL_HEALTH_CHECK.md into .github/skills/
```

The template contains 10 ready-to-run prompts with explicit PASS/FAIL criteria covering trigger accuracy, over-firing prevention, source-pointer discipline, multi-skill invocation, and more.

---

## GitHub Action

```yaml
# .github/workflows/agentlint.yml
name: agentlint
on: [push, pull_request]

jobs:
  agentlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Mr-afroverse/agentlint@v0.6.0
```

### Action inputs

| Input | Default | Description |
|-------|---------|-------------|
| `path` | `.` | Directory to scan |
| `format` | `text` | Output format — `text`, `json`, `sarif`, `badge`, or `html` |
| `adapter` | `auto` | Force adapter — `copilot`, `cursor`, `windsurf`, `aider`, `continue`, `claudecode`, `gemini`, or `auto` |
| `fail-on-warnings` | `false` | Exit 1 when warnings are present |
| `version` | `0.6.0` | `instruction-lint` version to install — pin for reproducible CI |
| `config` | _(empty)_ | Path to `.agentlint.yml` config file (passed as `--config`) |

Example — fail the build on warnings:

```yaml
- uses: Mr-afroverse/agentlint@v0.6.0
  with:
    fail-on-warnings: true
```

Example — emit SARIF for [GitHub Code Scanning](https://docs.github.com/en/code-security/code-scanning):

```yaml
- name: Install agentlint
  run: pip install instruction-lint
- name: Run agentlint (SARIF)
  run: agentlint --format sarif > agentlint.sarif
- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: agentlint.sarif
```

Example — write an HTML report as a build artifact:

```yaml
- name: Install agentlint
  run: pip install instruction-lint
- name: Run agentlint (HTML)
  run: agentlint --format html || true   # don't fail; upload the report regardless
- name: Upload HTML report
  uses: actions/upload-artifact@v4
  with:
    name: agentlint-report
    path: agentlint-report.html
```

---

## SARIF → GitHub inline PR annotations

agentlint's `--format sarif` output is SARIF 2.1.0. GitHub Code Scanning converts it to inline annotations on pull requests automatically once the SARIF file is uploaded.

### Option A — GitHub Code Scanning (recommended)

Requires GitHub Advanced Security (free for public repos, licensed for private).

```yaml
# .github/workflows/agentlint.yml
name: agentlint
on: [push, pull_request]

jobs:
  agentlint:
    runs-on: ubuntu-latest
    permissions:
      security-events: write   # required for upload-sarif
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Install agentlint
        run: pip install instruction-lint
      - name: Run agentlint
        run: agentlint --format sarif > agentlint.sarif || true
      - name: Upload SARIF to GitHub Code Scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: agentlint.sarif
```

Violations appear as inline annotations on the **Files changed** tab of every PR, with the check ID, message, and fix hint visible without leaving the review UI.

### Option B — Lightweight GitHub Actions annotations (no GHAS required)

For private repos without GitHub Advanced Security, pipe the JSON output through a small script to emit [workflow commands](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions).

```yaml
- name: Install agentlint
  run: pip install instruction-lint
- name: Run agentlint and emit annotations
  run: |
    agentlint --format json > agentlint-result.json || true
    python - <<'EOF'
    import json, sys
    data = json.load(open("agentlint-result.json"))
    level_map = {"error": "error", "warning": "warning", "info": "notice"}
    for v in data["violations"]:
        level = level_map.get(v["severity"], "warning")
        file  = v["file"]
        line  = v.get("line") or 1
        msg   = v["message"].replace("%", "%25").replace("\n", "%0A")
        print(f"::{level} file={file},line={line}::{v['check_id']} — {msg}")
    if data["errors"]:
        sys.exit(1)
    EOF
```

### Option C — reviewdog

If you already use [reviewdog](https://github.com/reviewdog/reviewdog) in your pipeline:

```yaml
- name: Install tools
  run: |
    pip install instruction-lint
    curl -sfL https://raw.githubusercontent.com/reviewdog/reviewdog/master/install.sh | sh -s -- -b /usr/local/bin
- name: Run agentlint via reviewdog
  env:
    REVIEWDOG_GITHUB_API_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    agentlint --format sarif > agentlint.sarif || true
    reviewdog -f=sarif -name=agentlint -reporter=github-pr-review < agentlint.sarif
```

reviewdog posts each violation as a PR review comment on the exact changed line.

### Baseline suppression in CI

For repos with pre-existing violations, capture a baseline once and only fail on new regressions:

```yaml
# Step 1 (run once, commit .agentlint-baseline.json to the repo)
# agentlint --update-baseline .agentlint-baseline.json

# Step 2 (in CI — only new violations fail the build)
- name: Run agentlint with baseline
  run: agentlint --baseline .agentlint-baseline.json
```

---

## CLI reference

```
Usage: agentlint [OPTIONS] [PATH]

  agentlint — audit AI coding assistant instruction files.

Options:
  -V, --version                   Show the version and exit.
  --format [text|json|sarif|badge|html]
                                  Output format (default: text).
                                  'badge' writes agentlint-badge.svg to disk.
                                  'html' writes agentlint-report.html to disk.
  --config PATH                   Path to .agentlint.yml config file.
  --adapter [copilot|cursor|windsurf|aider|continue|claudecode|gemini|auto]
                                  Force a specific adapter (default: auto-
                                  detect).
  --fail-on-warnings              Exit 1 when warnings are present (overrides
                                  config).
  --init                          Generate .agentlint.yml and copy
                                  SKILL_HEALTH_CHECK.md into .github/skills/.
  --fix                           Auto-fix violations that have a deterministic
                                  fix. Modifies files in-place.
  --baseline PATH                 Suppress violations already recorded in
                                  PATH. Reports only new regressions.
  --update-baseline PATH          Snapshot current violations to PATH and
                                  exit 0. Commit the file to silence known
                                  issues in CI.
  --watch                         Re-run on file changes. Requires: pip
                                  install 'instruction-lint[watch]'.
  -h, --help                      Show this message and exit.
```

---

## Development

```bash
git clone https://github.com/Mr-afroverse/agentlint
cd agentlint
pip install -e ".[dev]"  # or: pip install instruction-lint
pytest
```

---

## License

MIT — see [LICENSE](LICENSE).
