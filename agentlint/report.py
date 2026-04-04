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

# Badge fill colours (shields.io palette)
_BADGE_COLOR = {
    "A": "#44cc11",
    "B": "#97ca00",
    "C": "#dfb317",
    "D": "#fe7d37",
    "F": "#e05d44",
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


def format_badge(result: LintResult) -> str:
    """Return a shields.io-style flat SVG badge showing the grade."""
    grade = result.grade()
    color = _BADGE_COLOR.get(grade, "#9f9f9f")
    label = "agentlint"
    value = f"Grade: {grade}"
    # Approximate character widths at 11px Verdana (shields.io formula)
    label_w = len(label) * 6 + 10
    value_w = len(value) * 6 + 10
    total_w = label_w + value_w
    label_x = label_w // 2
    value_x = label_w + value_w // 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20">'
        f'<linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/>'
        f"</linearGradient>"
        f'<rect width="{label_w}" height="20" fill="#555"/>'
        f'<rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>'
        f'<rect width="{total_w}" height="20" fill="url(#s)"/>'
        f'<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">'
        f'<text x="{label_x}" y="15" fill="#010101" fill-opacity=".3">{label}</text>'
        f'<text x="{label_x}" y="14">{label}</text>'
        f'<text x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{value}</text>'
        f'<text x="{value_x}" y="14">{value}</text>'
        f"</g>"
        f"</svg>"
    )
