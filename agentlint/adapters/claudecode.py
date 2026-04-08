from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class ClaudeCodeAdapter(BaseAdapter):
    """Handles Claude Code instruction format:
    - CLAUDE.md                    (dispatch / global instructions)
    - .claude/agents/*.md          (sub-agent files)
    - .claude/commands/*.md        (slash-command definitions)
    """

    name = "claudecode"

    def detect(self, root: Path) -> bool:
        return (
            (root / "CLAUDE.md").exists()
            or (root / ".claude" / "agents").exists()
            or (root / ".claude" / "commands").exists()
        )

    def collect(self, root: Path) -> list[InstructionFile]:
        files: list[InstructionFile] = []

        # Primary instruction file (DISPATCH)
        dispatch_path = root / "CLAUDE.md"
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

        # Sub-agent files (.claude/agents/*.md — SKILL role)
        agents_dir = root / ".claude" / "agents"
        if agents_dir.exists():
            for agent_file in sorted(agents_dir.rglob("*.md")):
                content, lines = self._read(agent_file)
                meta = self._parse_frontmatter(content)
                files.append(
                    InstructionFile(
                        path=agent_file,
                        content=content,
                        lines=lines,
                        adapter=self.name,
                        role=Role.SKILL,
                        metadata=meta,
                    )
                )

        # Slash-command definitions (.claude/commands/*.md — SKILL role)
        commands_dir = root / ".claude" / "commands"
        if commands_dir.exists():
            for cmd_file in sorted(commands_dir.rglob("*.md")):
                content, lines = self._read(cmd_file)
                meta = self._parse_frontmatter(content)
                files.append(
                    InstructionFile(
                        path=cmd_file,
                        content=content,
                        lines=lines,
                        adapter=self.name,
                        role=Role.SKILL,
                        metadata=meta,
                    )
                )

        return files
