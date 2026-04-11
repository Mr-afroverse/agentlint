from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class CopilotAdapter(BaseAdapter):
    """Handles GitHub Copilot instruction format:
    - .github/copilot-instructions.md      (dispatch)
    - .github/instructions/*.md            (per-file instructions, VS Code 1.99+)
    - .github/skills/**/SKILL.md           (individual skills)
    """

    name = "copilot"
    _DISPATCH_NAME = "copilot-instructions.md"
    _SKILL_FILENAME = "SKILL.md"

    def detect(self, root: Path) -> bool:
        return (
            (root / ".github" / self._DISPATCH_NAME).exists()
            or (root / ".github" / "skills").exists()
            or (root / ".github" / "instructions").exists()
        )

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Dispatch file
        dispatch_path = root / ".github" / self._DISPATCH_NAME
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

        # Per-file instruction files (.github/instructions/*.md — VS Code 1.99+ format)
        instructions_dir = root / ".github" / "instructions"
        if instructions_dir.exists():
            for instr_file in sorted(instructions_dir.rglob("*.md")):
                content, lines = self._read(instr_file)
                meta = self._parse_frontmatter(content)
                files.append(
                    InstructionFile(
                        path=instr_file,
                        content=content,
                        lines=lines,
                        adapter=self.name,
                        role=Role.SKILL,
                        metadata=meta,
                    )
                )

        # Skill files
        skills_dir = root / ".github" / "skills"
        if skills_dir.exists():
            for skill_file in sorted(skills_dir.rglob(self._SKILL_FILENAME)):
                # Skip the health-check document itself — it intentionally
                # contains patterns that would trigger false positives.
                if skill_file.name == "SKILL_HEALTH_CHECK.md":
                    continue
                content, lines = self._read(skill_file)
                meta = self._parse_frontmatter(content)
                files.append(
                    InstructionFile(
                        path=skill_file,
                        content=content,
                        lines=lines,
                        adapter=self.name,
                        role=Role.SKILL,
                        metadata=meta,
                    )
                )

        return files
