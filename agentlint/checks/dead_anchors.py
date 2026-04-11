"""
AL-F02  Internal anchor links must resolve to headings in the same file.

Flags `[text](#anchor)` references where the target anchor does not correspond
to any heading in the document.

Anchor slug generation follows GitHub Flavored Markdown rules:
  - Lowercase all heading text
  - Strip everything that is not a letter, digit, space, or hyphen
  - Replace consecutive spaces/underscores with a single hyphen
  - Remove leading/trailing hyphens

Only same-file `#anchor` links are checked.  Cross-file links (`file.md#anchor`,
`http://…#anchor`) are ignored.  Runs on SKILL, DISPATCH, and DOCS files.

Lines inside fenced code blocks are skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation
from agentlint.checks._utils import _CODE_FENCE_RE

# Matches `[text](#anchor)` but NOT `[text](file.md#anchor)` or `[text](http://…)`
_LOCAL_ANCHOR_RE = re.compile(r"\[(?:[^\]]*)]\(#([^)]+)\)")

# Matches ATX headings: `# Heading`, `## Heading`, etc. (1–6 hashes)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)")


def _to_slug(heading_text: str) -> str:
    """Convert a heading string to its GitHub-style anchor slug."""
    text = heading_text.strip()
    # Strip inline markdown: remove backtick markers but keep inner text,
    # resolve link syntax [label](url) → label, strip bold/italic/strikethrough
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~]", "", text)
    text = text.lower()
    # Keep only letters, digits, spaces, and hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace each space/underscore with its own hyphen (preserves double-hyphens
    # that arise when punctuation like '&' is stripped, e.g. "A & B" → "a--b")
    text = re.sub(r"[\s_]", "-", text)
    text = text.strip("-")
    return text


def _collect_heading_slugs(lines: list[str]) -> set[str]:
    """Return all heading anchor slugs defined in the file."""
    slugs: set[str] = set()
    in_code = False
    for line in lines:
        if _CODE_FENCE_RE.match(line.strip()):
            in_code = not in_code
        if in_code:
            continue
        m = _HEADING_RE.match(line)
        if m:
            slugs.add(_to_slug(m.group(1)))
    return slugs


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        known_slugs = _collect_heading_slugs(f.lines)
        in_code = False

        for lineno, line in enumerate(f.lines, start=1):
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code
            if in_code:
                continue

            for m in _LOCAL_ANCHOR_RE.finditer(line):
                anchor = m.group(1).strip()
                if anchor not in known_slugs:
                    violations.append(
                        Violation(
                            check_id="AL-F02",
                            severity=Severity.WARNING,
                            file=f.path,
                            line=lineno,
                            message=(
                                f"Dead anchor link: `#{anchor}` does not match "
                                f"any heading in this file."
                            ),
                            fix_hint=(
                                f"Add a heading that resolves to `#{anchor}`, "
                                "or correct the anchor to match an existing heading."
                            ),
                        )
                    )

    return violations
