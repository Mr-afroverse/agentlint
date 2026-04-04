from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Role(str, Enum):
    DISPATCH = "dispatch"  # the main instructions / dispatch file
    SKILL = "skill"  # an individual skill / rule file
    DOCS = "docs"  # general documentation file (via extra_paths)


@dataclass
class InstructionFile:
    """Normalised representation of any AI instruction file, regardless of format."""

    path: Path
    content: str
    lines: list[str]
    adapter: str  # "copilot" | "cursor" | "generic"
    role: Role
    metadata: dict = field(
        default_factory=dict
    )  # parsed frontmatter (name, description, …)


@dataclass
class Violation:
    check_id: str
    severity: Severity
    file: Path
    line: int | None
    message: str
    fix_hint: str
    auto_fixable: bool = False
    fix_data: dict = field(default_factory=dict)


@dataclass
class LintResult:
    root: Path
    files_scanned: int
    violations: list[Violation]
    adapter: str
    scanned_files: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.WARNING]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def grade(self) -> str:
        """A / B / C / D / F based on violation density per scanned file."""
        if not self.files_scanned:
            return "A"
        error_density = len(self.errors) / self.files_scanned
        warn_density = len(self.warnings) / self.files_scanned
        score = 100 - (error_density * 20) - (warn_density * 5)
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"
