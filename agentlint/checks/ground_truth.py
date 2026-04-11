"""
AL-G01  Ground-truth file checks — verify documentation values against
        authoritative data in JSON or YAML files.

Reads a scalar or list from a structured data file and validates that
documentation files contain the correct value(s).

Modes:
  - ``value_match``  (default): extract a scalar, verify docs match.
  - ``no_stale_refs``: extract a list of valid identifiers, flag doc
    references matching ``ref_pattern`` that are not in the list.

No subprocess execution — reads files only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation


def _navigate(data: Any, path: str) -> Any:
    """Traverse *data* along a simple dot-notation path.

    Supports:
      ``"key"``              → ``data["key"]``
      ``"key.subkey"``       → ``data["key"]["subkey"]``
      ``"items[*].id"``      → ``[item["id"] for item in data["items"]]``
    """
    parts = path.lstrip("$.").split(".")
    current: Any = data
    i = 0
    while i < len(parts):
        part = parts[i]
        # Array fan-out: items[*] or items[]
        if part.endswith("[*]") or part.endswith("[]"):
            key = part.rsplit("[", 1)[0]
            if key:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            if not isinstance(current, list):
                return None
            remaining = ".".join(parts[i + 1 :])
            if remaining:
                return [
                    _navigate(item, remaining)
                    for item in current
                    if _navigate(item, remaining) is not None
                ]
            return current
        # Normal key
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        if current is None:
            return None
        i += 1
    return current


def _read_data_file(path: Path) -> Any:
    """Read and parse a JSON or YAML file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(raw)
    return json.loads(raw)


def _resolve_target_files(root: Path, patterns: list[str]) -> list[Path]:
    """Expand file patterns (plain paths or globs) into concrete paths."""
    result: list[Path] = []
    for pat in patterns:
        if "*" in pat or "?" in pat:
            result.extend(sorted(root.glob(pat)))
        else:
            p = root / pat
            if p.is_file():
                result.append(p)
    return result


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for rule in config.ground_truth_files:
        rule_id = rule.get("id", "CUSTOM")
        data_file = rule.get("json_file", "")
        data_path = rule.get("json_path", "")
        doc_pattern = rule.get("doc_pattern", "")
        target_files = rule.get("files", [])
        severity_str = rule.get("severity", "error")
        severity = Severity.ERROR if severity_str == "error" else Severity.WARNING
        reason = rule.get("reason", "")
        mode = rule.get("mode", "value_match")

        # Guard against path traversal via crafted config values.
        source_path = root / data_file
        if not source_path.resolve().is_relative_to(root.resolve()):
            violations.append(
                Violation(
                    check_id="AL-G01",
                    severity=Severity.WARNING,
                    file=root / data_file,
                    line=None,
                    message=f"[{rule_id}] Ground truth path escapes project root: `{data_file}`",
                    fix_hint="Use a path relative to the project root in .agentlint.yml.",
                )
            )
            continue
        if not source_path.is_file():
            violations.append(
                Violation(
                    check_id="AL-G01",
                    severity=Severity.WARNING,
                    file=source_path,
                    line=None,
                    message=f"[{rule_id}] Ground truth file not found: `{data_file}`",
                    fix_hint="Check the json_file path in .agentlint.yml.",
                )
            )
            continue

        try:
            data = _read_data_file(source_path)
        except (json.JSONDecodeError, yaml.YAMLError, OSError) as exc:
            violations.append(
                Violation(
                    check_id="AL-G01",
                    severity=Severity.WARNING,
                    file=source_path,
                    line=None,
                    message=f"[{rule_id}] Cannot parse `{data_file}`: {exc}",
                    fix_hint="Fix the file syntax or check the path.",
                )
            )
            continue

        truth = _navigate(data, data_path)
        if truth is None:
            violations.append(
                Violation(
                    check_id="AL-G01",
                    severity=Severity.WARNING,
                    file=source_path,
                    line=None,
                    message=f"[{rule_id}] Path `{data_path}` not found in `{data_file}`",
                    fix_hint="Check the json_path in .agentlint.yml.",
                )
            )
            continue

        resolved = _resolve_target_files(root, target_files)

        if mode == "no_stale_refs":
            ref_pattern = rule.get("ref_pattern", "")
            _check_stale_refs(
                rule_id, truth, ref_pattern, resolved, severity, reason, violations
            )
        else:
            _check_value_match(
                rule_id, str(truth), doc_pattern, resolved, severity, reason, violations
            )

    return violations


def _check_value_match(
    rule_id: str,
    truth_value: str,
    doc_pattern: str,
    target_files: list[Path],
    severity: Severity,
    reason: str,
    violations: list[Violation],
) -> None:
    """Verify that the documented value matches the ground truth."""
    if not doc_pattern:
        return
    try:
        pat = re.compile(doc_pattern)
    except re.error as exc:
        import sys

        print(
            f"[agentlint] Warning: invalid doc_pattern regex in ground_truth_files "
            f"(id={rule_id}): {exc}",
            file=sys.stderr,
        )
        return

    for fpath in target_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            m = pat.search(line)
            if m:
                doc_val = m.group(1) if m.lastindex else m.group(0)
                if doc_val != truth_value:
                    msg = (
                        f"[{rule_id}] Documented value `{doc_val}` \u2260 "
                        f"ground truth `{truth_value}`"
                    )
                    if reason:
                        msg += f". {reason}"
                    violations.append(
                        Violation(
                            check_id="AL-G01",
                            severity=severity,
                            file=fpath,
                            line=lineno,
                            message=msg,
                            fix_hint=f"Update to `{truth_value}`.",
                        )
                    )


def _check_stale_refs(
    rule_id: str,
    valid_ids: Any,
    ref_pattern: str,
    target_files: list[Path],
    severity: Severity,
    reason: str,
    violations: list[Violation],
) -> None:
    """Flag references matching *ref_pattern* that are not in *valid_ids*."""
    if not isinstance(valid_ids, list) or not ref_pattern:
        return
    valid_set = {str(v) for v in valid_ids if v is not None}
    if not valid_set:
        return

    try:
        pat = re.compile(ref_pattern)
    except re.error as exc:
        import sys

        print(
            f"[agentlint] Warning: invalid ref_pattern regex in ground_truth_files "
            f"(id={rule_id}): {exc}",
            file=sys.stderr,
        )
        return

    for fpath in target_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            for m in pat.finditer(line):
                ref_val = m.group(1) if m.lastindex else m.group(0)
                if ref_val not in valid_set:
                    msg = f"[{rule_id}] Reference `{ref_val}` not in ground truth"
                    if reason:
                        msg += f". {reason}"
                    violations.append(
                        Violation(
                            check_id="AL-G01",
                            severity=severity,
                            file=fpath,
                            line=lineno,
                            message=msg,
                            fix_hint=f"Remove the stale reference or add `{ref_val}` to the source.",
                        )
                    )
