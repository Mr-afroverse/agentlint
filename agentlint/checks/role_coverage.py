"""
AL-D04  Role coverage completeness.

Verifies that every role declared in ``required_roles`` config has at least
one SKILL file on disk.  A skill's role name is derived from its ``name``
frontmatter field, falling back to the skill file's parent directory name.

Example .agentlint.yml:
    required_roles:
      - eudr-standards
      - security
      - testing

If no SKILL file matches the role name, an error is raised on the dispatch
file (or the repo root if no dispatch file is present).
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
    violations: list[Violation] = []

    if not config.required_roles:
        return violations

    skill_names: set[str] = {
        sf.metadata.get("name", sf.path.parent.name)
        for sf in files
        if sf.role == Role.SKILL
    }

    dispatch_files = [f for f in files if f.role == Role.DISPATCH]
    report_file = dispatch_files[0].path if dispatch_files else (root / ".")

    for role in config.required_roles:
        if role not in skill_names:
            violations.append(
                Violation(
                    check_id="AL-D04",
                    severity=Severity.ERROR,
                    file=report_file,
                    line=None,
                    message=f"Required role `{role}` has no matching SKILL file.",
                    fix_hint=(
                        f"Create a SKILL file whose `name` frontmatter or parent "
                        f"directory is `{role}`."
                    ),
                )
            )

    return violations
