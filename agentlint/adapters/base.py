from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

import yaml

from agentlint.models import InstructionFile


class BaseAdapter(ABC):
    name: str = "generic"

    @abstractmethod
    def detect(self, root: Path) -> bool:
        """Return True if this adapter's instruction format is present in *root*."""
        ...

    @abstractmethod
    def collect(self, root: Path) -> list[InstructionFile]:
        """Collect and normalise all instruction files for this adapter."""
        ...

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _read(path: Path) -> tuple[str, list[str]]:
        content = path.read_text(encoding="utf-8", errors="replace")
        return content, content.splitlines()

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Extract YAML frontmatter from either:
        - ````skill\\n---\\n...\\n---` (4-backtick fenced skill block), or
        - Standard `---\\n...\\n---` frontmatter.
        """
        # 4-backtick fenced skill block (GitHub Copilot SKILL.md format)
        m = re.search(
            r"^````skill\s*\n---\n(.*?)\n---",
            content,
            re.DOTALL | re.MULTILINE,
        )
        if m:
            try:
                return yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                pass

        # Standard frontmatter
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if m:
            try:
                return yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                pass

        return {}
