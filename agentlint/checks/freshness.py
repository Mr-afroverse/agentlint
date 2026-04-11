"""
AL-FRESH01  Stale date detection.

Warns when instruction files contain dates older than a configurable
threshold.  Useful for catching stale deployment guides, version references,
or dated instructions that may no longer reflect current state.

Activated via ``.agentlint.yml``:

    stale_days: 180    # warn on any date older than 180 days

Set ``stale_days: 0`` (default) to disable entirely.

Supported date formats:

    2024-01-15             ISO-8601
    2024/01/15             slash-separated
    January 15, 2024       long month name
    Jan 15, 2024           short month name
    15 January 2024        day-first long
    15 Jan 2024            day-first short

Lines inside fenced code blocks are skipped.  Future dates (beyond today) are
never flagged.  Violations are warnings.

Suppressible per-line with ``# agentlint: disable=AL-FRESH01``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from agentlint.checks._utils import _CODE_FENCE_RE
from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation

# ---------------------------------------------------------------------------
# Month name vocabulary
# ---------------------------------------------------------------------------
_MONTH_LONG = (
    "January|February|March|April|May|June|July"
    "|August|September|October|November|December"
)
_MONTH_SHORT = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_MONTHS = f"{_MONTH_LONG}|{_MONTH_SHORT}"

# ---------------------------------------------------------------------------
# Date patterns — (compiled regex, strptime format string or None for named)
# ---------------------------------------------------------------------------
_DATE_RES: list[tuple[re.Pattern[str], str | None]] = [
    # ISO-8601: 2024-01-15
    (
        re.compile(r"\b(\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b"),
        "%Y-%m-%d",
    ),
    # Slash-separated: 2024/01/15
    (
        re.compile(r"\b(\d{4}/(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01]))\b"),
        "%Y/%m/%d",
    ),
    # "January 15, 2024"  /  "Jan 15, 2024"
    (
        re.compile(
            rf"\b((?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})\b",
            re.IGNORECASE,
        ),
        None,
    ),
    # "15 January 2024"  /  "15 Jan 2024"
    (
        re.compile(
            rf"\b(\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}})\b",
            re.IGNORECASE,
        ),
        None,
    ),
]

_NAMED_FMTS = (
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def _parse_date(text: str, fmt: str | None) -> date | None:
    """Return a ``date`` or *None* if parsing fails."""
    if fmt is not None:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            return None
    # Named-month: normalise whitespace, strip trailing comma artefacts, then
    # try every recognised format.
    normalised = re.sub(r"\s+", " ", text).strip().rstrip(",")
    for f in _NAMED_FMTS:
        try:
            return datetime.strptime(normalised, f).date()
        except ValueError:
            continue
    return None


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    if not config.stale_days:
        return []

    today = date.today()
    violations: list[Violation] = []

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        in_fence = False
        for lineno, raw in enumerate(f.content.splitlines(), 1):
            if _CODE_FENCE_RE.match(raw.strip()):
                in_fence = not in_fence
            if in_fence:
                continue

            if "agentlint: disable=AL-FRESH01" in raw:
                continue

            line = raw.rstrip()
            seen_spans: list[tuple[int, int]] = []

            for pattern, fmt in _DATE_RES:
                for m in pattern.finditer(line):
                    # Skip overlapping matches (e.g. ISO already caught part
                    # of a named-month pattern on the same span).
                    span = m.span()
                    if any(
                        span[0] < end and span[1] > start for start, end in seen_spans
                    ):
                        continue

                    d = _parse_date(m.group(1), fmt)
                    if d is None:
                        continue
                    if d > today:
                        continue  # future date — not stale

                    age_days = (today - d).days
                    if age_days >= config.stale_days:
                        seen_spans.append(span)
                        violations.append(
                            Violation(
                                check_id="AL-FRESH01",
                                severity=Severity.WARNING,
                                file=f.path,
                                line=lineno,
                                message=(
                                    f"Date '{m.group(1)}' is {age_days} days old "
                                    f"(threshold: {config.stale_days} days). "
                                    "Update or remove the outdated date reference."
                                ),
                                fix_hint="Update the date or add context explaining why it is still accurate.",
                            )
                        )

    return violations
