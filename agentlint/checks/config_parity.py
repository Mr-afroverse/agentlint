"""
AL-E01  Keys present in a source config file must also appear in its template.

Typical use: `.env` vs `.env.example` — every key the application needs at
runtime should be documented in the template so new developers can set up
the project without guessing.

Configured via `.agentlint.yml`:

    config_parity:
      - source: "config/.env"
        template: "config/.env.example"
        exclude_keys: ["SECRET_THAT_SHOULD_NOT_BE_IN_TEMPLATE"]
        severity: error
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation

# Matches KEY=… lines, optionally prefixed by `export `.
_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _extract_keys(path: Path) -> set[str]:
    """Return the set of environment-variable key names defined in *path*."""
    keys: set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = _KEY_RE.match(stripped)
            if m:
                keys.add(m.group(1))
    except OSError:
        pass
    return keys


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for rule in config.config_parity:
        source_rel = rule.get("source", "")
        template_rel = rule.get("template", "")
        if not source_rel or not template_rel:
            continue

        source_path = root / source_rel
        template_path = root / template_rel

        if not source_path.is_file() or not template_path.is_file():
            continue

        exclude: set[str] = set(rule.get("exclude_keys", []))
        severity = Severity(rule.get("severity", "error"))

        source_keys = _extract_keys(source_path) - exclude
        template_keys = _extract_keys(template_path)

        missing = sorted(source_keys - template_keys)
        for key in missing:
            violations.append(
                Violation(
                    check_id="AL-E01",
                    severity=severity,
                    file=template_path,
                    line=None,
                    message=(
                        f"Key `{key}` exists in `{source_rel}` but is missing "
                        f"from `{template_rel}`."
                    ),
                    fix_hint=f"Add `{key}=` to `{template_rel}`.",
                )
            )

    return violations
