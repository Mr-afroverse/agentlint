"""
AL-D01  Skill path referenced in dispatch table → must exist on disk.
AL-D02  SKILL file on disk → must be referenced in dispatch table.
AL-D05  Two or more SKILL files share the same effective name → one will
        silently shadow the other in role_coverage checks.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

# Matches backtick-quoted paths that look like skill files, e.g.:
#   `.github/skills/eudr-standards/SKILL.md`
#   `.cursor/rules/my-rule.mdc`
_SKILL_PATH_RE = re.compile(r"`([^`]+/(?:SKILL\.md|[^`]+\.mdc))`")


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    dispatch_files = [f for f in files if f.role == Role.DISPATCH]
    skill_files = [f for f in files if f.role == Role.SKILL]

    # ---------------------------------------------------------------- AL-D05
    # Duplicate skill names — runs regardless of dispatch presence.
    if len(skill_files) >= 2:
        name_to_files: dict[str, list[InstructionFile]] = {}
        for sf in skill_files:
            skill_name = sf.metadata.get("name", sf.path.parent.name)
            name_to_files.setdefault(skill_name, []).append(sf)
        for skill_name, dupes in name_to_files.items():
            if len(dupes) > 1:
                for sf in dupes:
                    violations.append(
                        Violation(
                            check_id="AL-D05",
                            severity=Severity.ERROR,
                            file=sf.path,
                            line=1,
                            message=(
                                f"Duplicate skill name `{skill_name}` across "
                                f"{len(dupes)} SKILL files — one will shadow "
                                "the other in role coverage."
                            ),
                            fix_hint=(
                                "Give each skill a unique `name` in its frontmatter "
                                "or rename its parent directory."
                            ),
                        )
                    )

    if not dispatch_files:
        return violations

    dispatch = dispatch_files[0]

    # ---------------------------------------------------------------- AL-D01
    for m in _SKILL_PATH_RE.finditer(dispatch.content):
        rel = m.group(1)
        if not (root / rel).exists():
            violations.append(
                Violation(
                    check_id="AL-D01",
                    severity=Severity.ERROR,
                    file=dispatch.path,
                    line=_line_of(dispatch.content, m.start()),
                    message=f"Skill path not found on disk: `{rel}`",
                    fix_hint="Create the file or correct the path in the dispatch table.",
                )
            )

    # ---------------------------------------------------------------- AL-D02
    dispatch_text = dispatch.content
    for sf in skill_files:
        rel = sf.path.relative_to(root).as_posix()
        # VS Code 1.99+ auto-discovers .github/skills/** via XML <skill> injection —
        # no manual dispatch entry is needed or expected for these files.
        if rel.startswith(".github/skills/"):
            continue
        if rel not in dispatch_text:
            skill_name = sf.metadata.get("name", sf.path.parent.name)
            violations.append(
                Violation(
                    check_id="AL-D02",
                    severity=Severity.ERROR,
                    file=sf.path,
                    line=1,
                    message=(
                        f"Skill `{skill_name}` (`{rel}`) is not referenced in "
                        f"the dispatch file."
                    ),
                    fix_hint=(
                        f"Add an entry for `{rel}` in the dispatch table with "
                        f"a trigger description."
                    ),
                )
            )

    return violations


def _line_of(content: str, offset: int) -> int:
    return content[:offset].count("\n") + 1
