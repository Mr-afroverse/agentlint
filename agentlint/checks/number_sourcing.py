"""
AL-N01  Lines in skill files that contain threshold / percentage numbers should
        carry a source pointer so future readers know where the value came from.

A source pointer is satisfied when:
  a) The same line matches any configured source marker, OR
  b) The line is a table row (|…) or blockquote (>…) AND a source marker
     appears within `number_source_lookback` lines above it.

Lines inside fenced code blocks (``` … ```) are always skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

# Matches percentage values and comparison operators with percentages.
# Intentionally does NOT match bare `≥ N` or `≤ N` without `%` — those are
# non-scoring values (connection counts, process limits, etc.).
_THRESHOLD_RE = re.compile(
    r"\b\d+\s*%"  # "90%", "90 %"
    r"|[≥≤]\s*\d+(?:\.\d+)?\s*%"  # "≥ 90%", "≤ 3.0%"
    r"|(?<![a-zA-Z])[<>]=?\s*\d+\s*%"  # "< 60%", ">= 80%"
)

# Exactly 3 backticks at start of line — opening/closing a code fence.
_CODE_FENCE_RE = re.compile(r"^```(?!`)")


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    source_re = re.compile("|".join(config.source_markers), re.IGNORECASE)
    lookback = config.number_source_lookback
    violations: list[Violation] = []

    for sf in [f for f in files if f.role == Role.SKILL]:
        lines = sf.lines
        in_code = False

        for lineno, line in enumerate(lines, start=1):
            # Track code fence state
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code
            if in_code:
                continue

            if not _THRESHOLD_RE.search(line):
                continue
            if source_re.search(line):
                continue

            # For table rows and blockquotes: check the preceding N lines
            stripped = line.lstrip()
            if stripped.startswith("|") or stripped.startswith(">"):
                lb_start = max(0, lineno - 1 - lookback)
                lb_text = "\n".join(lines[lb_start : lineno - 1])
                if source_re.search(lb_text):
                    continue

            violations.append(
                Violation(
                    check_id="AL-N01",
                    severity=Severity.WARNING,
                    file=sf.path,
                    line=lineno,
                    message=f"Threshold number without source pointer: `{line.strip()[:100]}`",
                    fix_hint=(
                        "Add a source pointer on this line, e.g. '(Source: constants.py)', "
                        "'(Article 9, Regulation 2023/1115)', or '(heuristic)'."
                    ),
                )
            )

    return violations
