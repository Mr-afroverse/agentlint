"""Tests for AL-D03 circular reference detection."""

from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.circular_refs import run
from agentlint.config import Config
from agentlint.models import Severity

_ADAPTER = CopilotAdapter()


def _collect(root: Path):
    return _ADAPTER.collect(root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(root: Path, name: str, content: str) -> Path:
    skill_dir = root / ".github" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(content)
    return path


def _write_dispatch(root: Path, content: str) -> Path:
    gh = root / ".github"
    gh.mkdir(parents=True, exist_ok=True)
    path = gh / "copilot-instructions.md"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# AL-D03: no cycle
# ---------------------------------------------------------------------------


def test_d03_pass_no_cycle(tmp_path: Path):
    """Dispatch references two skills; neither skill references back."""
    _write_dispatch(
        tmp_path,
        "| eudr | `.github/skills/eudr/SKILL.md` | scoring |\n"
        "| sec  | `.github/skills/sec/SKILL.md`  | security |\n",
    )
    _write_skill(tmp_path, "eudr", "# EUDR\nNo back reference here.")
    _write_skill(tmp_path, "sec", "# Security\nNo back reference here.")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert d03 == []


def test_d03_pass_no_dispatch(tmp_path: Path):
    """No dispatch file — no cycles possible."""
    _write_skill(tmp_path, "only", "# Lone skill")
    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert violations == []


def test_d03_pass_single_skill(tmp_path: Path):
    """Dispatch + one skill, skill does not reference dispatch."""
    _write_dispatch(tmp_path, "| skill | `.github/skills/only/SKILL.md` | all |\n")
    _write_skill(tmp_path, "only", "# Only\nNo cross refs.")
    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert d03 == []


# ---------------------------------------------------------------------------
# AL-D03: dispatch → skill → dispatch cycle
# ---------------------------------------------------------------------------


def test_d03_fail_skill_references_dispatch(tmp_path: Path):
    """Skill explicitly references the dispatch file — creates a cycle."""
    dispatch_rel = ".github/copilot-instructions.md"
    _write_dispatch(
        tmp_path,
        "| eudr | `.github/skills/eudr/SKILL.md` | scoring |\n",
    )
    _write_skill(
        tmp_path,
        "eudr",
        f"# EUDR\nSee also `{dispatch_rel}` for context.\n",
    )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert len(d03) == 1
    assert d03[0].severity == Severity.ERROR
    assert "circular" in d03[0].message.lower()
    assert dispatch_rel in d03[0].message or "copilot-instructions" in d03[0].message


# ---------------------------------------------------------------------------
# AL-D03: skill → skill → skill cycle
# ---------------------------------------------------------------------------


def test_d03_fail_skill_to_skill_cycle(tmp_path: Path):
    """Skill A references Skill B which references Skill A — SKILL/SKILL cycle."""
    _write_dispatch(
        tmp_path,
        "| a | `.github/skills/a/SKILL.md` | all |\n"
        "| b | `.github/skills/b/SKILL.md` | all |\n",
    )
    _write_skill(tmp_path, "a", "# A\nSee `.github/skills/b/SKILL.md` for details.\n")
    _write_skill(tmp_path, "b", "# B\nSee `.github/skills/a/SKILL.md` for details.\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert len(d03) == 1
    assert "AL-D03" == d03[0].check_id
    assert "circular" in d03[0].message.lower()


# ---------------------------------------------------------------------------
# AL-D03: longer chain
# ---------------------------------------------------------------------------


def test_d03_fail_three_node_cycle(tmp_path: Path):
    """A → B → C → A."""
    _write_dispatch(
        tmp_path,
        "| a | `.github/skills/a/SKILL.md` | all |\n"
        "| b | `.github/skills/b/SKILL.md` | all |\n"
        "| c | `.github/skills/c/SKILL.md` | all |\n",
    )
    _write_skill(tmp_path, "a", "# A\nSee `.github/skills/b/SKILL.md`.\n")
    _write_skill(tmp_path, "b", "# B\nSee `.github/skills/c/SKILL.md`.\n")
    _write_skill(tmp_path, "c", "# C\nSee `.github/skills/a/SKILL.md`.\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert len(d03) == 1


# ---------------------------------------------------------------------------
# AL-D03: self-reference
# ---------------------------------------------------------------------------


def test_d03_fail_self_reference(tmp_path: Path):
    """A skill that references itself."""
    _write_dispatch(tmp_path, "| loop | `.github/skills/loop/SKILL.md` | all |\n")
    _write_skill(
        tmp_path,
        "loop",
        "# Loop\nSee `.github/skills/loop/SKILL.md` for everything.\n",
    )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    # Self-references are filtered out during graph construction (target != source).
    # A self-loop is NOT a cycle in this model — we only track cross-file cycles.
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert d03 == []


# ---------------------------------------------------------------------------
# AL-D03: no double-reporting for the same cycle
# ---------------------------------------------------------------------------


def test_d03_deduplicate_cycle(tmp_path: Path):
    """Same A↔B cycle should produce exactly one violation."""
    _write_dispatch(
        tmp_path,
        "| a | `.github/skills/a/SKILL.md` | all |\n"
        "| b | `.github/skills/b/SKILL.md` | all |\n",
    )
    # Both A and B reference each other — same cycle entered from two nodes.
    _write_skill(tmp_path, "a", "# A\nSee `.github/skills/b/SKILL.md`.\n")
    _write_skill(tmp_path, "b", "# B\nSee `.github/skills/a/SKILL.md`.\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert len(d03) == 1


# ---------------------------------------------------------------------------
# AL-D03: file-relative path references (regression for path normalization)
# ---------------------------------------------------------------------------


def test_d03_fail_file_relative_cycle(tmp_path: Path):
    """Cycle via file-relative backtick path (e.g. `../b/SKILL.md`)."""
    _write_dispatch(
        tmp_path,
        "| a | `.github/skills/a/SKILL.md` | all |\n"
        "| b | `.github/skills/b/SKILL.md` | all |\n",
    )
    # skill-a references skill-b using a path relative to its own directory:
    # .github/skills/a/ + ../b/SKILL.md → .github/skills/b/SKILL.md
    _write_skill(tmp_path, "a", "# A\nSee `../b/SKILL.md` for details.\n")
    # skill-b closes the cycle using a repo-root-relative path
    _write_skill(tmp_path, "b", "# B\nSee `.github/skills/a/SKILL.md` for details.\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert len(d03) == 1
    assert "circular" in d03[0].message.lower()


def test_d03_pass_file_relative_non_instruction(tmp_path: Path):
    """File-relative ref resolving to a non-instruction file must not cause a cycle."""
    _write_dispatch(
        tmp_path,
        "| a | `.github/skills/a/SKILL.md` | all |\n",
    )
    _write_skill(tmp_path, "a", "# A\nSee `../../../README.md` for context.\n")
    (tmp_path / "README.md").write_text("# Readme\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d03 = [v for v in violations if v.check_id == "AL-D03"]
    assert d03 == []
