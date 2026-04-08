"""
AL-TOK01  Instruction file token budget.

Warns when an instruction file's estimated token count exceeds the configured
budget.  Token count is approximated as ``len(content) / 4`` — the standard
OpenAI heuristic (≈4 characters per token on average English prose).  No
external dependencies required.

Activated via `.agentlint.yml`:

    token_budget: 2000        # warn when any instruction file exceeds 2000 tokens

Set to 0 (default) to disable the check entirely.

The check runs on SKILL and DISPATCH files.  DOCS files are intentionally
excluded — they are reference documents, not AI instruction files, and token
cost applies differently.
"""

from __future__ import annotations

from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation


def _estimate_tokens(content: str) -> int:
    """Approximate token count: 1 token ≈ 4 characters (OpenAI heuristic)."""
    return max(1, len(content) // 4)


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    if not config.token_budget:
        return []

    violations: list[Violation] = []

    for f in [f for f in files if f.role in (Role.SKILL, Role.DISPATCH)]:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        estimated = _estimate_tokens(f.content)
        if estimated > config.token_budget:
            violations.append(
                Violation(
                    check_id="AL-TOK01",
                    severity=Severity.WARNING,
                    file=f.path,
                    line=None,
                    message=(
                        f"Estimated token count ({estimated}) exceeds budget "
                        f"({config.token_budget}). Large instruction files "
                        "increase cost and may degrade agent focus."
                    ),
                    fix_hint=(
                        "Split this file into smaller, focused skill files, "
                        "or remove redundant content to reduce token count."
                    ),
                )
            )

    return violations
