from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class WindsurfAdapter(BaseAdapter):
    """Handles Windsurf instruction format:
    - .windsurfrules              (monolithic dispatch / global rules)
    - .windsurf/rules/*.md        (modular per-rule files, Windsurf convention)
    """

    name = "windsurf"

    def detect(self, root: Path) -> bool:
        return (root / ".windsurfrules").exists() or (
            root / ".windsurf" / "rules"
        ).exists()

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Monolithic .windsurfrules
        p = root / ".windsurfrules"
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

        # Modular .windsurf/rules/*.md
        rules_dir = root / ".windsurf" / "rules"
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
