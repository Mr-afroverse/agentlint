"""
AL-C01  Cross-file value consistency groups.

Extracts a regex capture group from multiple files and verifies that every
file reports the same value. Files that disagree with the consensus are
flagged.

Configured via `.agentlint.yml`:

    consistency_groups:
      - id: test-count
        pattern: '\\b(\\d+)\\s+passed'
        files: ["README.md", "DEPLOYMENT_GUIDE.md", "docs/RELEASE_CHECKLIST.md"]
        severity: error
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for group in config.consistency_groups:
        group_id = group.get("id", "AL-C01")
        raw_pattern = group.get("pattern", "")
        file_list = group.get("files", [])
        try:
            severity = Severity(group.get("severity", "error"))
        except ValueError:
            severity = Severity.ERROR

        if not raw_pattern or len(file_list) < 2:
            continue

        try:
            pat = re.compile(raw_pattern)
        except re.error:
            continue

        # Extract values from each existing file
        extracted: dict[str, list[tuple[str, int]]] = {}  # rel_path → [(value, line)]
        for rel in file_list:
            fpath = root / rel
            if not fpath.is_file():
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                m = pat.search(line)
                if m:
                    val = m.group(1) if pat.groups >= 1 else m.group(0)
                    extracted.setdefault(rel, []).append((val, lineno))
                    break  # first match per file

        # Need at least 2 files with values to compare
        if len(extracted) < 2:
            continue

        # Find consensus — the most common value
        all_values = [matches[0][0] for matches in extracted.values()]
        counter = Counter(all_values)
        consensus, _ = counter.most_common(1)[0]

        for rel, matches in extracted.items():
            value, lineno = matches[0]
            if value != consensus:
                violations.append(
                    Violation(
                        check_id="AL-C01",
                        severity=severity,
                        file=root / rel,
                        line=lineno,
                        message=(
                            f"[{group_id}] Value `{value}` in `{rel}` differs "
                            f"from consensus `{consensus}` across {len(extracted)} files."
                        ),
                        fix_hint=f"Update to `{consensus}` or correct the other files.",
                    )
                )

    return violations
