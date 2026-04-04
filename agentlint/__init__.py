from __future__ import annotations

from pathlib import Path

__version__ = "0.3.0"
__all__ = ["__version__"]

# Bundled templates directory — used by `agentlint init` to copy SKILL_HEALTH_CHECK.md
TEMPLATES_DIR = Path(__file__).parent / "templates"
