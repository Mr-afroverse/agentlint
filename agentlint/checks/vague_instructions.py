"""
AL-Q01  Vague instruction detection.

Flags lines in instruction files that contain structurally vague phrases
which give the AI agent no actionable guidance.  Examples:

  "write clean code"          — what *is* clean? no measurable criterion
  "be helpful"                — meaningless without context of what help means
  "follow best practices"     — which practices, in which domain?
  "make it work properly"     — no definition of "properly"

The check runs on SKILL and DISPATCH files.  Lines inside fenced code blocks
are skipped.  Violations are warnings — false positives are possible on lines
that discuss *why* vague instructions are bad, or in examples.

Users can suppress individual violations with `ignore_paths` or by adding an
inline comment like `# agentlint: disable=AL-Q01`.

Source: competitive landscape research (cursor-doctor 48-pattern catalogue,
AgentLinter, ai-context-kit), and EU EU compliance pipeline feedback-v3.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation
from agentlint.checks._utils import _CODE_FENCE_RE

# ---------------------------------------------------------------------------
# Vague-phrase pattern catalogue.
# Each entry: (pattern_re_string, readable_label)
# Patterns are matched case-insensitively against full lines.
# ---------------------------------------------------------------------------
_VAGUE_PATTERNS: list[tuple[str, str]] = [
    # Generic quality adjectives without criteria
    (r"\bwrite\s+clean\s+code\b", "write clean code"),
    (r"\bclean\s+code\b", "clean code"),
    (r"\bwrite\s+good\s+code\b", "write good code"),
    (r"\bproduce\s+(?:high[- ]quality|quality)\s+code\b", "produce quality code"),
    # "Best practices" family
    (r"\bfollow\s+(?:the\s+)?best\s+practices?\b", "follow best practices"),
    (r"\buse\s+(?:the\s+)?best\s+practices?\b", "use best practices"),
    (r"\badhere\s+to\s+best\s+practices?\b", "adhere to best practices"),
    (r"\bapply\s+best\s+practices?\b", "apply best practices"),
    # "Be helpful / professional / polite" family
    (r"\bbe\s+helpful\b", "be helpful"),
    (r"\bbe\s+polite\b", "be polite"),
    (r"\bbe\s+professional\b", "be professional"),
    (r"\bbe\s+friendly\b", "be friendly"),
    (r"\bbe\s+concise(?!\s*,|\s+but\b)", "be concise"),
    (r"\bbe\s+thorough\b", "be thorough"),
    # "Make it work" / undefined outcomes
    (r"\bmake\s+it\s+work\s+(?:properly|correctly|well)\b", "make it work properly"),
    (r"\bmake\s+sure\s+it\s+works?\b", "make sure it works"),
    (
        r"\bensure\s+(?:it\s+)?(?:works?|functions?)\s+(?:properly|correctly|well)\b",
        "ensure it works properly",
    ),
    # Effort-based non-instructions
    (r"\bdo\s+your\s+best\b", "do your best"),
    (r"\btry\s+(?:your\s+)?(?:best|hard(?:est)?)\b", "try your best/hardest"),
    (r"\bmake\s+(?:a\s+)?(?:good|best)\s+(?:effort|attempt)\b", "make a good effort"),
    # "Appropriately / properly / correctly" without definition
    (
        r"\bhandle\s+(?:it|errors?|exceptions?|cases?)\s+appropriately\b",
        "handle appropriately",
    ),
    (
        r"\bdo\s+(?:it|this|that)\s+(?:properly|correctly|appropriately)\b",
        "do it properly",
    ),
    # "As needed / as necessary / as required" without criteria
    (r"\bas\s+needed\b", "as needed"),
    (r"\bas\s+necessary\b", "as necessary"),
    (r"\bas\s+required\b", "as required"),
    (r"\bwhen\s+appropriate\b", "when appropriate"),
    # "Improve", "optimise", "enhance" without metrics
    (
        r"\bimprove\s+(?:the\s+)?(?:code|performance|quality|it)\s+(?:as\s+needed|where\s+possible|appropriately)\b",
        "improve as needed",
    ),
    (
        r"\boptimis[ez]\s+(?:the\s+)?(?:code|performance|it)\s+(?:as\s+needed|where\s+possible|appropriately)\b",
        "optimise as needed",
    ),
    # "Use common sense"
    (r"\buse\s+common\s+sense\b", "use common sense"),
    (r"\bexercise\s+(?:good\s+)?judgment\b", "exercise judgment"),
    # "Always do the right thing"
    (r"\bdo\s+the\s+right\s+thing\b", "do the right thing"),
    (r"\buse\s+your\s+best\s+judgment\b", "use your best judgment"),
    # Generic "follow the existing style/pattern"
    (
        r"\bfollow\s+(?:the\s+)?existing\s+(?:style|pattern|conventions?|code)\b",
        "follow existing style",
    ),
    (
        r"\bmatch\s+(?:the\s+)?(?:existing\s+)?(?:style|pattern|code\s+style)\b",
        "match the style",
    ),
    # "Make it readable / maintainable" without criteria
    (
        r"\bmake\s+(?:it|the\s+code)\s+(?:readable|maintainable|understandable)\b",
        "make it readable",
    ),
]

# Compile all patterns upfront
_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pat, re.IGNORECASE), label) for pat, label in _VAGUE_PATTERNS
]

# Inline disable comment
_DISABLE_RE = re.compile(r"agentlint:\s*disable\s*=\s*AL-Q01", re.IGNORECASE)


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for f in [_f for _f in files if _f.role in (Role.SKILL, Role.DISPATCH)]:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        in_code = False
        for lineno, line in enumerate(f.lines, start=1):
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code
            if in_code:
                continue
            if _DISABLE_RE.search(line):
                continue

            for pattern, label in _COMPILED:
                if pattern.search(line):
                    violations.append(
                        Violation(
                            check_id="AL-Q01",
                            severity=Severity.WARNING,
                            file=f.path,
                            line=lineno,
                            message=(
                                f'Vague instruction detected: "{label}". '
                                "This gives the agent no actionable criterion."
                            ),
                            fix_hint=(
                                "Replace with a specific, measurable instruction. "
                                f'E.g. instead of "{label}", specify the exact '
                                "standard, threshold, or behaviour expected."
                            ),
                        )
                    )
                    break  # one violation per line — report the first match

    return violations
