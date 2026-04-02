"""
AL-T01  Two skills whose trigger descriptions share too many keywords may cause
        the agent to pick the wrong skill when both triggers could apply.

Overlap is measured with Jaccard similarity over non-stop-word tokens.
Threshold is configurable (default 0.5 = 50% shared keywords).

Trigger text is extracted from:
  1. The dispatch table row for the skill (preferred), or
  2. The skill's frontmatter `description` field.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "when",
        "any", "new", "adding", "modifying", "writing", "using", "with",
        "before", "after", "all", "this", "that", "by", "be", "is", "are",
        "it", "its", "my", "your", "we", "our", "not", "but", "from",
    }
)


def _extract_trigger(dispatch_content: str, skill_rel: str) -> str | None:
    """Return the trigger column text for *skill_rel* from the dispatch table."""
    pattern = re.compile(
        r"\|[^|]*\|\s*`?" + re.escape(skill_rel) + r"`?\s*\|([^|]+)\|",
        re.IGNORECASE,
    )
    m = pattern.search(dispatch_content)
    return m.group(1).strip() if m else None


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    if not config.checks.get("trigger-overlap", True):
        return []

    dispatch_files = [f for f in files if f.role == Role.DISPATCH]
    skill_files = [f for f in files if f.role == Role.SKILL]

    if not dispatch_files or len(skill_files) < 2:
        return []

    dispatch_content = dispatch_files[0].content
    threshold = config.trigger_overlap_threshold

    # Build (skill_file, trigger_text, keyword_set) triples
    entries: list[tuple[InstructionFile, str, set[str]]] = []
    for sf in skill_files:
        rel = sf.path.relative_to(root).as_posix()
        trigger = _extract_trigger(dispatch_content, rel) or sf.metadata.get(
            "description", ""
        )
        if trigger:
            kw = _keywords(trigger)
            if kw:
                entries.append((sf, trigger, kw))

    violations: list[Violation] = []
    seen: set[frozenset] = set()

    for i, (sf_a, trig_a, kw_a) in enumerate(entries):
        for sf_b, trig_b, kw_b in entries[i + 1 :]:
            pair: frozenset = frozenset({sf_a.path, sf_b.path})
            if pair in seen:
                continue
            seen.add(pair)

            sim = _jaccard(kw_a, kw_b)
            if sim >= threshold:
                shared = sorted(kw_a & kw_b)
                rel_b = sf_b.path.relative_to(root).as_posix()
                violations.append(
                    Violation(
                        check_id="AL-T01",
                        severity=Severity.WARNING,
                        file=sf_a.path,
                        line=None,
                        message=(
                            f"Trigger overlap ({sim:.0%} shared keywords) with "
                            f"`{rel_b}`.\n"
                            f"      Shared keywords: {', '.join(shared)}\n"
                            f"      This trigger: {trig_a[:80]}\n"
                            f"      Other trigger: {trig_b[:80]}"
                        ),
                        fix_hint=(
                            "Tighten each trigger so it applies to only one skill. "
                            "Add distinguishing words that the other skill's trigger lacks."
                        ),
                    )
                )

    return violations
