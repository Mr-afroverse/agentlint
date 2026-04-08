"""
AL-INV01  Inverse capability claim verification.

Flags documentation lines that make a negative existence claim about a path
while the backtick-referenced path actually exists on disk.

Trigger examples (file exists on disk, doc claims it doesn't):
    There is no `agents/alerter.py` in this system.
    This repo does not have `config/auth.py`.
    `app/audit_log.py` is not implemented in this project.
    `src/alerting.py` is not supported.

Not triggered:
    Lines where the referenced path genuinely does not exist on disk.
    Backtick tokens with no directory separator and no file extension.
    Lines with no negation indicator.

Source: EU Compliance Pipeline feedback-v3 §4 Gap 6.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation

# Negation indicator that PRECEDES a backtick path reference on the same line.
# Covers: "no", "there is no", "does not have/include/contain/implement/provide/support",
#         and the contracted "doesn't ..." forms.
_NEG_BEFORE_RE = re.compile(
    r"(?i)\b(?:"
    r"no\b"
    r"|there\s+is\s+no\b"
    r"|does?\s+not\s+(?:have|include|contain|implement|provide|support)\b"
    r"|doesn?'?t\s+(?:have|include|contain|implement|provide|support)\b"
    r")"
)

# Negation indicator that FOLLOWS a backtick path reference on the same line.
# Covers: "is not implemented/supported/present/available/included/found/there",
#         "isn't ...", "does not exist", "doesn't exist", "not implemented/..."
_NEG_AFTER_RE = re.compile(
    r"(?i)\b(?:"
    r"is\s+not\s+(?:implemented|supported|present|available|included|found|there)\b"
    r"|isn?'?t\s+(?:implemented|supported|present|available|included|found|there)\b"
    r"|does?\s+not\s+exist\b"
    r"|doesn?'?t\s+exist\b"
    r"|not\s+(?:implemented|supported|present|available|included|found)\b"
    r")"
)

# Backtick-quoted inline code token.
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")


def _looks_like_path(token: str) -> bool:
    """True when the token resembles a file system path (has separator or extension)."""
    return "/" in token or "\\" in token or bool(re.search(r"\.[a-zA-Z]{1,8}$", token))


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        for lineno, line in enumerate(f.lines, start=1):
            neg_before = list(_NEG_BEFORE_RE.finditer(line))
            neg_after = list(_NEG_AFTER_RE.finditer(line))
            if not (neg_before or neg_after):
                continue

            for m in _BACKTICK_RE.finditer(line):
                token = m.group(1).strip()
                if not _looks_like_path(token):
                    continue

                path_start = m.start()
                path_end = m.end()
                # NEG_BEFORE pattern: the negation phrase must end before the
                # backtick path starts (negation → path ordering on the line).
                before_hit = any(nb.end() <= path_start for nb in neg_before)
                # NEG_AFTER pattern: the negation phrase must start after the
                # backtick path ends (path → negation ordering on the line).
                after_hit = any(na.start() >= path_end for na in neg_after)
                if not (before_hit or after_hit):
                    continue

                if (root / token).exists():
                    violations.append(
                        Violation(
                            check_id="AL-INV01",
                            severity=Severity.WARNING,
                            file=f.path,
                            line=lineno,
                            message=(
                                f"Inverse capability claim: `{token}` is claimed "
                                f"absent but exists on disk."
                            ),
                            fix_hint=(
                                f"Update the documentation — `{token}` exists. "
                                "Correct the claim or remove/rename the file."
                            ),
                        )
                    )

    return violations
