from __future__ import annotations

import json
from pathlib import Path

from agentlint import __version__
from agentlint.models import LintResult, Severity, Violation

_SEVERITY_ICON = {
    Severity.ERROR: "✖",
    Severity.WARNING: "⚠",
    Severity.INFO: "ℹ",
}

_ANSI = {
    "red": "\033[31m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

_GRADE_COLOR = {
    "A": "green",
    "B": "green",
    "C": "yellow",
    "D": "red",
    "F": "red",
}


def _c(text: str, color: str) -> str:
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def format_text(result: LintResult, root: Path) -> str:
    grade = result.grade()
    grade_str = _c(f"Grade: {grade}", _GRADE_COLOR.get(grade, "reset"))

    if not result.violations:
        return (
            f"\n{_c('[agentlint] PASS', 'green')} — "
            f"{result.files_scanned} file(s) scanned, 0 violations.  {grade_str}\n"
        )

    header = (
        f"\n{_c('[agentlint]', 'red')} "
        f"{len(result.errors)} error(s), {len(result.warnings)} warning(s) "
        f"across {result.files_scanned} file(s).  {grade_str}\n"
    )

    # Group violations by file
    by_file: dict[Path, list[Violation]] = {}
    for v in result.violations:
        by_file.setdefault(v.file, []).append(v)

    body_lines: list[str] = []
    for path, viols in sorted(by_file.items()):
        body_lines.append(f"  {_c(_rel(path, root), 'bold')}")
        for v in viols:
            loc = f":{v.line}" if v.line else ""
            icon_color = "red" if v.severity == Severity.ERROR else "yellow"
            icon = _c(_SEVERITY_ICON.get(v.severity, "•"), icon_color)
            body_lines.append(f"    {icon} [{v.check_id}]{loc}  {v.message}")
            if v.fix_hint:
                body_lines.append(f"      {_c('Fix →', 'bold')} {v.fix_hint}")
        body_lines.append("")

    footer = "Fix the issues above and re-run agentlint.\n"
    return header + "\n".join(body_lines) + footer


def format_json(result: LintResult, root: Path) -> str:
    def _v(v: Violation) -> dict:
        return {
            "check_id": v.check_id,
            "severity": v.severity.value,
            "file": _rel(v.file, root),
            "line": v.line,
            "message": v.message,
            "fix_hint": v.fix_hint,
            "auto_fixable": v.auto_fixable,
        }

    return json.dumps(
        {
            "grade": result.grade(),
            "adapter": result.adapter,
            "files_scanned": result.files_scanned,
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "violations": [_v(v) for v in result.violations],
        },
        indent=2,
    )


_SARIF_LEVEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)


def format_sarif(result: LintResult, root: Path) -> str:
    """Return a SARIF 2.1.0 JSON string for the lint result."""
    # Collect unique rules from violations
    seen_rules: dict[str, dict] = {}
    for v in result.violations:
        if v.check_id not in seen_rules:
            seen_rules[v.check_id] = {
                "id": v.check_id,
                "name": v.check_id.replace("-", ""),
                "shortDescription": {"text": v.message},
            }

    sarif_results = []
    for v in result.violations:
        entry: dict = {
            "ruleId": v.check_id,
            "level": _SARIF_LEVEL.get(v.severity, "warning"),
            "message": {"text": v.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": _rel(v.file, root),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {"startLine": v.line or 1},
                    }
                }
            ],
        }
        if v.fix_hint:
            entry["fixes"] = [
                {"description": {"text": v.fix_hint}, "artifactChanges": []}
            ]
        sarif_results.append(entry)

    payload = {
        "version": "2.1.0",
        "$schema": _SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agentlint",
                        "version": __version__,
                        "informationUri": "https://github.com/Mr-afroverse/agentlint",
                        "rules": list(seen_rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(payload, indent=2)
