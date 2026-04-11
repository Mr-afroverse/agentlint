"""
AL-DEP*  User-supplied deprecated pattern scanning.

Projects configure a list of deprecated AI provider API patterns (model names,
SDK method signatures, API endpoints) that should no longer be referenced in
instruction files.  Each entry is compiled as a Python regex.

Example .agentlint.yml::

    deprecated_patterns:
      - pattern: "gpt-4-0613"
        reason: "Model deprecated by OpenAI."
        replacement: "gpt-4o"
      - pattern: "openai\\.ChatCompletion\\.create"
        reason: "openai v0.x API — removed in v1.0."
        replacement: "client.chat.completions.create"

Each entry may have:
  pattern:      (required) Python regex.
  reason:       (optional) Human-readable explanation.
  replacement:  (optional) What to use instead.
  severity:     (optional) "error" or "warning" (default: warning).
  id:           (optional) Custom check ID (default: AL-DEP<n>).
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    if not config.deprecated_patterns:
        return []

    violations: list[Violation] = []

    # Pre-compile patterns once — avoids recompiling per file.
    compiled: list[tuple[str, str, str, str, re.Pattern[str], Severity]] = []
    for idx, entry in enumerate(config.deprecated_patterns, start=1):
        raw_pattern = entry.get("pattern", "")
        if not raw_pattern:
            continue
        try:
            pat = re.compile(raw_pattern)
        except re.error as exc:
            import sys

            print(
                f"[agentlint] Warning: invalid regex in deprecated_patterns "
                f"(entry {idx}): {exc}",
                file=sys.stderr,
            )
            continue  # bad regex in user config
        check_id = entry.get("id") or f"AL-DEP{idx:02d}"
        reason = entry.get("reason", "Deprecated pattern matched.")
        replacement = entry.get("replacement", "")
        fix_hint = f"Replace with: {replacement}" if replacement else ""
        try:
            severity = Severity(entry.get("severity", "warning"))
        except ValueError:
            severity = Severity.WARNING
        compiled.append((check_id, reason, fix_hint, replacement, pat, severity))

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        for check_id, reason, fix_hint, replacement, pat, severity in compiled:
            for lineno, line in enumerate(f.lines, start=1):
                if pat.search(line):
                    if replacement:
                        new_line = pat.sub(replacement, line)
                        auto_fixable = True
                        fix_data: dict = {"old_line": line, "new_line": new_line}
                    else:
                        auto_fixable = False
                        fix_data = {}
                    violations.append(
                        Violation(
                            check_id=check_id,
                            severity=severity,
                            file=f.path,
                            line=lineno,
                            message=reason,
                            fix_hint=fix_hint,
                            auto_fixable=auto_fixable,
                            fix_data=fix_data,
                        )
                    )

    return violations
