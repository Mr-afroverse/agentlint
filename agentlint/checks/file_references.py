"""
AL-F01  Concrete source-file paths referenced in skill files must exist on disk.

Matches paths like `app/services/foo.py`, `src/utils/bar.ts`, etc.
Glob patterns and template strings (containing `{` or `*`) are ignored.

When ``tree_diagram_paths`` is enabled in config, also checks filenames
inside ASCII tree diagrams (├── / └── prefixed lines) outside code fences.

When ``tree_diagram_fenced`` is additionally enabled, tree diagrams inside
``` code fences are also scanned (opt-in, off by default).
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

# Matches paths starting with a common source root segment followed by at least
# one directory separator and a filename with an extension.
_FILE_REF_RE = re.compile(
    r"\b((?:app|src|lib|pkg|backend|frontend)/[a-zA-Z0-9_/.-]+\.[a-zA-Z]{1,6})\b"
)

# Exactly 3 backticks at start of line — opening/closing a code fence.
_CODE_FENCE_RE = re.compile(r"^```(?!`)")

# Tree diagram line: ├── filename.ext or └── filename.ext
_TREE_FILE_RE = re.compile(r"[│├└─\s]*[├└]\u2500\u2500\s+([\w.-]+\.[\w]{1,6})\b")


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    # Build candidate roots: configured + any top-level subdirectory of root.
    candidate_roots: list[Path] = [root / sr for sr in config.source_roots]
    try:
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                candidate_roots.append(child)
    except PermissionError:
        pass

    def _exists(ref: str) -> bool:
        return any((cr / ref).exists() for cr in candidate_roots)

    # Collect project files for fuzzy suggestions (only paths matching the regex prefix).
    known_files: list[str] = []
    try:
        for f in root.rglob("*"):
            if f.is_file() and not any(
                part.startswith(".") for part in f.relative_to(root).parts
            ):
                rel = f.relative_to(root).as_posix()
                if _FILE_REF_RE.match(rel):
                    known_files.append(rel)
    except PermissionError:
        pass

    # Collect all filenames in project (for tree diagram checking).
    known_filenames: set[str] = set()
    if config.tree_diagram_paths or config.tree_diagram_fenced:
        try:
            for f in root.rglob("*"):
                if f.is_file() and not any(
                    part.startswith(".") for part in f.relative_to(root).parts
                ):
                    known_filenames.add(f.name)
        except PermissionError:
            pass

    violations: list[Violation] = []

    for sf in [f for f in files if f.role in (Role.SKILL, Role.DOCS)]:
        seen: set[str] = set()
        in_code = False
        for lineno, line in enumerate(sf.lines, start=1):
            # Track code fence state
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code

            # File-ref scanning is always skipped inside fences.
            if not in_code:
                for m in _FILE_REF_RE.finditer(line):
                    ref = m.group(1)
                    if ref in seen or "{" in ref or "*" in ref:
                        continue
                    seen.add(ref)
                    if not _exists(ref):
                        suggestions = difflib.get_close_matches(
                            ref, known_files, n=1, cutoff=0.6
                        )
                        if suggestions:
                            fix_hint = (
                                f"Did you mean '{suggestions[0]}'? "
                                "Update the path or create the missing file."
                            )
                        else:
                            fix_hint = "Update the path or create the missing file."
                        violations.append(
                            Violation(
                                check_id="AL-F01",
                                severity=Severity.WARNING,
                                file=sf.path,
                                line=lineno,
                                message=f"Referenced file not found on disk: `{ref}`",
                                fix_hint=fix_hint,
                            )
                        )

            # Tree diagram paths: outside fences (tree_diagram_paths) OR
            # inside fences too (tree_diagram_fenced).
            scan_tree = (config.tree_diagram_paths and not in_code) or (
                config.tree_diagram_fenced and in_code
            )
            if scan_tree:
                for m in _TREE_FILE_RE.finditer(line):
                    fname = m.group(1)
                    if fname in seen:
                        continue
                    seen.add(fname)
                    if fname not in known_filenames:
                        suggestions = difflib.get_close_matches(
                            fname,
                            sorted(known_filenames),
                            n=1,
                            cutoff=0.6,
                        )
                        fix_hint = (
                            f"Did you mean '{suggestions[0]}'? " if suggestions else ""
                        )
                        fix_hint += "Update the filename or create the missing file."
                        violations.append(
                            Violation(
                                check_id="AL-F01",
                                severity=Severity.WARNING,
                                file=sf.path,
                                line=lineno,
                                message=f"Tree diagram file not found on disk: `{fname}`",
                                fix_hint=fix_hint,
                            )
                        )

    return violations
