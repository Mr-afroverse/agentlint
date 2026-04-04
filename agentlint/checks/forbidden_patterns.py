"""
AL-P*   Configurable forbidden pattern scanning.

Ships with a small set of universal defaults (see config.py DEFAULT_FORBIDDEN).
Projects extend these via .agentlint.yml without replacing the defaults.

Paths matching any entry in config.ignore_paths are silently skipped.
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
    violations: list[Violation] = []

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        for pattern_def in config.forbidden_patterns:
            try:
                pat = re.compile(pattern_def["pattern"])
            except re.error:
                continue  # bad regex in user config — skip silently

            try:
                severity = Severity(pattern_def.get("severity", "error"))
            except ValueError:
                severity = Severity.ERROR

            for lineno, line in enumerate(f.lines, start=1):
                if pat.search(line):
                    violations.append(
                        Violation(
                            check_id=pattern_def.get("id", "AL-P"),
                            severity=severity,
                            file=f.path,
                            line=lineno,
                            message=pattern_def.get(
                                "reason", "Forbidden pattern matched."
                            ),
                            fix_hint=pattern_def.get("fix", ""),
                        )
                    )

    return violations
