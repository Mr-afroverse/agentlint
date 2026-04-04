# Feature Gap Analysis: `agentlint` v0.1.1

**From:** A production compliance-monitoring pipeline built on GitHub Copilot  
**Repo evaluated:** https://github.com/Mr-afroverse/agentlint (v0.1.1, April 3 2026)  
**Purpose of this document:** Honest, detailed feedback on where agentlint fits and what it would need to
cover the class of documentation drift problems our project actually experiences. Offered as constructive
input, not criticism — the tool is clearly well-designed within its stated scope.

---

## 1. Our Project in Brief

A 7-stage EU regulatory compliance monitoring pipeline (~4,000 lines of Python):

```
Source Monitor → Regulatory Diff → Category Filter → LLM Interpretation
    → Client Mapping → Risk Scoring → Notification
```

- **12 agents** under `agents/` — each is a pure-Python module with `@dataclass` result schemas
- **13 documentation files** — README, deployment guide, architecture diagram, release checklist,
  limitations, quick-reference, 4 docs in `docs/`, `logs/README.md`, CI workflow docs
- **8 config files** — JSON sources/clients per environment, `.env`, `.env.example`
- **623 tests** — pytest, covering all agents and the orchestrator
- **GitHub Actions CI** — PR validation, weekly scheduled run

The key design tension: constants live in Python (scoring caps, LLM call limits, notification threshold),
decision data lives in JSON (which sources are active, which clients exist), and prose descriptions of
both live scattered across 13 markdown files. Keeping the three in sync is the core documentation problem.

---

## 2. The Documentation Drift We Actually Experienced

Before a recent full-codebase audit, we had **29 confirmed drift findings** across 13 files.
After the audit, all 29 were fixed by hand. The breakdown:

| Severity | Count | Typical example |
|----------|-------|-----------------|
| SIGNIFICANT | 4 | Wrong threshold value in architecture diagram |
| MINOR | 9 | Stale test count in 5 different files |
| CLEANUP | 16 | Removed source ID appearing in 7 still-active docs |

Representative concrete examples — each one is real and verified:

```
RELEASE_CHECKLIST.md:   "Expected test count: 497 passed"  (actual: 623)
LIMITATIONS.md:         "No alerting on system failure"     (failure_alerter.py exists and works)
VISUAL_ARCHITECTURE.md: "Notification threshold: 25"        (code constant: 30)
README.md:              source "eu-gdpr-main"               (removed from sources.json months earlier)
DEPLOYMENT_GUIDE.md:    source "eu-gdpr-main"               (same stale reference)
QUICK_REFERENCE.md:     source "eu-gdpr-main"               (same)
SCHEDULED_EXECUTION.md: source "eu-gdpr-main"               (same)
GITHUB_ACTIONS_SETUP.md:source "eu-gdpr-main"               (same)
VISUAL_ARCHITECTURE.md: file "weekly_regulation_check.yml"  (actual: scheduled.yml)
VISUAL_ARCHITECTURE.md: file "stress_test_api_failures.py"  (actual: stress_test_alerts.py)
VISUAL_ARCHITECTURE.md: file "digest_tracking.json"         (actual file does not exist)
config/.env.example:    missing FLASK_SECRET_KEY and DASHBOARD_PASSWORD (both required at runtime)
agents/rate_limiter.py: code defaults 10/day                (operational .env value: 30/day)
```

None of these were caught by markdownlint, yamllint, or any existing CI check.

---

## 3. What agentlint Does Well

To be precise: agentlint's stated scope is "AI coding assistant instruction files" and it is honest about
this throughout its README. Within that scope, it does useful things:

| Check | What it catches | Verdict |
|-------|----------------|---------|
| AL-D01 | Skill path in dispatch table → exists on disk | Directly useful |
| AL-D02 | Skill on disk → referenced in dispatch table | Directly useful |
| AL-F01 | Source-file paths inside skill files → exist on disk | Directly useful |
| AL-N01 | Number in instruction file lacks a `(Source: X)` comment | Stylistically useful |
| AL-T01 | Two skill trigger descriptions overlap (cosine similarity) | Useful for multi-skill repos |
| AL-P* | Custom forbidden string/regex patterns | Partially useful (see Gap 1) |

For `.github/copilot-instructions.md` and `.github/skills/**/SKILL.md`, agentlint is genuinely useful.
AL-D01/D02 would catch a broken skill path the moment a file is renamed. AL-F01 would catch a dead
reference inside a skill body. These are real bugs we would want caught.

**However, in our audit, only 2 of the 29 findings were in instruction or skill files.**
The other 27 were in general documentation files that agentlint does not scan.

