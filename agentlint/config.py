from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Built-in forbidden patterns — codebase-agnostic defaults that ship with
# the tool. Projects can add their own in .agentlint.yml.
# ---------------------------------------------------------------------------
DEFAULT_FORBIDDEN: list[dict] = [
    {
        "id": "AL-P01",
        # Matches "1338 tests passing" but NOT when followed by a live-count pointer
        # OR when it appears as a bad-example annotation (line contains " ←").
        "pattern": r"\b\d{3,5} tests? pass(ing|ed)\b(?!.*(?:pytest|run|command|←|✅))",
        "reason": "Hardcoded test counts become stale immediately.",
        "fix": "Replace with: run your test command for the live count.",
        "severity": "error",
    },
]

# ---------------------------------------------------------------------------
# Built-in source markers — patterns that count as a valid source pointer.
# Projects add their own via config; these are the universal defaults.
# ---------------------------------------------------------------------------
DEFAULT_SOURCE_MARKERS: list[str] = [
    r"[Ss]ource[:\s]",
    r"[Ss]ee `",
    r"[Aa]rticle\s+\d",
    r"heuristic",
    r"\.py\b",
    r"read `",
    r"→ read",
    r"run `",
]


@dataclass
class Config:
    # ------------------------------------------------------------------ paths
    instruction_dirs: list[str] = field(
        default_factory=lambda: [".github/skills", ".cursor/rules"]
    )
    dispatch_files: list[str] = field(
        default_factory=lambda: [
            ".github/copilot-instructions.md",
            ".cursorrules",
            ".windsurfrules",
        ]
    )
    # Where to look when resolving source file references like `app/services/foo.py`
    source_roots: list[str] = field(default_factory=lambda: [".", "src"])

    # ---------------------------------------------------------- check toggles
    checks: dict[str, bool] = field(
        default_factory=lambda: {
            "dispatch-coverage": True,
            "file-references": True,
            "number-sourcing": True,
            "trigger-overlap": True,
            "forbidden-patterns": True,
        }
    )

    # --------------------------------------------------------- check settings
    number_source_lookback: int = 15
    # Jaccard similarity threshold for trigger overlap (0.0 – 1.0)
    trigger_overlap_threshold: float = 0.5

    # ------------------------------------------------------- source / pattern
    # Project-specific markers that count as valid source pointers
    source_markers: list[str] = field(
        default_factory=lambda: list(DEFAULT_SOURCE_MARKERS)
    )
    forbidden_patterns: list[dict] = field(
        default_factory=lambda: list(DEFAULT_FORBIDDEN)
    )
    # "extend" (default) — user patterns are added after defaults
    # "replace" — user patterns replace defaults entirely
    forbidden_patterns_mode: str = "extend"

    # ------------------------------------------------------------ reporting
    output_format: str = "text"  # "text" | "json" | "sarif" | "badge"
    fail_on_warnings: bool = False

    # -------------------------------------------------- severity overrides
    # Map check ID → "error" | "warning" to re-classify individual checks.
    # Example: severity_overrides: {AL-N01: error}
    severity_overrides: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------ ignores
    ignore_paths: list[str] = field(default_factory=lambda: ["archive/"])

    # ---------------------------------------- v0.2 — documentation drift scope
    # Glob patterns for extra files to scan with AL-P* and AL-F01.
    extra_paths: list[str] = field(default_factory=list)

    # .env vs .env.example key parity checks (AL-E01)
    config_parity: list[dict] = field(default_factory=list)

    # Cross-file value consistency groups (AL-C01)
    consistency_groups: list[dict] = field(default_factory=list)

    # ----------------------------------------------------------------- load
    @classmethod
    def load(cls, root: Path) -> "Config":
        for name in (".agentlint.yml", ".agentlint.yaml"):
            cfg_file = root / name
            if cfg_file.exists():
                return cls._from_file(cfg_file)
        return cls()

    @classmethod
    def _from_file(cls, path: Path) -> "Config":
        with open(path, encoding="utf-8") as fh:
            try:
                data: dict[str, Any] = yaml.safe_load(fh) or {}
            except yaml.YAMLError as exc:
                raise SystemExit(
                    f"[agentlint] Invalid config file {path}:\n  {exc}"
                ) from None

        cfg = cls()

        # Apply scalar / list overrides
        scalar_keys = {
            "number_source_lookback",
            "trigger_overlap_threshold",
            "output_format",
            "fail_on_warnings",
            "forbidden_patterns_mode",
            "instruction_dirs",
            "dispatch_files",
            "source_roots",
            "ignore_paths",
            "extra_paths",
        }
        for key in scalar_keys:
            if key in data:
                setattr(cfg, key, data[key])

        # Merge dicts
        if "checks" in data:
            cfg.checks.update(data["checks"])

        # Severity overrides
        if "severity_overrides" in data:
            raw = data["severity_overrides"]
            if isinstance(raw, dict):
                cfg.severity_overrides = {
                    k: v
                    for k, v in raw.items()
                    if isinstance(v, str) and v in ("error", "warning")
                }

        # Extend source markers
        if "source_markers" in data:
            cfg.source_markers = list(DEFAULT_SOURCE_MARKERS) + data["source_markers"]

        # Forbidden patterns — extend or replace
        if "forbidden_patterns" in data:
            if data.get("forbidden_patterns_mode") == "replace":
                cfg.forbidden_patterns = data["forbidden_patterns"]
            else:
                existing_ids = {p["id"] for p in DEFAULT_FORBIDDEN}
                for p in data["forbidden_patterns"]:
                    if p.get("id") not in existing_ids:
                        cfg.forbidden_patterns.append(p)

        # Config parity rules (AL-E01)
        if "config_parity" in data and isinstance(data["config_parity"], list):
            cfg.config_parity = data["config_parity"]

        # Consistency groups (AL-C01)
        if "consistency_groups" in data and isinstance(
            data["consistency_groups"], list
        ):
            cfg.consistency_groups = data["consistency_groups"]

        return cfg
