from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class GeminiAdapter(BaseAdapter):
    """Handles Google Gemini CLI instruction format:
    - GEMINI.md                    (dispatch / global instructions)
    - .gemini/rules/*.md           (per-topic rule files)
    """

    name = "gemini"

    def detect(self, root: Path) -> bool:
        return (root / "GEMINI.md").exists() or (root / ".gemini" / "rules").exists()

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Primary instruction file (DISPATCH)
        dispatch_path = root / "GEMINI.md"
        if dispatch_path.exists():
            content, lines = self._read(dispatch_path)
            files.append(
                InstructionFile(
                    path=dispatch_path,
                    content=content,
                    lines=lines,
                    adapter=self.name,
                    role=Role.DISPATCH,
                    metadata={},
                )
            )

        # Per-topic rule files (.gemini/rules/*.md — SKILL role)
        rules_dir = root / ".gemini" / "rules"
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
