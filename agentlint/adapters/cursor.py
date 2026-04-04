from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class CursorAdapter(BaseAdapter):
    """Handles Cursor instruction format:
    - .cursorrules           (monolithic dispatch / global rules)
    - .cursor/rules/*.mdc    (modular per-rule files)
    """

    name = "cursor"

    def detect(self, root: Path) -> bool:
        return (root / ".cursorrules").exists() or (root / ".cursor" / "rules").exists()

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Monolithic .cursorrules
        p = root / ".cursorrules"
        if p.exists():
            content, lines = self._read(p)
            files.append(
                InstructionFile(
                    path=p,
                    content=content,
                    lines=lines,
                    adapter=self.name,
                    role=Role.DISPATCH,
                    metadata={},
                )
            )

        # Modular .cursor/rules/*.mdc
        rules_dir = root / ".cursor" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.rglob("*.mdc")):
                content, lines = self._read(rule_file)
                meta = self._parse_frontmatter(content)
                files.append(
                    InstructionFile(
                        path=rule_file,
                        content=content,
                        lines=lines,
                        adapter=self.name,
                        role=Role.SKILL,
                        metadata=meta,
                    )
                )

        return files
