# Agentlint Stress Test Report — ClaudeCode Adapter Repos
**Date:** 2026-04-08  
**Runner:** stress-test agent  
**Agentlint root:** `C:\Users\-_-\Downloads\Skillproject`  
**Scope:** Two public ClaudeCode-adapter repos tested for real-world check behaviour

---

## 1. Repos Tested

| # | Repo | Stars | Adapter | Why Selected |
|---|------|-------|---------|--------------|
| 4 | `arc42/quality.arc42.org-site` | ~200 | claudecode | Large CLAUDE.md (1 160 lines, 11-entry ToC). Known `&`-containing headings for AL-F02 anchor testing. 9 command skill files for dispatch-coverage testing. |
| 5 | `ndif-team/nnsight` | 883 | claudecode | Massive CLAUDE.md (1 900+ lines, 23-entry ToC). Heavy anchor cross-references — tests AL-F02 zero-false-positive rate on clean anchors. |

---

## 2. Gate Results

### Repo 4 — `arc42/quality.arc42.org-site`

| Gate | Verdict | Detail |
|------|---------|--------|
| 2.1 Clone | GREEN | Cloned successfully |
| 2.2 Adapter detection | GREEN | `claudecode` — correct |
| 2.3 Completion | GREEN | Exit 1, valid JSON, 10 files scanned, no traceback |
| 2.4 Violation volume | GREEN | 16 violations (8 errors, 8 warnings) — proportional |

**Violation breakdown:**

| Check | Count | Severity | Summary |
|-------|-------|----------|---------|
| AL-D02 | 8 | error | 8 skill files in `.claude/commands/` not referenced from dispatch (CLAUDE.md) |
| AL-F01 | 5 | warning | Template paths (`src/main.rs`, `src/auth/jwt.rs`, etc.) in command docs don't exist on disk |
| AL-F02 | 2 | warning | Anchor `#testing--validation` and `#git--deployment` flagged as dead — **false positives** (see Section 3) |
| AL-Q01 | 1 | warning | Line 790: `"Follow best practices"` — genuinely vague |

### Repo 5 — `ndif-team/nnsight`

| Gate | Verdict | Detail |
|------|---------|--------|
| 2.1 Clone | GREEN | Cloned successfully |
| 2.2 Adapter detection | GREEN | `claudecode` — correct |
| 2.3 Completion | GREEN | Exit 0 grade A, valid JSON, 1 file scanned, no traceback |
| 2.4 Violation volume | GREEN | 1 violation — proportional for a single clean file |

**Violation breakdown:**

| Check | Count | Severity | Summary |
|-------|-------|----------|---------|
| AL-F02 | 1 | warning | Anchor `#development--testing-notes` flagged as dead — **false positive** (see Section 3) |

---

## 3. Per-Check Analysis (New Checks)

### AL-F02 — Dead Anchor Links

**Status: AMBER — false positive on ampersand headings**

All three AL-F02 violations across both repos are **false positives** caused by the same bug.

**Root cause** (`agentlint/checks/dead_anchors.py`, `_to_slug()` function, line 47):

`python
# Current (buggy):
text = re.sub(r"[^\w\s-]", "", text)   # strips '&', leaves two spaces
text = re.sub(r"[\s_]+", "-", text)      # collapses spaces into ONE hyphen
`

When heading `Testing & Validation` is slugified:  
1. `&` is stripped → `"testing  validation"` (two spaces)  
2. `[\s_]+` collapse → `"testing-validation"` (single hyphen)

But GitHub's actual algorithm converts each space independently to a hyphen:  
`"testing  validation"` → `"testing--validation"` (double hyphen)

So the anchor `#testing--validation` in the markdown is **valid**, but the slug function produces `testing-validation` (single hyphen) and reports a mismatch.

**Affected violations:**

| Repo | File | Line | Anchor | Heading |
|------|------|------|--------|---------|
| arc42 | `CLAUDE.md` | 18 | `#testing--validation` | `## Testing & Validation` |
| arc42 | `CLAUDE.md` | 19 | `#git--deployment` | `## Git & Deployment` |
| nnsight | `CLAUDE.md` | 57 | `#development--testing-notes` | `## Development & Testing Notes` |

**Fix required:** In `_to_slug()`, replace each whitespace character with a hyphen individually (`re.sub(r"[\s_]", "-", text)`) instead of collapsing runs (`re.sub(r"[\s_]+", "-", text)`). Then optionally strip leading/trailing hyphens.

