"""
AL-F01  Concrete source-file paths referenced in skill and dispatch files must
        exist on disk.

Matches paths like `app/services/foo.py`, `src/utils/bar.ts`, etc.
The prefix set is built dynamically from hardcoded defaults, configured
``source_roots``, and top-level non-hidden project directories — so project-
specific trees like ``agentlint/`` are automatically included.
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
from agentlint.checks._utils import _CODE_FENCE_RE

# Default prefix set — used as the baseline when building the dynamic regex.
_DEFAULT_PREFIXES: frozenset[str] = frozenset(
    {"app", "src", "lib", "pkg", "backend", "frontend"}
)

# Module-level fallback regex (used when dynamic building is not possible).
_FILE_REF_RE = re.compile(
    r"\b((?:app|src|lib|pkg|backend|frontend)/[a-zA-Z0-9_/.-]+\.[a-zA-Z]{1,6})\b"
)


def _build_file_ref_re(config: Config, root: Path) -> re.Pattern[str]:
    """Return a file-ref regex whose prefix set covers:
    - the hardcoded defaults (app, src, lib, ...)
    - any configured source_roots that are simple directory names
    - any non-hidden top-level directory found in *root*
    """
    prefixes: set[str] = set(_DEFAULT_PREFIXES)
    for sr in config.source_roots:
        sr = sr.strip()
        if sr and sr != "." and "/" not in sr and "\\" not in sr:
            prefixes.add(sr)
    try:
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith((".", "_")):
                prefixes.add(child.name)
    except PermissionError:
        pass
    prefix_pat = "|".join(re.escape(p) for p in sorted(prefixes))
    return re.compile(rf"\b((?:{prefix_pat})/[a-zA-Z0-9_/.-]+\.[a-zA-Z]{{1,6}})\b")


# Tree diagram line: ├── filename.ext or └── filename.ext
_TREE_FILE_RE = re.compile(r"[│├└─\s]*[├└]\u2500\u2500\s+([\w.-]+\.[\w]{1,6})\b")


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    # Build a project-aware regex that covers agentlint/, tests/, etc. in addition
    # to the default prefixes.
    file_ref_re = _build_file_ref_re(config, root)

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
                if file_ref_re.match(rel):
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

    for sf in [f for f in files if f.role in (Role.SKILL, Role.DISPATCH, Role.DOCS)]:
        seen: set[str] = set()
        in_code = False
        for lineno, line in enumerate(sf.lines, start=1):
            # Track code fence state
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code

            # File-ref scanning is always skipped inside fences.
            if not in_code:
                for m in file_ref_re.finditer(line):
                    ref = m.group(1)
                    if ref in seen or "{" in ref or "*" in ref:
                        continue
                    # Skip path segments embedded inside URLs (e.g. GitHub badge
                    # URLs where the package name appears as a URL component).
                    if m.start() > 0 and line[m.start() - 1] == "/":
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