---

## 4. Gap Analysis — What We Needed That Doesn't Exist

### Gap 1: Scope — instruction files only, not all repository documentation

**What agentlint scans (Copilot adapter):**
```
.github/copilot-instructions.md
.github/skills/**/SKILL.md
```

**What our drift was actually in:**
```
README.md
LIMITATIONS.md
DEPLOYMENT_GUIDE.md
QUICK_REFERENCE.md
docs/RELEASE_CHECKLIST.md
docs/VISUAL_ARCHITECTURE.md
docs/SCHEDULED_EXECUTION.md
docs/GITHUB_ACTIONS_SETUP.md
logs/README.md
```

AL-P* forbidden patterns can be added via `.agentlint.yml`, but the pattern match still runs only against
the scanned instruction/skill files. Adding `pattern: '\beu-gdpr-main\b'` would not have caught the five
occurrences of that string in general `docs/*.md` and root-level markdown files.

**What would close this gap:**  
A `--scope all-markdown` flag (or a `scan_paths` config key) that extends pattern checks and file-reference
checks to all `.md` files in the repository, while keeping the instruction-specific checks (AL-D01, AL-D02,
AL-T01) scoped to their natural targets. The two concerns are orthogonal — they don't need the same scope.

---

### Gap 2: AL-N01 checks syntax (source pointer present/absent), not semantic correctness

**What AL-N01 does:**  
Flags a number in an instruction file that lacks a comment like `(Source: constants.py)`.  
Fix suggested: _"Add '(Source: constants.py)' or a regulatory article reference."_

**What we actually needed:**  
The number in the documentation was **wrong** — not merely unsourced.

Concrete example:
```
# In docs/VISUAL_ARCHITECTURE.md (before fix):
⚪ Score 0–24   → No email
⚪ Score 25–29  → No email           ← value 25 is wrong

# In agents/notification_agent.py (source of truth):
minimum_risk_score: int = 30          ← actual value is 30
```

AL-N01 would have warned: "Threshold number without source pointer." After a developer adds
`(Source: notification_agent.py)`, the warning goes away — but **the wrong value (25) remains in the
doc** and the check passes. The tool cannot tell the difference between a correctly-sourced wrong value and
a correctly-sourced correct value.

Similarly for score caps:
```
# VISUAL_ARCHITECTURE.md (before fix):
INFORMATIONAL → max 20  (Source: risk_scoring_agent.py)   ← correct after sourcing
SEMI-BINDING  → max 74  (Source: risk_scoring_agent.py)   ← correct after sourcing
```

With proper source pointers, AL-N01 is satisfied. But if someone changes `INFORMATIONAL_MAX_SCORE = 20`
to `INFORMATIONAL_MAX_SCORE = 15` in the Python file, the doc now has a stale value with a valid source
pointer — and AL-N01 still passes because the pointer exists.

**What would close this gap:**  
A value-extraction check: given a source pointer annotation like `(Source: risk_scoring_agent.py:ScoringWeights.INFORMATIONAL_MAX_SCORE)`,
read the referenced Python file, extract the constant's actual value, and compare it against the number
in the documentation. This is a fundamentally different class of check — it requires file I/O at the
referenced path and light Python-AST or regex parsing to extract integer literals from constant assignments.

This would be the most powerful feature addition: **"sourced numbers that the tool actually validates,
not just marks as reviewed."**

---

### Gap 3: No ground-truth extraction from external commands or config files

Several classes of drift require running something or reading a structured file to know the correct value:

**Test counts** — appear in 5 of our markdown files and must match `pytest` output:
```
README.md:              "623 passed, 2 skipped"
LIMITATIONS.md:         "623 tests"
DEPLOYMENT_GUIDE.md:    "623 passed"
docs/RELEASE_CHECKLIST.md: "623 passed, 2 skipped"
docs/VISUAL_ARCHITECTURE.md: (referenced in a comment)
```
Before our fix, most of these said `497` or `460+`. No static linter can know what `pytest` outputs
without running it. But a CI-aware check could: run `python -m pytest --co -q` to get the count, then
grep all markdown for numeric patterns near the word "test" and validate they match.

**Active source IDs** — must match `config/sources.json` and `config/sources_production.json`:
```json
{"id": "edpb-news",  "type": "rss" ...}
{"id": "cnil-france-news", ...}
{"id": "edps-news", ...}
{"id": "enisa-news", ...}
```
The source `eu-gdpr-main` was removed from these config files. It then appeared as a stale reference
in 5 documentation files for months. A tool that reads the JSON to build an authoritative source-ID list
and then checks all documentation for references to IDs not in that list would have caught all 5 instantly.

