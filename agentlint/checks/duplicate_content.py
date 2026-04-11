"""
AL-DUP01  Near-duplicate instruction files detected.

Two instruction files are flagged when their Jaccard similarity (computed on
3-character n-grams of normalised text) exceeds ``duplicate_threshold`` in
config (default: 0.85).  Only compares pairs of files *with the same role*
(SKILL–SKILL or DISPATCH–DISPATCH) to avoid false positives from intentional
adapter bridging.

Disabled when fewer than two files are present, or when
``duplicate_threshold: 0`` is set in ``.agentlint.yml``.

Similarity formula::

    J(A, B) = |ngrams(A) ∩ ngrams(B)| / |ngrams(A) ∪ ngrams(B)|

All text is lower-cased and runs of whitespace are collapsed to a single
space before n-gram extraction to reduce noise from minor formatting
differences.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

_WS_RE = re.compile(r"\s+")
_NGRAM_SIZE = 3


def _normalise(text: str) -> str:
    """Lower-case + collapse whitespace."""
    return _WS_RE.sub(" ", text.lower()).strip()


def _ngrams(text: str, n: int = _NGRAM_SIZE) -> set[str]:
    """Return the set of character n-grams for *text*."""
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _jaccard(a: str, b: str) -> float:
    """Jaccard similarity on character n-grams of *a* and *b*."""
    na = _ngrams(a)
    nb = _ngrams(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    intersection = len(na & nb)
    union = len(na | nb)
    return intersection / union if union else 0.0


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    threshold = config.duplicate_threshold
    if threshold <= 0.0:
        return []

    violations: list[Violation] = []

    # Group by role — only compare files with the same role.
    for role in (Role.SKILL, Role.DISPATCH):
        role_files = [f for f in files if f.role == role and not _is_ignored(f, config)]
        if len(role_files) < 2:
            continue

        # Pre-compute normalised text for each file.
        normalised: dict[Path, str] = {
            f.path: _normalise(f.content) for f in role_files
        }

        for fa, fb in combinations(role_files, 2):
            sim = _jaccard(normalised[fa.path], normalised[fb.path])
            if sim >= threshold:
                pct = int(sim * 100)
                rel_a = _rel(fa.path, root)
                rel_b = _rel(fb.path, root)

                # Report on the *second* file (the likely duplicate).
                violations.append(
                    Violation(
                        check_id="AL-DUP01",
                        severity=Severity.WARNING,
                        file=fb.path,
                        line=None,
                        message=(
                            f"Near-duplicate of '{rel_a}' "
                            f"({pct}% similarity). "
                            "Consolidate or differentiate these files to avoid "
                            "conflicting instructions."
                        ),
                        fix_hint=(
                            f"Merge '{rel_b}' into '{rel_a}', or add distinct "
                            "content to justify having both files."
                        ),
                    )
                )

    return violations


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _is_ignored(f: InstructionFile, config: Config) -> bool:
    normalised = f.path.as_posix()
    return any(ign in normalised for ign in config.ignore_paths)


def _rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()
