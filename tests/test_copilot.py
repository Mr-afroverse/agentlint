from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.models import Role

_ADAPTER = CopilotAdapter()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_via_dispatch_file(tmp_path: Path):
    github = tmp_path / ".github"
    github.mkdir()
    (github / "copilot-instructions.md").write_text("# dispatch", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_via_skills_dir(tmp_path: Path):
    (tmp_path / ".github" / "skills").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_via_instructions_dir(tmp_path: Path):
    (tmp_path / ".github" / "instructions").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_false_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# collect() — dispatch
# ---------------------------------------------------------------------------


def test_collect_dispatch(tmp_path: Path):
    github = tmp_path / ".github"
    github.mkdir()
    (github / "copilot-instructions.md").write_text("# Global", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.DISPATCH
    assert files[0].adapter == "copilot"


# ---------------------------------------------------------------------------
# collect() — .github/instructions/*.md (SKILL, VS Code 1.99+ format)
# ---------------------------------------------------------------------------


def test_collect_instructions_dir_as_skill(tmp_path: Path):
    instr_dir = tmp_path / ".github" / "instructions"
    instr_dir.mkdir(parents=True)
    (instr_dir / "python.md").write_text(
        "---\napplyTo: '**/*.py'\n---\n# Python rules", encoding="utf-8"
    )
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.SKILL
    assert files[0].adapter == "copilot"
    assert files[0].path.name == "python.md"


def test_collect_multiple_instruction_files(tmp_path: Path):
    instr_dir = tmp_path / ".github" / "instructions"
    instr_dir.mkdir(parents=True)
    (instr_dir / "python.md").write_text("# Python", encoding="utf-8")
    (instr_dir / "typescript.md").write_text("# TypeScript", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    names = {f.path.name for f in files}
    assert names == {"python.md", "typescript.md"}
    assert all(f.role == Role.SKILL for f in files)


def test_collect_instructions_and_dispatch_together(tmp_path: Path):
    github = tmp_path / ".github"
    github.mkdir()
    (github / "copilot-instructions.md").write_text("# Global", encoding="utf-8")
    instr_dir = github / "instructions"
    instr_dir.mkdir()
    (instr_dir / "tests.md").write_text("# Test conventions", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 2
    assert any(f.role == Role.DISPATCH for f in files)
    assert any(f.role == Role.SKILL for f in files)


def test_collect_instructions_frontmatter_parsed(tmp_path: Path):
    instr_dir = tmp_path / ".github" / "instructions"
    instr_dir.mkdir(parents=True)
    (instr_dir / "style.md").write_text(
        "---\napplyTo: '**/*.ts'\ndescription: TypeScript style\n---\n# TS",
        encoding="utf-8",
    )
    files = _ADAPTER.collect(tmp_path)
    assert files[0].metadata.get("applyTo") == "**/*.ts"


def test_collect_empty_when_nothing_present(tmp_path: Path):
    files = _ADAPTER.collect(tmp_path)
    assert files == []
