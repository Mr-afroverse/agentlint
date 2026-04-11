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
    # Where to look when resolving source file references like `app/services/foo.py`
    source_roots: list[str] = field(default_factory=lambda: [".", "src"])

    # ---------------------------------------------------------- check toggles
    checks: dict[str, bool] = field(
        default_factory=lambda: {
            # ── Dispatch / structure ──────────────────────────────────────
            "dispatch-coverage": True,  # AL-D01/AL-D02/AL-D04/AL-D05
            "circular-refs": True,  # AL-D03
            "role-coverage": True,  # AL-D04
            # ── File & anchor references ──────────────────────────────────
            "file-references": True,  # AL-F01
            "dead-anchors": True,  # AL-F02
            # ── Number sourcing ───────────────────────────────────────────
            "number-sourcing": True,  # AL-N01/AL-N02
            "value-extraction": True,  # AL-V01
            # ── Trigger quality ───────────────────────────────────────────
            "trigger-overlap": True,  # AL-T01
            # ── Content patterns ──────────────────────────────────────────
            "forbidden-patterns": True,  # AL-P*
            "deprecated-patterns": True,  # AL-DEP*
            # ── Security ─────────────────────────────────────────────────
            "secret-detection": True,  # AL-S01
            # ── Semantic quality ──────────────────────────────────────────
            "inverse-claims": True,  # AL-INV01
            "vague-instructions": True,  # AL-Q01
            "semantic-conflict": True,  # AL-CONF01
            "duplicate-content": True,  # AL-DUP01
            # ── File metadata & structure ─────────────────────────────────
            "encoding-check": True,  # AL-ENC01
            "frontmatter-schema": True,  # AL-FM01
            "min-content": True,  # AL-LEN01
            "token-budget": True,  # AL-TOK01
            "freshness": True,  # AL-FRESH01
            # ── Config-driven standalone ──────────────────────────────────
            "config-parity": True,  # AL-E01
            "consistency-groups": True,  # AL-C01
            "ground-truth": True,  # AL-G01
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
    # Per-file check suppression: maps a path pattern (same substring match as
    # ignore_paths) to a list of check keys to suppress for that file.
    # Files present here are still collected and scanned by all OTHER checks.
    # Populated automatically when an ignore_paths dict entry has a "checks" key:
    #   ignore_paths:
    #     - path: "CHANGELOG.md"
    #       checks: ["dead-anchors"]
    #       reason: "Illustrative examples trigger AL-F02 false positives"
    ignore_checks: dict[str, list[str]] = field(default_factory=dict)

    # ---------------------------------------- v0.2 — documentation drift scope
    # Glob patterns for extra files to scan with AL-P* and AL-F01.
    extra_paths: list[str] = field(default_factory=list)

    # .env vs .env.example key parity checks (AL-E01)
    config_parity: list[dict] = field(default_factory=list)

    # Cross-file value consistency groups (AL-C01)
    consistency_groups: list[dict] = field(default_factory=list)

    # Ground-truth file checks (AL-G01)
    ground_truth_files: list[dict] = field(default_factory=list)

    # Opt-in: detect file paths inside ASCII tree diagrams for AL-F01
    tree_diagram_paths: bool = False

    # Opt-in: also scan tree diagrams inside ``` code fences for AL-F01
    # Requires tree_diagram_paths: true to have any effect.
    tree_diagram_fenced: bool = False

    # AL-TOK01: warn when estimated token count of an instruction file exceeds
    # this budget.  0 = disabled (default).
    token_budget: int = 0

    # AL-D04: required role names — every role must have at least one SKILL file.
    # Role is matched against skill `name` frontmatter or parent directory name.
    required_roles: list[str] = field(default_factory=list)

    # AL-LEN01: warn when estimated token count of an instruction file is below
    # this threshold. Files this small are likely accidental stubs.
    # Uses the same character-count / 4 heuristic as AL-TOK01.
    min_content_tokens: int = 10

    # AL-FM01: required frontmatter keys for SKILL files.  Empty list = disabled.
    # Example: required_frontmatter: [name, description]
    required_frontmatter: list[str] = field(default_factory=list)

    # AL-DUP01: Jaccard similarity threshold for near-duplicate detection.
    # Range 0.0–1.0. Files with similarity >= threshold are flagged.
    # Default 0.85. Set to 0 to disable.
    duplicate_threshold: float = 0.85

    # AL-FRESH01: warn on dates older than this many days in instruction files.
    # 0 = disabled (default).
    stale_days: int = 0

    # AL-DEP*: user-supplied list of deprecated AI provider API patterns.
    # Each entry: {pattern, reason, replacement (optional), severity (optional), id (optional)}.
    # Empty list = disabled (default).
    deprecated_patterns: list[dict] = field(default_factory=list)

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

        # Apply string / list / bool overrides (no numeric coercion needed).
        scalar_keys = {
            "output_format",
            "fail_on_warnings",
            "forbidden_patterns_mode",
            "source_roots",
            "extra_paths",
        }
        for key in scalar_keys:
            if key in data:
                setattr(cfg, key, data[key])

        # Integer fields — cast to int to guard against quoted YAML values
        # (e.g. `token_budget: "2000"` would store a str and crash downstream).
        for _int_key in ("number_source_lookback", "token_budget", "stale_days"):
            if _int_key in data and data[_int_key] is not None:
                try:
                    setattr(cfg, _int_key, int(data[_int_key]))
                except (TypeError, ValueError):
                    pass  # keep the dataclass default

        # Float fields — same guard for threshold values.
        for _float_key in ("trigger_overlap_threshold", "duplicate_threshold"):
            if _float_key in data and data[_float_key] is not None:
                try:
                    setattr(cfg, _float_key, float(data[_float_key]))
                except (TypeError, ValueError):
                    pass  # keep the dataclass default

        # ignore_paths: each entry is either a plain string or a dict with
        # a required "path" key and optional "reason" and "checks" keys.
        # When "checks" is present the file is not blanket-ignored — it is
        # still collected and scanned, but only the listed check keys are
        # suppressed for that file.
        if "ignore_paths" in data:
            raw_paths = data["ignore_paths"]
            if isinstance(raw_paths, list):
                parsed_checks: dict[str, list[str]] = {}
                cfg.ignore_paths = [
                    (entry["path"] if isinstance(entry, dict) else str(entry))
                    for entry in raw_paths
                    if isinstance(entry, (str, dict))
                ]
                for entry in raw_paths:
                    if isinstance(entry, dict):
                        p = entry.get("path", "")
                        raw_c = entry.get("checks")
                        if p and isinstance(raw_c, list):
                            parsed_checks[p] = [str(c) for c in raw_c]
                cfg.ignore_checks = parsed_checks

        # Merge dicts — guard against non-dict YAML values (e.g. checks: true)
        if "checks" in data and isinstance(data["checks"], dict):
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

        # Extend source markers — guard against scalar YAML values (e.g. source_markers: "heuristic")
        if "source_markers" in data and isinstance(data["source_markers"], list):
            cfg.source_markers = list(DEFAULT_SOURCE_MARKERS) + data["source_markers"]

        # Forbidden patterns — extend or replace
        # Guard: skip malformed entries (non-dict items raise AttributeError on .get())
        if "forbidden_patterns" in data and isinstance(
            data["forbidden_patterns"], list
        ):
            if data.get("forbidden_patterns_mode") == "replace":
                cfg.forbidden_patterns = [
                    p for p in data["forbidden_patterns"] if isinstance(p, dict)
                ]
            else:
                existing_ids = {p["id"] for p in DEFAULT_FORBIDDEN}
                for p in data["forbidden_patterns"]:
                    if not isinstance(p, dict):
                        continue  # skip bare strings or other non-dict entries
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

        # Ground truth file checks (AL-G01)
        if "ground_truth_files" in data and isinstance(
            data["ground_truth_files"], list
        ):
            cfg.ground_truth_files = data["ground_truth_files"]

        # Tree diagram path detection for AL-F01 (opt-in)
        if "tree_diagram_paths" in data:
            cfg.tree_diagram_paths = bool(data["tree_diagram_paths"])

        # Fenced tree diagram scanning for AL-F01 (opt-in)
        if "tree_diagram_fenced" in data:
            cfg.tree_diagram_fenced = bool(data["tree_diagram_fenced"])

        # Required role names (AL-D04)
        if "required_roles" in data and isinstance(data["required_roles"], list):
            cfg.required_roles = [str(r) for r in data["required_roles"]]

        # Minimum content tokens (AL-LEN01)
        if "min_content_tokens" in data and data["min_content_tokens"] is not None:
            try:
                cfg.min_content_tokens = int(data["min_content_tokens"])
            except (TypeError, ValueError):
                pass  # keep the dataclass default

        # Required frontmatter keys (AL-FM01)
        if "required_frontmatter" in data and isinstance(
            data["required_frontmatter"], list
        ):
            cfg.required_frontmatter = [str(k) for k in data["required_frontmatter"]]

        # Deprecated patterns (AL-DEP*)
        if "deprecated_patterns" in data and isinstance(
            data["deprecated_patterns"], list
        ):
            cfg.deprecated_patterns = data["deprecated_patterns"]

        return cfg
