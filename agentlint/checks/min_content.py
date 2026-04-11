"""
AL-LEN01  SKILL files with very little content are likely accidental stubs.

Token count is approximated as ``len(content) / 4`` (same heuristic as
AL-TOK01).  The threshold is controlled by ``min_content_tokens`` in config
(default: 10 tokens ≈ 40 characters).  Set to 0 to disable.

Only runs on SKILL files — DISPATCH and DOCS files can legitimately be brief.
"""

from __future__ import annotations

from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    if not config.min_content_tokens:
        return []

    violations: list[Violation] = []

    for f in [_f for _f in files if _f.role == Role.SKILL]:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        estimated = max(1, len(f.content) // 4)
        if estimated < config.min_content_tokens:
            violations.append(
                Violation(
                    check_id="AL-LEN01",
                    severity=Severity.WARNING,
                    file=f.path,
                    line=None,
                    message=(
                        f"SKILL file has very little content (estimated "
                        f"{estimated} token(s), minimum is "
                        f"{config.min_content_tokens}). Likely an accidental stub."
                    ),
                    fix_hint=(
                        "Add substantive instructions or remove the file if it "
                        "is no longer needed."
                    ),
                )
            )

    return violations
