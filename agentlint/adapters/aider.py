from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class AiderAdapter(BaseAdapter):
    """Handles Aider instruction format:
    - .aider.conf.yml          (global config / dispatch)
    - .aider/rules/*.md        (modular convention files)
    """

    name = "aider"

    def detect(self, root: Path) -> bool:
        return (root / ".aider.conf.yml").exists() or (
            root / ".aider" / "rules"
        ).is_dir()

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Monolithic .aider.conf.yml
        p = root / ".aider.conf.yml"
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

        # Modular .aider/rules/*.md
        rules_dir = root / ".aider" / "rules"
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
