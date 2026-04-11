"""
AL-V01  Validate documented numbers against their referenced source constants.

When a source annotation includes a constant path — e.g.
  ``(Source: agents/notification_agent.py:NotificationConfig.minimum_risk_score)``
— the check resolves the file, extracts the constant's current value, and
compares it to the number in the documentation.

Annotations without a constant path (plain ``(Source: constants.py)``) are
left to AL-N01 and ignored here.

Extraction strategy
-------------------
For ``.py`` files the extractor first tries a full Python AST parse.  This
correctly handles class-level vs module-level scoping, type-annotated
assignments, and simple negative literals.  If the AST cannot resolve the
constant to a numeric literal the extractor falls back to the original regex
approach so that no previously-passing files regress.

For all other file types (YAML, JSON, TypeScript, …) only the regex extractor
runs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation
from agentlint.checks._utils import _CODE_FENCE_RE

# (Source: filepath.ext:Dotted.constant_name)
_SOURCE_CONST_RE = re.compile(r"\(Source:\s*([\w/\\.-]+\.\w{1,6}):([\w.]+)\)")

# Any integer or decimal number token, including negative literals.
# (?<!\w) prevents matching the digits inside a word or after a digit (e.g.
# the "15" in "10-15" is still caught, but "-15" is NOT spuriously matched
# when the preceding character is a digit).
_NUMBER_RE = re.compile(r"(?<!\w)(-?\d+(?:\.\d+)?)\b")


def _resolve_file(root: Path, source_roots: list[str], ref: str) -> Path | None:
    """Try to locate *ref* relative to *root* or under configured source_roots.

    Returns None if the resolved path escapes the project root (path traversal guard).
    """
    root_resolved = root.resolve()
    direct = root / ref
    try:
        if direct.resolve().is_relative_to(root_resolved) and direct.is_file():
            return direct
    except OSError:
        pass
    for sr in source_roots:
        candidate = root / sr / ref
        try:
            if (
                candidate.resolve().is_relative_to(root_resolved)
                and candidate.is_file()
            ):
                return candidate
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# Regex extractor — original implementation, used as fallback / non-Python
# ---------------------------------------------------------------------------


def _extract_constant_value(content: str, constant_path: str) -> str | None:
    """Extract the numeric literal assigned to *constant_path* in file content.

    Handles common assignment styles:
      MODULE_LEVEL = 30
      class_attr: int = 30
      CONSTANT: float = 3.14

    For Python files prefer ``_extract_constant_value_ast`` which understands
    class scoping.  This function remains the fallback and the extractor for
    non-Python source files.
    """
    name = constant_path.rsplit(".", 1)[-1]
    pattern = re.compile(
        rf"\b{re.escape(name)}\b\s*(?::\s*[\w\[\], |]+\s*)?=\s*(\d+(?:\.\d+)?)"
    )
    match = pattern.search(content)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# AST extractor — Python-only, scope-aware
# ---------------------------------------------------------------------------


def _ast_const_to_str(node: ast.expr) -> str | None:
    """Return the string representation of a numeric AST node, or *None*."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return str(node.value)
    # Unary minus: -42, -3.14
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        return str(-node.operand.value)
    return None


def _extract_constant_value_ast(content: str, constant_path: str) -> str | None:
    """Extract *constant_path* from Python source using the AST.

    *constant_path* uses dot notation:
    - ``ATTR`` — searches the module body
    - ``ClassName.ATTR`` — searches inside ``ClassName``
    - ``Outer.Inner.ATTR`` — navigates nested class definitions

    Returns the numeric string value (e.g. ``"42"``, ``"3.14"``, ``"-1"``)
    or *None* when the constant cannot be resolved to a numeric literal.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    parts = constant_path.split(".")
    attr_name = parts[-1]
    class_path = parts[:-1]

    # Navigate to the target scope through nested class definitions.
    scope_body: list[ast.stmt] = list(tree.body)
    for class_name in class_path:
        found = next(
            (
                node
                for node in scope_body
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        if found is None:
            return None
        scope_body = list(found.body)

    # Scan the resolved scope for an assignment to `attr_name`.
    for node in scope_body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == attr_name:
                    return _ast_const_to_str(node.value)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == attr_name
                and node.value is not None
            ):
                return _ast_const_to_str(node.value)

    return None


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

                # Use AST for Python files; fall back to regex for other languages.
                if target.suffix == ".py":
                    actual = _extract_constant_value_ast(content, const_path)
                    if actual is None:
                        actual = _extract_constant_value(content, const_path)
                else:
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
                                f"Documented value `{doc_value}` ≠ source "
                                f"`{const_path}` = `{actual}` in `{file_ref}`"
                            ),
                            fix_hint=f"Update the value to `{actual}` or correct the source.",
                        )
                    )

    return violations
