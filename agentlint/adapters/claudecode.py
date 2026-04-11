from __future__ import annotations

from pathlib import Path

from agentlint.adapters.base import BaseAdapter
from agentlint.models import InstructionFile, Role


class ClaudeCodeAdapter(BaseAdapter):
    """Handles Claude Code instruction format:
    - CLAUDE.md                    (dispatch / global instructions)
    - <subdir>/CLAUDE.md           (per-directory instructions, Claude Code v1.0+)
    - .claude/agents/*.md          (sub-agent files)
    - .claude/commands/*.md        (slash-command definitions)
    - .claude/rules/*.md           (rules/instruction files)
    """

    name = "claudecode"

    def detect(self, root: Path) -> bool:
        return (
            (root / "CLAUDE.md").exists()
            or (root / ".claude" / "agents").exists()
            or (root / ".claude" / "commands").exists()
            or (root / ".claude" / "rules").exists()
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

        # Per-directory CLAUDE.md files (subdirectories only — Claude Code v1.0+)
        for nested in sorted(root.rglob("CLAUDE.md")):
            if nested == dispatch_path:
                continue  # root CLAUDE.md already handled as DISPATCH
            content, lines = self._read(nested)
            meta = self._parse_frontmatter(content)
            files.append(
                InstructionFile(
                    path=nested,
                    content=content,
                    lines=lines,
                    adapter=self.name,
                    role=Role.SKILL,
                    metadata=meta,
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

        # Rules files (.claude/rules/*.md — SKILL role)
        rules_dir = root / ".claude" / "rules"
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
