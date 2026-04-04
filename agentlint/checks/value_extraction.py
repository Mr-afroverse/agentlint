"""
AL-V01  Validate documented numbers against their referenced source constants.

When a source annotation includes a constant path — e.g.
  ``(Source: agents/notification_agent.py:NotificationConfig.minimum_risk_score)``
— the check resolves the file, extracts the constant's current value, and
compares it to the number in the documentation.

Annotations without a constant path (plain ``(Source: constants.py)``) are
left to AL-N01 and ignored here.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation

# (Source: filepath.ext:Dotted.constant_name)
_SOURCE_CONST_RE = re.compile(r"\(Source:\s*([\w/\\.-]+\.\w{1,6}):([\w.]+)\)")

# Any integer or decimal number token
_NUMBER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")

# Code fence toggle
_CODE_FENCE_RE = re.compile(r"^```(?!`)")


def _resolve_file(root: Path, source_roots: list[str], ref: str) -> Path | None:
    """Try to locate *ref* relative to *root* or under configured source_roots."""
    direct = root / ref
    if direct.is_file():
        return direct
    for sr in source_roots:
        candidate = root / sr / ref
        if candidate.is_file():
            return candidate
    return None


def _extract_constant_value(content: str, constant_path: str) -> str | None:
    """Extract the numeric literal assigned to *constant_path* in file content.

    Handles common assignment styles:
      MODULE_LEVEL = 30
      class_attr: int = 30
      CONSTANT: float = 3.14
    """
    name = constant_path.rsplit(".", 1)[-1]
    pattern = re.compile(
        rf"\b{re.escape(name)}\b\s*(?::\s*[\w\[\], |]+\s*)?=\s*(\d+(?:\.\d+)?)"
    )
    match = pattern.search(content)
    return match.group(1) if match else None


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for sf in files:
        in_code = False
        for lineno, line in enumerate(sf.lines, start=1):
            if _CODE_FENCE_RE.match(line.strip()):
                in_code = not in_code
            if in_code:
                continue

            for annot in _SOURCE_CONST_RE.finditer(line):
                file_ref = annot.group(1)
                const_path = annot.group(2)

                # Rightmost number preceding the annotation on this line
                before_text = line[: annot.start()]
                numbers = list(_NUMBER_RE.finditer(before_text))
                if not numbers:
                    continue  # no number to validate

                doc_value = numbers[-1].group(1)

                # Resolve the source file
                target = _resolve_file(root, config.source_roots, file_ref)
                if target is None:
                    violations.append(
                        Violation(
                            check_id="AL-V01",
                            severity=Severity.WARNING,
                            file=sf.path,
                            line=lineno,
                            message=f"Source file not found for value check: `{file_ref}`",
                            fix_hint="Update the file path in the source annotation.",
                        )
                    )
                    continue

                try:
                    content = target.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                actual = _extract_constant_value(content, const_path)
                if actual is None:
                    violations.append(
                        Violation(
                            check_id="AL-V01",
                            severity=Severity.WARNING,
                            file=sf.path,
                            line=lineno,
                            message=f"Could not extract `{const_path}` from `{file_ref}`",
                            fix_hint="Check that the constant name matches the code.",
                        )
                    )
                    continue

                if doc_value != actual:
                    violations.append(
                        Violation(
                            check_id="AL-V01",
                            severity=Severity.ERROR,
                            file=sf.path,
                            line=lineno,
                            message=(
                                f"Documented value `{doc_value}` \u2260 source "
                                f"`{const_path}` = `{actual}` in `{file_ref}`"
                            ),
                            fix_hint=f"Update the value to `{actual}` or correct the source.",
                        )
                    )

    return violations
