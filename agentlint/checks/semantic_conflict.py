"""
AL-CONF01  Contradictory directives detected across instruction files.

Scans all SKILL and DISPATCH files for imperative directive lines and flags
when the *same subject* appears with contradictory polarities in different
files.  Examples of contradictions this catches:

  File A: "Always use semicolons."
  File B: "Never use semicolons."

  File A: "Prefer single quotes."
  File B: "Avoid single quotes."

  File A: "Do not use tabs."
  File B: "Use tabs for indentation."

**Algorithm**

1. For each line, check whether it starts with (or contains early) one of a
   small set of *positive* polarity words (``always``, ``use``, ``do``,
   ``prefer``, ``require``, ``must``, ``should``) or *negative* polarity
   words (``never``, ``avoid``, ``don't``, ``do not``, ``don't use``,
   ``avoid using``, ``instead avoid``, ``never use``, ``no``, ``prohibit``,
   ``must not``, ``should not``).
2. The *predicate* is extracted by stripping the polarity word from the front
   of the matched phrase and normalising (lower-case, collapse whitespace,
   strip leading articles/punctuation).
3. Predicates are stored per-file as ``{normalised_predicate: (polarity, file, line)}``.
4. After scanning all files, any predicate that appears with both polarities
   in *different files* is flagged as a conflict.

Zero-config.  Runs on SKILL and DISPATCH files.  WARNING severity by default
(conflicts may be intentional overrides for specific contexts).

Suppressible per-line with ``# agentlint: disable=AL-CONF01``.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

# ---------------------------------------------------------------------------
# Polarity pattern pairs
# Each entry: (polarity, compiled_regex_that_matches_start_of_directive_phrase)
# The regex must have exactly ONE capturing group — the predicate remainder.
# ---------------------------------------------------------------------------
_POSITIVE = "positive"
_NEGATIVE = "negative"

# These match at the beginning of a line (after optional whitespace/bullets).
# Group 1 captures the rest of the phrase after the polarity word.
_POLARITY_RES: list[tuple[str, re.Pattern[str]]] = [
    # Negative first — order matters when checking both lists
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)(?:never use|never)\s+(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)(?:do\s+not\s+use|do\s+not)\s+(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)don'?t\s+(?:use\s+)?(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)avoid\s+(?:using\s+)?(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)must\s+not\s+(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)should\s+not\s+(.+)")),
    (_NEGATIVE, re.compile(r"(?i)(?:^|[-*•]\s*)(?:prohibit|forbid)\s+(.+)")),
    # Positive
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)always\s+(?:use\s+)?(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)use\s+(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)prefer\s+(?:using\s+)?(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)must\s+(?:use\s+)?(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)should\s+(?:use\s+)?(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)require\s+(.+)")),
    (_POSITIVE, re.compile(r"(?i)(?:^|[-*•]\s*)always\s+(.+)")),
]

# Limit predicate to the first ~8 words to avoid over-matching long prose
_MAX_PREDICATE_WORDS = 8

# Strip trailing punctuation and filler from predicate tail
_TRAILING_RE = re.compile(r"[.,:;!?)\]]+$")
# Strip leading "use " left over when negation phrase is "must not use", "do not use" etc.
_LEADING_USE_RE = re.compile(r"^use\s+", re.I)
# Strip leading articles / conjunctions
_LEADING_FILLER_RE = re.compile(r"^(?:the|a|an|to|for|of|in|on|with|at|from)\s+", re.I)

_DISABLE_RE = re.compile(r"#\s*agentlint:\s*disable=AL-CONF01", re.I)


def _normalise_predicate(raw: str) -> str:
    """Return a stable lower-cased key from a raw predicate string."""
    # Take only up to N words to avoid false-unique long phrases
    words = raw.split()[:_MAX_PREDICATE_WORDS]
    text = " ".join(words)
    text = _TRAILING_RE.sub("", text).strip()
    # Strip residual leading "use " — left by "do not use X" / "must not use X" patterns
    text = _LEADING_USE_RE.sub("", text)
    text = _LEADING_FILLER_RE.sub("", text)
    return text.lower().strip()


def _predicates_overlap(a: str, b: str) -> bool:
    """True when *a* and *b* refer to the same subject.

    Exact equality OR one predicate is a token-prefix of the other (minimum
    2 shared leading words).  This handles cases like "tabs" matching
    "tabs for indentation", or "double quotes" matching "double quotes for strings".
    """
    if a == b:
        return True
    a_words = a.split()
    b_words = b.split()
    n = min(len(a_words), len(b_words))
    if n < 1:
        return False
    # Single shared word only allowed when that word is reasonably long (≥ 4 chars)
    if n == 1:
        return a_words[0] == b_words[0] and len(a_words[0]) >= 4
    return a_words[:n] == b_words[:n]


def _extract_directives(
    f: InstructionFile,
) -> list[tuple[str, str, int]]:
    """Return [(polarity, normalised_predicate, lineno)] for *f*."""
    results: list[tuple[str, str, int]] = []
    for lineno, raw_line in enumerate(f.lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if _DISABLE_RE.search(raw_line):
            continue
        for polarity, pat in _POLARITY_RES:
            m = pat.search(line)
            if m:
                predicate = _normalise_predicate(m.group(1))
                if len(predicate) >= 3:  # skip trivially short predicates
                    results.append((polarity, predicate, lineno))
                break  # only fire the first matching pattern per line
    return results


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    # Only scan SKILL and DISPATCH files
    target_files = [
        f
        for f in files
        if f.role in (Role.SKILL, Role.DISPATCH) and not _is_ignored(f, config)
    ]

    if len(target_files) < 2:
        return []

    # Build index: predicate → list of (polarity, file, lineno)
    index: dict[str, list[tuple[str, Path, int]]] = {}
    for f in target_files:
        for polarity, predicate, lineno in _extract_directives(f):
            index.setdefault(predicate, []).append((polarity, f.path, lineno))

    violations: list[Violation] = []
    reported: set[frozenset[object]] = set()

    # Compare every pair of predicate keys for semantic overlap
    predicate_keys = list(index.keys())
    for i, pred_a in enumerate(predicate_keys):
        for pred_b in predicate_keys[i:]:
            if not _predicates_overlap(pred_a, pred_b):
                continue

            # Merge the two occurrence lists
            combined = index[pred_a] + (index[pred_b] if pred_b != pred_a else [])
            positives = [(fp, ln) for pol, fp, ln in combined if pol == _POSITIVE]
            negatives = [(fp, ln) for pol, fp, ln in combined if pol == _NEGATIVE]

            if not positives or not negatives:
                continue

            # Only flag cross-file conflicts
            pos_files = {fp for fp, _ in positives}
            neg_files = {fp for fp, _ in negatives}
            if pos_files == neg_files:
                continue

            # Report on the negative file side
            # Canonical topic: the shorter of the two overlapping predicates.
            # Used as the dedup key so that different (pred_a, pred_b) pairs that
            # resolve to the same subject don't produce duplicate violations for
            # the same file pair.
            topic = pred_a if len(pred_a) <= len(pred_b) else pred_b
            for neg_file, neg_line in negatives:
                for pos_file, _ in positives:
                    if pos_file == neg_file:
                        continue
                    dedup_key: frozenset[object] = frozenset(
                        {neg_file, pos_file, topic}
                    )
                    if dedup_key in reported:
                        continue
                    reported.add(dedup_key)

                    rel_pos = _rel(pos_file, root)
                    rel_neg = _rel(neg_file, root)
                    violations.append(
                        Violation(
                            check_id="AL-CONF01",
                            severity=Severity.WARNING,
                            file=neg_file,
                            line=neg_line,
                            message=(
                                f"Contradictory directive for '{topic}': "
                                f"'{rel_pos}' permits it, '{rel_neg}' forbids it."
                            ),
                            fix_hint=(
                                "Reconcile the two files: either remove one directive, "
                                "narrow its scope, or add a comment explaining the "
                                "intentional override."
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