**What would close this gap:**  
A `ground_truth` config block in `.agentlint.yml`:
```yaml
ground_truth:
  - id: PROJ-TC
    command: "python -m pytest --co -q 2>&1 | tail -1"
    extract_regex: '(\d+) passed'
    doc_pattern: '\b(\d+)\s+passed\b'
    reason: "Test count in docs must match pytest output"
    severity: error

  - id: PROJ-SRC
    json_file: "config/sources_production.json"
    json_path: "$.sources[*].id"
    doc_search_in: "**/*.md"
    mode: "no_stale_refs"
    reason: "Source IDs referenced in docs must exist in sources_production.json"
    severity: warning
```
This is admittedly a larger feature — it requires running subprocess commands and a JSON path evaluator.
But for projects where Python constants and JSON config ARE the source of truth for documentation values,
this would eliminate the largest single class of drift.

---

### Gap 4: No cross-file value consistency check

Some values must be identical across multiple files simultaneously. Neither AL-N01 (per-file check) nor
AL-P* (forbidden pattern, not value equality) addresses this.

Concrete example — all of these must say the same test count at all times:
```
README.md line 47                → "623 passed, 2 skipped"
LIMITATIONS.md line 82           → "623 tests"
DEPLOYMENT_GUIDE.md line 31      → "623 passed"
docs/RELEASE_CHECKLIST.md line 4 → "623 passed, 2 skipped"
```

When the test count changes (it went from 497 → 529 → 571 → 580 → 585 → 621 → 623 over the life of this
project), all four files need updating. Currently there is no automated check that these four agree.

A forbidden-pattern approach cannot help here because the value itself isn't forbidden — only a stale
version of it is, and the tool cannot know what "stale" means without an external reference.

**What would close this gap:**  
A `consistency_groups` config key:
```yaml
consistency_groups:
  - id: PROJ-TESTCOUNT
    pattern: '\b(\d+)\s+passed,\s+(\d+)\s+skipped\b'
    files: ["README.md", "LIMITATIONS.md", "DEPLOYMENT_GUIDE.md", "docs/RELEASE_CHECKLIST.md"]
    reason: "All doc files must report the same test count"
    severity: error
```
The check would extract the captured group from each file, compare them, and fail if any differ from
the others (without needing to know which is "correct").

---

### Gap 5: No environment config parity check (.env vs .env.example)

One of our four SIGNIFICANT findings: `config/.env` contained `FLASK_SECRET_KEY` and `DASHBOARD_PASSWORD`
(required at runtime), but `config/.env.example` (the template developers use when setting up the project)
was missing both keys entirely. A new developer cloning the repo and copying `.env.example` would get a
broken installation with no obvious error message.

This class of problem — `.env` has keys that `.env.example` lacks — is a common and serious gap. It is
not about "instruction files" at all, but it is exactly the kind of drift a developer tooling project
should care about.

agentlint has no mechanism to compare two config files for key parity.

**What would close this gap:**  
A `config_parity` check:
```yaml
config_parity:
  - id: PROJ-ENV
    source: "config/.env"
    template: "config/.env.example"
    mode: "keys_only"             # ignore values, compare key names
    exclude_keys: ["LLM_API_KEY"] # keys intentionally absent from template
    reason: ".env.example must contain every key that .env defines"
    severity: error
```
This is a straightforward diff check between two line-based key-value files. It requires no instruction
file parsing and is pure file I/O. It would close a gap that affects every project that uses `.env` and
`.env.example`.

---

### Gap 6: No codebase inventory check (file/agent/function claimed vs. actually existing)

**`LIMITATIONS.md` (before fix):**
```
❌ No alerting on system failure
```
**Reality:**
```
agents/failure_alerter.py  (exists, implemented, tested — 623 tests include it)
```

This false claim may have existed in the doc since before `failure_alerter.py` was built. AL-F01 checks
whether paths *referenced inside instruction files* exist on disk — but it cannot catch the inverse:
a claim in a documentation file that a capability *does not exist* when in fact it does.

More generally: documentation files often make claims about the codebase's capabilities, limitations,
and components. There is no mechanism to validate those claims against the actual filesystem.

A simpler variant of this check would be: given a pattern like `agents/\w+_agent\.py` appearing in a
markdown file, verify the referenced path exists. AL-F01 does something like this inside skill files —
the scope extension from Gap 1 would partially cover this if applied to all markdown files.

---

## 5. Summary: Fit Table

