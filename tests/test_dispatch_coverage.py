from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.dispatch_coverage import run
from agentlint.config import Config
from agentlint.models import Severity


_ADAPTER = CopilotAdapter()


def _collect(root: Path):
    return _ADAPTER.collect(root)


# ---------------------------------------------------------------------------
# AL-D01: skill path referenced in dispatch → must exist on disk
# ---------------------------------------------------------------------------


def test_d01_pass_all_paths_exist(repo_root: Path):
    files = _collect(repo_root)
    violations = run(files, Config(), repo_root)
    d01 = [v for v in violations if v.check_id == "AL-D01"]
    assert d01 == [], "Expected no AL-D01 violations when all paths exist."


def test_d01_fail_missing_skill_file(tmp_path: Path):
    # Dispatch references a skill that doesn't exist on disk
    (tmp_path / ".github" / "skills" / "eudr-standards").mkdir(parents=True)
    dispatch = (
        "| `eudr` | `.github/skills/eudr-standards/SKILL.md` | Any scoring |\n"
        "| `ghost` | `.github/skills/ghost/SKILL.md` | Ghost skill |\n"
    )
    (tmp_path / ".github" / "copilot-instructions.md").write_text(dispatch)
    (tmp_path / ".github" / "skills" / "eudr-standards" / "SKILL.md").write_text(
        "# EUDR"
    )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d01 = [v for v in violations if v.check_id == "AL-D01"]
    assert len(d01) == 1
    assert "ghost" in d01[0].message
    assert d01[0].severity == Severity.ERROR


# ---------------------------------------------------------------------------
# AL-D02: skill on disk → must be referenced in dispatch
# ---------------------------------------------------------------------------


def test_d02_pass_all_skills_in_dispatch(repo_root: Path):
    files = _collect(repo_root)
    violations = run(files, Config(), repo_root)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert d02 == []


def test_d02_fail_skill_not_in_dispatch(tmp_path: Path):
    gh = tmp_path / ".github"
    # Use .github/instructions/ — collected as SKILLs and require explicit dispatch entries
    (gh / "instructions").mkdir(parents=True)
    (gh / "instructions" / "referenced-rule.md").write_text(
        "---\napplyTo: '**'\n---\n# Referenced"
    )
    (gh / "instructions" / "orphan-rule.md").write_text(
        "---\napplyTo: '**'\n---\n# Orphan"
    )
    # Dispatch only mentions referenced-rule
    dispatch = "`.github/instructions/referenced-rule.md` for linting\n"
    (gh / "copilot-instructions.md").write_text(dispatch)

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert len(d02) == 1
    assert "orphan" in d02[0].message.lower()


def test_no_dispatch_file_returns_empty(tmp_path: Path):
    # No dispatch file at all — checks should return nothing gracefully
    skills = tmp_path / ".github" / "skills" / "my-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# My Skill")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# AL-D05: duplicate skill names
# ---------------------------------------------------------------------------


def test_d05_no_violation_when_names_are_unique(tmp_path: Path):
    skills = tmp_path / ".github" / "skills"
    for name in ("alpha", "beta"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\n---\n# {name}", encoding="utf-8"
        )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d05 = [v for v in violations if v.check_id == "AL-D05"]
    assert d05 == []


def test_d05_fires_when_two_skills_share_name(tmp_path: Path):
    skills = tmp_path / ".github" / "skills"
    for subdir in ("dir-a", "dir-b"):
        d = skills / subdir
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: shared-name\n---\n# Shared", encoding="utf-8"
        )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d05 = [v for v in violations if v.check_id == "AL-D05"]
    assert len(d05) == 2
    assert all(v.check_id == "AL-D05" for v in d05)
    assert "shared-name" in d05[0].message


def test_d05_uses_parent_dir_name_when_no_frontmatter(tmp_path: Path):
    skills = tmp_path / ".github" / "skills"
    for subdir in ("same-dir", "same-dir-copy"):
        d = skills / subdir
        d.mkdir(parents=True)
        # No frontmatter — name derived from parent dir, which differs → no dupe
        (d / "SKILL.md").write_text("# Content", encoding="utf-8")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d05 = [v for v in violations if v.check_id == "AL-D05"]
    assert d05 == []


def test_d05_fires_without_dispatch_file(tmp_path: Path):
    # AL-D05 must work even with no dispatch file present
    skills = tmp_path / ".github" / "skills"
    for subdir in ("first", "second"):
        d = skills / subdir
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: duplicate\n---\n# Dup", encoding="utf-8"
        )

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d05 = [v for v in violations if v.check_id == "AL-D05"]
    assert len(d05) == 2


# ---------------------------------------------------------------------------
# CHECK-11: VS Code XML auto-discovery suppression for .github/skills/**
# ---------------------------------------------------------------------------


def test_d02_no_violation_for_vscode_skills_dir(tmp_path: Path):
    """Skills under .github/skills/ are auto-discovered by VS Code — no AL-D02."""
    skills = tmp_path / ".github" / "skills" / "my-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# My Skill")
    # Dispatch file exists but does NOT reference the skill
    (tmp_path / ".github" / "copilot-instructions.md").write_text("# Instructions\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert d02 == [], (
        "AL-D02 must not fire for .github/skills/ — VS Code handles dispatch"
    )


def test_d02_still_fires_for_instructions_skills(tmp_path: Path):
    """Skills under .github/instructions/ still require a dispatch entry."""
    gh = tmp_path / ".github"
    (gh / "instructions").mkdir(parents=True)
    (gh / "instructions" / "my-rule.md").write_text("---\napplyTo: '**'\n---\n# Rule")
    (gh / "copilot-instructions.md").write_text("# Instructions\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert len(d02) == 1, (
        "AL-D02 must fire for .github/instructions/ skills not in dispatch"
    )


def test_d02_vscode_skills_with_dispatch_entry_no_violation(tmp_path: Path):
    """Skills under .github/skills/ with a dispatch entry: still no violation."""
    skills = tmp_path / ".github" / "skills" / "my-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# My Skill")
    # Dispatch explicitly lists the skill anyway
    dispatch = "| skill | `.github/skills/my-skill/SKILL.md` | anything |\n"
    (tmp_path / ".github" / "copilot-instructions.md").write_text(dispatch)

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert d02 == []


def test_d02_mixed_skills_only_warns_non_vscode(tmp_path: Path):
    """Mix: .github/skills/ (suppressed) + .github/instructions/ (fires)."""
    gh = tmp_path / ".github"
    (gh / "skills" / "auto-skill").mkdir(parents=True)
    (gh / "skills" / "auto-skill" / "SKILL.md").write_text("# Auto")
    (gh / "instructions").mkdir()
    (gh / "instructions" / "manual-rule.md").write_text(
        "---\napplyTo: '**'\n---\n# Manual"
    )
    (gh / "copilot-instructions.md").write_text("# Instructions\n")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    # Only the .github/instructions/ skill fires — not the .github/skills/ one
    assert len(d02) == 1
    assert "manual-rule" in d02[0].message
