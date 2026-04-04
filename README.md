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

Or as a **pre-commit hook** (recommended — runs on every commit, zero maintenance):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Mr-afroverse/agentlint
    rev: v0.3.0
    hooks:
      - id: agentlint
```

---

## What it checks

| ID | Check | Severity | Zero-config |
|----|-------|----------|-----------|
| AL-D01 | Skill path in dispatch table → exists on disk | Error | ✓ |
| AL-D02 | Skill file on disk → referenced in dispatch table | Error | ✓ |
| AL-F01 | Source-file paths in skill files → exist on disk | Warning | ✓ |
| AL-N01 | Threshold numbers → have a source pointer | Warning | ✓ |
| AL-T01 | Trigger descriptions → no significant overlap | Warning | ✓ |
| AL-P* | Forbidden patterns (built-in defaults + configurable) | Error | ✓ |
| AL-E01 | `.env` vs `.env.example` key parity | Error | — |
| AL-C01 | Cross-file value consistency groups | Error | — |
| AL-V01 | Documented numeric values → match source constants | Error | — |
| AL-G01 | Documentation values → match ground-truth JSON/YAML | Error | — |

AL-D01, AL-D02, AL-F01, AL-N01, AL-T01, and AL-P* work out of the box. AL-E01, AL-C01, AL-V01, and AL-G01 are config-driven — add rules in `.agentlint.yml` to activate them.

---

## Supported assistants

| Assistant | Monolithic File | Modular Rules Directory | Format Detected |
|-----------|:---:|:---:|----------------|
| **GitHub Copilot** | ✓ | ✓ | `.github/copilot-instructions.md` + `.github/skills/**/SKILL.md` |
| **Cursor** | ✓ | ✓ | `.cursorrules` + `.cursor/rules/*.mdc` |
| **Windsurf** | ✓ | ✓ | `.windsurfrules` + `.windsurf/rules/*.md` |
| **Aider** | ✓ | ✓ | `.aider.conf.yml` + `.aider/rules/*.md` |
| **Continue.dev** | ✓ | ✓ | `.continuerules` + `.continue/rules/*.md` |

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
    ✖ [AL-V01]:31  Documented value `25` ≠ source `NotificationConfig.minimum_risk_score` = `30` in `agents/notification_agent.py`
      Fix → Update the value to `30` or correct the source.
```

> **AL-V01 source annotation format:** Add a constant path to your `(Source:)` annotation to enable value validation:
> ```
> Notification threshold: 30  (Source: agents/notification_agent.py:NotificationConfig.minimum_risk_score)
> ```
> agentlint resolves the file, extracts the constant's current value, and errors if they disagree. Plain `(Source: file.py)` annotations (without `:constant`) are handled by AL-N01 as before.

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

# Paths to skip (substring match on the file path)
ignore_paths:
  - "archive/"
  - "docs/health/"

# ── v0.2 features ────────────────────────────────────────────

# Glob patterns for extra documentation files to scan with AL-P* and AL-F01
extra_paths:
  - "docs/**/*.md"
  - "*.md"

# .env vs .env.example key parity (AL-E01)
# Parses KEY=value and export KEY=value formats. Commented-out keys (# KEY=)
# are not counted as defined keys in either file.
config_parity:
  - source: ".env"
    template: ".env.example"
    severity: error

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
tree_diagram_paths: true
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
      - uses: Mr-afroverse/agentlint@v0.3.0
```

### Action inputs

| Input | Default | Description |
|-------|---------|-------------|
| `path` | `.` | Directory to scan |
| `format` | `text` | Output format — `text`, `json`, `sarif`, or `badge` |
| `adapter` | `auto` | Force adapter — `copilot`, `cursor`, `windsurf`, `aider`, `continue`, or `auto` |
| `fail-on-warnings` | `false` | Exit 1 when warnings are present |

Example — fail the build on warnings:

```yaml
- uses: Mr-afroverse/agentlint@v0.3.0
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

---

## CLI reference

```
Usage: agentlint [OPTIONS] [PATH]

  agentlint — audit AI coding assistant instruction files.

Options:
  -V, --version                   Show the version and exit.
  --format [text|json|sarif|badge]
                                  Output format (default: text). 'badge' writes
                                  agentlint-badge.svg to disk.
  --config PATH                   Path to .agentlint.yml config file.
  --adapter [copilot|cursor|windsurf|aider|continue|auto]
                                  Force a specific adapter (default: auto-
                                  detect).
  --fail-on-warnings              Exit 1 when warnings are present (overrides
                                  config).
  --init                          Copy SKILL_HEALTH_CHECK.md template into
                                  .github/skills/.
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
