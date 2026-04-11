"""
AL-FM01  SKILL file frontmatter must contain all required keys.

Configured via ``required_frontmatter`` in ``.agentlint.yml``.  Disabled by
default (empty list) because required fields vary by adapter and project
convention.

Example configuration::

    required_frontmatter:
      - name
      - description

Files with no frontmatter at all are treated as if they have empty metadata —
all required keys are reported as missing.

Only runs on SKILL files.
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
    if not config.required_frontmatter:
        return []

    violations: list[Violation] = []

    for f in [_f for _f in files if _f.role == Role.SKILL]:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        missing = [key for key in config.required_frontmatter if key not in f.metadata]
        if missing:
            missing_fmt = ", ".join(f"`{k}`" for k in missing)
            violations.append(
                Violation(
                    check_id="AL-FM01",
                    severity=Severity.WARNING,
                    file=f.path,
                    line=1,
                    message=(
                        f"SKILL file is missing required frontmatter "
                        f"key(s): {missing_fmt}."
                    ),
                    fix_hint=(
                        "Add the missing key(s) to the frontmatter block at the "
                        "top of the file (either `---` YAML or ````skill` block)."
                    ),
                )
            )

    return violations