| Capability needed | AL-P* covers it? | AL-N01 covers it? | AL-F01 covers it? | Notes |
|---|---|---|---|---|
| Forbidden string in instruction files | ✅ Yes | — | — | Works well |
| Forbidden string in all `.md` files | ⚠️ Partial | — | — | Scope is instruction files; general docs not scanned |
| Broken file path in skill body | — | — | ✅ Yes | Works well |
| Wrong numeric value in docs (vs. code constant) | ❌ No | ❌ No (style only) | ❌ No | Requires value extraction |
| Test count in docs matches pytest output | ❌ No | ❌ No | ❌ No | Requires command execution |
| Stale source IDs in docs vs. config JSON | ❌ No | ❌ No | ❌ No | Requires JSON ground truth |
| Cross-file value consistency | ❌ No | ❌ No | ❌ No | No current mechanism |
| .env vs .env.example key parity | ❌ No | ❌ No | ❌ No | Out of scope entirely |
| False "does not exist" claims in docs | ❌ No | ❌ No | ⚠️ Scope-limited | Inverse of AL-F01 |

**Overall fit for our project (instruction files only):** Covers ~3 of our 29 findings.  
**Projected fit with Gap 1 + Gap 2 implemented:** Would cover ~22 of the 29 findings.  
**Projected fit with all 5 gaps implemented:** Would cover 27–29 of the 29 findings.

---

## 6. Feature Request Priority (Our Opinion)

Ordered by impact-to-implementation-effort ratio:

1. **Gap 1 (scan_paths / --scope all-markdown)** — HIGH impact, LOW effort. Extending AL-P* and
   AL-F01 pattern matching to user-configured paths would immediately expose most of our 29 findings.
   The instruction-specific checks (AL-D01/D02, AL-T01) remain safely scoped. Implementation is
   likely 20–50 lines of config parsing + glob expansion.

2. **Gap 5 (.env/.env.example parity)** — MEDIUM impact, LOW effort. Pure file I/O, no new concepts.
   Would close a class of problem that affects nearly every Python project. Implementation is ~30 lines.

3. **Gap 2 (value validation for sourced numbers)** — HIGH impact, MEDIUM effort. Requires Python-AST
   or regex extraction from referenced source files. Would make AL-N01 a genuinely correctness-checking
   rule rather than a style rule. Could be opt-in via `(Source: file.py:ClassName.CONSTANT_NAME)` syntax.

4. **Gap 4 (cross-file consistency groups)** — MEDIUM impact, MEDIUM effort. A new check type with its
   own config key. Regex-extract + compare across files. No external commands needed.

5. **Gap 3 (ground-truth from commands/JSON)** — HIGH impact, HIGH effort. Requires subprocess
   execution and JSON path resolution. Most powerful but most complex to implement safely (injection
   risk from user-supplied commands in `.agentlint.yml`).

---

## 7. What We Did Instead (for transparency)

Because agentlint's scope didn't cover our drift problem, we implemented a two-layer manual approach:

**Layer 1 — agentlint** (for `.github/copilot-instructions.md` + skills):  
Run `agentlint` in CI via the GitHub Action. Catches dead skill paths and missing source pointers in
the one file that contains operational thresholds.

**Layer 2 — grep patterns in `pr-validation.yml`** (for all other `.md` files):  
Shell script checking for forbidden strings across all markdown:
```bash
grep -rn "eu-gdpr-main\|460+ tests\|497 passed\|Regulatory Update:" docs/ *.md logs/
```
This works but requires manual maintenance every time a value legitimately changes. It is a workaround
for the absence of Gap 1–4 above.

The ideal state is a single unified tool that handles both layers, with config-file-based ground truth
for values that change over the project lifecycle.

---

## 8. Conclusion

agentlint is solving the right problem. Documentation drift from code is real, silent, and zero linters
catch it today. The architectural decision to make checks "codebase-aware" rather than purely text-aware
is exactly correct.

The gap between what it *currently* does and what projects like ours *need* is primarily one of **scope**
(instruction files vs. all documentation) and **check depth** (presence of source pointer vs. correctness
of the sourced value). Neither gap requires rethinking the architecture — both are incremental extensions
of what AL-F01 and AL-N01 already do conceptually.

The `.agentlint.yml` configuration surface is well-designed and would accommodate most of the proposed
features without breaking existing users. The `severity_overrides`, `source_roots`, and
`forbidden_patterns_mode: replace` keys demonstrate the right extensibility pattern.

We would use a version of agentlint that addressed Gap 1 and Gap 2 without reservation in CI.

---

*Prepared April 4, 2026. Repository: EU Regulatory Compliance Monitoring Pipeline (private, not public).*  
*All examples are from real audit findings on this codebase, not hypothetical.*
