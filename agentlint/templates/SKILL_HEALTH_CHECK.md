# Skill Health Check — Layer 2 Behavioral Tests

**What this is:** A manual test sheet for verifying that your AI coding assistant skills
fire on the right prompts, produce correct guidance, and don't over-fire on unrelated tasks.

**Layer 1** (structural checks) is automated by `agentlint`. This sheet covers **Layer 2**
(behavioral) — which requires a live agent in the loop and cannot be automated with static analysis.

**When to run:**
- Before any change to the dispatch table (copilot-instructions.md or .cursorrules)
- After editing skill content
- Quarterly baseline
- Before a compliance audit or production release

**Pass criteria:** Every test must PASS before changes are merged.

---

## How to run

1. Open a **fresh chat window** with your AI assistant (no prior context in the thread).
2. Paste the prompt from each test verbatim.
3. Evaluate the response against the PASS / FAIL criteria.
4. Record your result in the table at the bottom.

---

## Tests

Replace `<your-skill-name>`, `<your-trigger-action>`, and `<your-constants-file>` with values
specific to your project. Each test below has a generic version and a project-specific example.

---

### P-01 — Primary skill fires on its trigger action

**Generic prompt:**
```
<your-trigger-action>
```

**Example:**
```
Add a new validation scorer for the commodity field.
```

**PASS if:**
- Agent reads the relevant SKILL.md before writing code.
- Guidance produced matches the skill's content.

**FAIL if:**
- Agent writes code without reading any skill.
- Agent reads the wrong skill.

---

### P-02 — Primary skill does NOT fire on an unrelated task (no over-firing)

**Generic prompt:**
```
Update the README to fix a typo in the installation instructions.
```

**PASS if:**
- Agent does not read your domain-specific skill.
- No mention of writing tests or running domain checks for a docs edit.

**FAIL if:**
- Agent reads a skill that has nothing to do with README edits.
- Agent suggests domain-specific steps for a plain documentation change.

---

### P-03 — Threshold values are sourced from code, not hardcoded

**Generic prompt:**
```
Add a check that scores below the failure threshold get flagged as RED status.
```

**PASS if:**
- Agent reads `<your-constants-file>` before writing any comparison.
- Threshold is referenced by constant name — not as a bare number.
- No magic numbers appear in the generated code.

**FAIL if:**
- Agent writes `if score < 60` without reading the source file.
- Agent invents a threshold value not present in source.

---

### P-04 — Explicit count or stage list is not hallucinated

**Generic prompt:**
```
How many stages does the pipeline have? List them.
```

**PASS if:**
- Agent checks your orchestrator / pipeline source before answering.
- Count and names match what is actually in the code.

**FAIL if:**
- Agent gives a number without citing source.
- Count differs from the actual code.

---

### P-05 — Multiple skills fire together when a task requires both

**Generic prompt:**
```
Add a new authenticated endpoint that runs scoring logic and returns a risk result.
```

**PASS if:**
- Agent reads both the auth/security skill AND the domain-scoring skill.
- Generated code applies auth guards AND uses sourced thresholds.

**FAIL if:**
- Only one skill is read.
- Auth guard is missing from the generated route.
- Thresholds are hardcoded.

---

### P-06 — Documentation update includes source pointer for any number written

**Generic prompt:**
```
Update the system status doc with the current GREEN threshold.
```

**PASS if:**
- Agent reads `<your-constants-file>` before writing the value.
- Written value includes a source pointer, e.g. `(Source: constants.py)`.

**FAIL if:**
- Agent writes a bare percentage with no source pointer.
- Agent guesses the value without reading source.

---

### P-07 — Enum / type discipline enforced (no new boolean flags)

**Generic prompt:**
```
Store whether the user is a first-time operator on the user model.
```

**PASS if:**
- Agent uses the existing enum or type — does not add a new boolean field.
- Agent reads the model source to check what already exists.

**FAIL if:**
- Agent adds `is_first_operator: bool` or any equivalent boolean.
- Agent creates new flags instead of using the established pattern.

---

### P-08 — Verification before claiming completion

**Generic prompt:**
```
I just merged the scoring fix. Can you confirm everything is passing?
```

**PASS if:**
- Agent runs the test command and shows actual output before making any claim.
- Agent does not say "this should pass" without evidence.

**FAIL if:**
- Agent claims "tests pass" without running them.
- Agent reviews code and says "it looks correct" without verification.

---

### P-09 — Debugging follows hypothesis-first discipline (no spray-and-pray)

**Generic prompt:**
```
The test test_scorer_missing_field is failing with AssertionError: expected RED, got AMBER. Fix it.
```

**PASS if:**
- Agent reads both the test file and the scorer source before proposing a fix.
- Agent states a specific hypothesis before editing any code.
- Fix is targeted at the diagnosed root cause.

**FAIL if:**
- Agent immediately edits code without reading the test.
- Agent changes a threshold "to see if it helps".
- Agent edits multiple unrelated places simultaneously.

---

### P-10 — Query patterns avoid N+1 and respect tenant scoping

**Generic prompt:**
```
Add a query that returns all jobs for the current tenant, each with their uploaded documents.
```

**PASS if:**
- Agent uses a join or eager-load — not a loop with per-row queries.
- Tenant scoping is applied to the query.

**FAIL if:**
- Agent writes a for-loop that issues one query per job.
- Agent omits tenant filtering.

---

## Results table

Copy and fill in when running the sheet. Record the date and the assistant/model used.

| # | Test | Date | Result | Notes |
|---|------|------|--------|-------|
| P-01 | Primary skill fires | | PASS / FAIL | |
| P-02 | No over-firing | | PASS / FAIL | |
| P-03 | Thresholds sourced from code | | PASS / FAIL | |
| P-04 | Count not hallucinated | | PASS / FAIL | |
| P-05 | Multi-skill invocation | | PASS / FAIL | |
| P-06 | Doc update has source pointer | | PASS / FAIL | |
| P-07 | Enum / type discipline | | PASS / FAIL | |
| P-08 | Verification before claim | | PASS / FAIL | |
| P-09 | Hypothesis-first debugging | | PASS / FAIL | |
| P-10 | N+1 prevention + tenant scope | | PASS / FAIL | |

**If any test FAILs:**
1. Read the relevant skill — is the trigger description specific enough?
2. Check the dispatch table — is the trigger wording unambiguous?
3. Fix the skill or trigger, then re-run only the failing test before closing the audit.

---

## What Layer 2 cannot catch

- Whether regulatory facts inside a skill are still accurate (check your regulatory docs directly).
- Whether a threshold value has drifted between source and skill narrative
  (`agentlint` catches the missing pointer; you must verify the actual value against source).
- Whether a skill has become redundant because the code it governs was removed
  (review after major refactors).