**Positive signal:** 22 clean anchors in nnsight CLAUDE.md passed without false positives. The check correctly validates well-formed anchors — the only issue is the `&`-to-double-hyphen edge case.

---

### AL-S01 — Secret Detection

**Status: GREEN — silent (correct)**

Zero firings across both repos. Neither repo contains credential-like values in instruction files. Silence on clean content is the expected behaviour.

---

### AL-INV01 — Inverse Capability Claims

**Status: GREEN — silent (correct)**

Zero firings. Neither repo uses negation-existence patterns (`"there is no X"`). After checking ~20 repos across the full stress suite, these patterns simply don't appear organically in real instruction files — authors document what IS present, not what isn't.

---

### AL-Q01 — Vague Instructions

**Status: GREEN**

Fired once on arc42 CLAUDE.md line 790: `"Follow best practices"`. The phrase is genuinely vague, even though sub-bullets add specifics. Zero firings on nnsight — its instruction file is notably precise and technical.

Positive: zero fires inside code blocks or examples across both repos.

---

### AL-N02 — Written Percentage Sourcing

**Status: GREEN — silent (correct)**

Zero firings. Neither repo uses written-out percentage phrases (`N percent`). Instruction files universally use `%` notation. Silence is expected.

---

### AL-D03 — Circular References

**Status: GREEN — silent (correct)**

Zero firings. No circular backtick-path references found. Completed in <1 second on both repos — DFS performance is fine.

---

### AL-TOK01 — Token Budget

**Status: GREEN — silent (correct, opt-in)**

Neither repo has `.agentlint.yml` with `token_budget` set. Check correctly stays silent.

---

### AL-D04 — Role Coverage

**Status: GREEN — silent (correct, opt-in)**

Neither repo has `.agentlint.yml` with `required_roles` set. Check correctly stays silent.

---

## 4. Other Checks Observed

| Check | Repo 4 (arc42) | Repo 5 (nnsight) | Assessment |
|-------|----------------|-------------------|------------|
| AL-D02 (Dispatch) | 8 fires — all 8 command files unreferenced from CLAUDE.md | 0 | GREEN — correct for ClaudeCode command structure |
| AL-F01 (File refs) | 5 fires — template/example paths in command docs | 0 | GREEN — legitimately broken refs (template Rust paths in a Ruby/Jekyll project) |

---

## 5. Verdict Table

`
+----------+--------+---------+---------+--------------------------------------+
| Check    | Fires? | FP Risk | Verdict | Notes                                |
+----------+--------+---------+---------+--------------------------------------+
| AL-S01   | No     | None    | GREEN   | Silent on clean repos (correct)      |
| AL-INV01 | No     | None    | GREEN   | Pattern doesn't occur in the wild    |
| AL-Q01   | Yes(1) | Low     | GREEN   | Fired on genuinely vague phrase      |
| AL-F02   | Yes(3) | HIGH    | AMBER   | ALL 3 fires are FPs (& slug bug)     |
| AL-N02   | No     | None    | GREEN   | Written % not used in instruction    |
| AL-D03   | No     | N/A     | GREEN   | Cycles don't occur; fast completion  |
| AL-TOK01 | No     | N/A     | GREEN   | Opt-in, correctly silent             |
| AL-D04   | No     | N/A     | GREEN   | Opt-in, correctly silent             |
+----------+--------+---------+---------+--------------------------------------+
`

---

## 6. Action Items

### Must Fix Before Release

1. **AL-F02 slug calculation bug** — `_to_slug()` in `agentlint/checks/dead_anchors.py` line 47.  
   Change `re.sub(r"[\s_]+", "-", text)` → `re.sub(r"[\s_]", "-", text)`  
   **Impact:** 100% of AL-F02 firings in this test batch are false positives caused by this bug.

### No Action Required

- AL-S01, AL-INV01, AL-Q01, AL-N02, AL-D03, AL-TOK01, AL-D04 — all behaving correctly in the wild.

---

## 7. Confidence Assessment

**These two repos: MEDIUM** — one AMBER finding (AL-F02 false positives).  
**Overall (if combined with repos 1–3): depends on full suite roll-up.**

The AL-F02 bug is a one-line fix with high confidence. Once patched, all checks would be GREEN across these repos.

---

*Report generated by the stress-test agent. No source code was modified during testing.*
