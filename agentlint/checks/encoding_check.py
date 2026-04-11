"""
AL-ENC01  Instruction files must be valid UTF-8.

The adapter reads files with ``errors="replace"``, which silently substitutes
invalid bytes with the replacement character (U+FFFD).  This check re-reads
each file's raw bytes and attempts a strict UTF-8 decode so that encoding
problems surface as an explicit lint error instead of corrupting content
downstream.

Runs on SKILL, DISPATCH, and DOCS files.
"""

from __future__ import annotations

from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation


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

        try:
            raw = f.path.read_bytes()
        except OSError:
            continue

        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            # Report approximate line number from byte offset.
            approx_line = raw[: exc.start].count(b"\n") + 1
            violations.append(
                Violation(
                    check_id="AL-ENC01",
                    severity=Severity.ERROR,
                    file=f.path,
                    line=approx_line,
                    message=(
                        f"File contains non-UTF-8 bytes at byte offset {exc.start} "
                        f"(0x{raw[exc.start]:02X}). Content read with replacement "
                        "characters — instructions may be silently corrupted."
                    ),
                    fix_hint=(
                        "Re-save the file as UTF-8 (without BOM) in your editor."
                    ),
                )
            )

    return violations
