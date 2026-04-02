from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class ContinueAdapter(BaseAdapter):
    """Handles Continue.dev instruction format:
    - .continuerules           (monolithic dispatch / global rules)
    - .continue/rules/*.md     (modular per-rule files)
    """

    name = "continue"

    def detect(self, root: Path) -> bool:
        return (root / ".continuerules").exists() or (
            root / ".continue" / "rules"
        ).is_dir()

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Monolithic .continuerules
        p = root / ".continuerules"
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

        # Modular .continue/rules/*.md
        rules_dir = root / ".continue" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.rglob("*.md")):
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
