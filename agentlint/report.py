from __future__ import annotations

import json
from datetime import datetime, timezone
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
            "scanned_files": result.scanned_files,
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


def _html_escape(text: str) -> str:
    """Minimal HTML escaping for report content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_html(result: LintResult, root: Path) -> str:
    """Return a self-contained HTML report page."""
    grade = result.grade()
    grade_color = {
        "A": "#44cc11",
        "B": "#97ca00",
        "C": "#dfb317",
        "D": "#fe7d37",
        "F": "#e05d44",
    }.get(grade, "#9f9f9f")

    errors = len(result.errors)
    warnings = len(result.warnings)
    total = len(result.violations)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Group violations by file
    by_file: dict[Path, list[Violation]] = {}
    for v in result.violations:
        by_file.setdefault(v.file, []).append(v)

    # Build violation rows HTML
    rows_html = ""
    for filepath, viols in sorted(by_file.items()):
        rel = _html_escape(_rel(filepath, root))
        rows_html += '<div class="file-group">'
        rows_html += f'<h3 class="file-name">{rel}</h3>'
        rows_html += (
            '<table class="violations-table">'
            "<thead><tr>"
            "<th>Severity</th><th>Check</th><th>Line</th>"
            "<th>Message</th><th>Fix hint</th>"
            "</tr></thead><tbody>"
        )
        for v in viols:
            sev = v.severity.value
            sev_icon = {
                "error": "&#x2716;",
                "warning": "&#x26a0;",
                "info": "&#x2139;",
            }.get(sev, "&bull;")
            fix = _html_escape(v.fix_hint) if v.fix_hint else ""
            rows_html += (
                f'<tr class="row-{sev}" data-severity="{sev}">'
                f'<td><span class="badge sev-{sev}">{sev_icon} {sev}</span></td>'
                f"<td><code>{_html_escape(v.check_id)}</code></td>"
                f"<td>{v.line or ''}</td>"
                f"<td>{_html_escape(v.message)}</td>"
                f'<td class="fix-col">{fix}</td>'
                f"</tr>"
            )
        rows_html += "</tbody></table></div>"

    if not result.violations:
        rows_html = '<p class="pass-msg">&#x2714; No violations found.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentlint report</title>
<style>
:root {{
  --bg: #ffffff; --fg: #1a1a2e; --card: #f8f9fa;
  --border: #dee2e6; --code-bg: #f1f3f5; --muted: #6c757d;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0d1117; --fg: #c9d1d9; --card: #161b22;
    --border: #30363d; --code-bg: #21262d; --muted: #8b949e;
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--fg);
  padding: 2rem; max-width: 1100px; margin: 0 auto;
}}
header {{ display: flex; align-items: center; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }}
.grade-badge {{
  font-size: 2rem; font-weight: 800; padding: 0.4rem 1rem;
  border-radius: 8px; color: #fff; background: {grade_color};
  white-space: nowrap;
}}
.summary {{ font-size: 0.9rem; color: var(--muted); line-height: 1.6; }}
.summary strong {{ color: var(--fg); }}
.filters {{
  margin-bottom: 1.5rem; display: flex; gap: 0.6rem;
  flex-wrap: wrap; align-items: center;
}}
.filter-label {{ font-size: 0.85rem; color: var(--muted); margin-right: 0.25rem; }}
.filter-btn {{
  padding: 0.3rem 0.8rem; border: 1px solid var(--border);
  border-radius: 20px; cursor: pointer; background: var(--card);
  color: var(--fg); font-size: 0.82rem; transition: all 0.15s;
}}
.filter-btn:hover {{ border-color: #0d6efd; }}
.filter-btn.active {{ border-color: #0d6efd; background: #0d6efd; color: #fff; }}
.file-group {{
  border: 1px solid var(--border); border-radius: 8px;
  margin-bottom: 1.25rem; overflow: hidden;
}}
.file-name {{
  font-family: ui-monospace, "Cascadia Code", monospace; font-size: 0.875rem;
  padding: 0.6rem 1rem; background: var(--card);
  border-bottom: 1px solid var(--border); font-weight: 600;
}}
.violations-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
.violations-table th {{
  text-align: left; padding: 0.5rem 0.75rem; background: var(--card);
  border-bottom: 1px solid var(--border); font-weight: 600;
  font-size: 0.75rem; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--muted);
}}
.violations-table td {{
  padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
.violations-table tr:last-child td {{ border-bottom: none; }}
.badge {{
  display: inline-block; padding: 0.18rem 0.5rem;
  border-radius: 4px; font-size: 0.75rem; font-weight: 700;
}}
.sev-error {{ background: #ffebe9; color: #cf222e; }}
.sev-warning {{ background: #fff8c5; color: #9a6700; }}
.sev-info {{ background: #ddf4ff; color: #0969da; }}
@media (prefers-color-scheme: dark) {{
  .sev-error {{ background: #3d1c1c; color: #f85149; }}
  .sev-warning {{ background: #2d2200; color: #e3b341; }}
  .sev-info {{ background: #031d2e; color: #58a6ff; }}
}}
code {{
  font-family: ui-monospace, "Cascadia Code", monospace; font-size: 0.85em;
  background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px;
}}
.fix-col {{ color: var(--muted); font-size: 0.82rem; }}
.pass-msg {{
  text-align: center; padding: 3rem; font-size: 1.1rem;
  color: #44cc11; font-weight: 600;
}}
.hidden {{ display: none !important; }}
footer {{
  margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);
  font-size: 0.8rem; color: var(--muted); text-align: center;
}}
</style>
</head>
<body>
<header>
  <span class="grade-badge">Grade&nbsp;{grade}</span>
  <div>
    <div style="font-size:1.05rem;font-weight:600;margin-bottom:0.25rem">agentlint report</div>
    <div class="summary">
      Generated {timestamp} &nbsp;&bull;&nbsp;
      <strong>{result.files_scanned}</strong> file(s) scanned &nbsp;&bull;&nbsp;
      <strong>{errors}</strong> error(s) &nbsp;&bull;&nbsp;
      <strong>{warnings}</strong> warning(s)
    </div>
  </div>
</header>
<div class="filters">
  <span class="filter-label">Filter:</span>
  <button class="filter-btn active" data-filter="all" onclick="applyFilter('all')">All ({total})</button>
  <button class="filter-btn" data-filter="error" onclick="applyFilter('error')">Errors ({errors})</button>
  <button class="filter-btn" data-filter="warning" onclick="applyFilter('warning')">Warnings ({warnings})</button>
</div>
{rows_html}
<footer>Generated by <strong>agentlint {__version__}</strong></footer>
<script>
function applyFilter(sev) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{
    b.classList.toggle('active', b.dataset.filter === sev);
  }});
  document.querySelectorAll('tr[data-severity]').forEach(function(r) {{
    r.classList.toggle('hidden', sev !== 'all' && r.dataset.severity !== sev);
  }});
  document.querySelectorAll('.file-group').forEach(function(g) {{
    var vis = g.querySelectorAll('tr[data-severity]:not(.hidden)');
    g.classList.toggle('hidden', vis.length === 0 && {str(bool(result.violations)).lower()});
  }});
}}
</script>
</body>
</html>"""
