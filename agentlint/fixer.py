"""
Auto-fix engine for agentlint.

Groups fixable violations by file, then rebuilds each file's line array
using fix_data["new_line"] for matched violations.

Rules:
  - Only violations with auto_fixable=True and a line number are eligible.
  - fix_data must contain "old_line" and "new_line" keys.
  - If the current on-disk content of a line no longer matches fix_data["old_line"]
    (e.g. another fix already changed it), that fix is skipped to avoid
    partial-replacement collisions.
  - Multiple fixes targeting the same line number: first fix wins; rest are skipped.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import cast

import click

from agentlint.models import Violation

def apply_fixes(
    violations: list[Violation],
    root: Path,
) -> tuple[list[Violation], int]:
    """Apply all auto-fixable violations to disk.

    Returns a tuple of (applied_violations, skipped_count) where
    *applied_violations* is the list of Violation objects that were
    successfully written to disk.  *skipped_count* covers violations
    that were marked auto_fixable but whose on-disk line had already
    changed (stale fix_data), or that had duplicate line numbers.
    """
    fixable = [
        v for v in violations if v.auto_fixable and v.line is not None and v.fix_data
    ]

    if not fixable:
        return [], 0

    # Group violations by file path.
    by_file: dict[Path, list[Violation]] = defaultdict(list)
    for v in fixable:
        by_file[v.file].append(v)

    applied: list[Violation] = []
    skipped = 0

    for file_path, file_violations in by_file.items():
        try:
            raw = file_path.read_text(encoding="utf-8", newline="")
        except OSError:
            skipped += len(file_violations)
            continue

        # splitlines(keepends=True) preserves \n / \r\n per line.
        lines = raw.splitlines(keepends=True)

        # Sort by line number ascending; track which lines have been modified.
        sorted_violations = sorted(file_violations, key=lambda v: cast(int, v.line))
        already_modified: set[int] = set()
        pending: list[tuple[int, str, str, Violation]] = []

        for v in sorted_violations:
            lineno: int = cast(int, v.line)  # non-None guaranteed by `fixable` filter
            if lineno in already_modified:
                skipped += 1
                continue
            if lineno < 1 or lineno > len(lines):
                skipped += 1
                continue

            # Strip the on-disk line ending for comparison.
            current = lines[lineno - 1].rstrip("\n\r")
            expected = v.fix_data.get("old_line", "")

            if current != expected:
                # Stale: the line changed since the violation was collected.
                skipped += 1
                continue

            pending.append((lineno, current, v.fix_data["new_line"], v))
            already_modified.add(lineno)

        if not pending:
            continue

        # Build relative path for display.
        try:
            rel = file_path.relative_to(root).as_posix()
        except ValueError:
            rel = file_path.as_posix()

        click.echo(f"[agentlint] Fixing {rel}:")

        # Apply pending changes.
        for lineno, old_text, new_text, v in pending:
            # Preserve the original line ending.
            ending = lines[lineno - 1][len(old_text):]
            lines[lineno - 1] = new_text + ending
            applied.append(v)
            click.echo(f"  line {lineno}:  - {old_text}")
            click.echo(f"            + {new_text}")

        file_path.write_text("".join(lines), encoding="utf-8", newline="")

    return applied, skipped
