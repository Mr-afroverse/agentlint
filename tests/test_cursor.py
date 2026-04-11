from __future__ import annotations

from pathlib import Path

from agentlint.adapters.cursor import CursorAdapter
from agentlint.models import Role

_ADAPTER = CursorAdapter()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_via_cursorrules(tmp_path: Path):
    (tmp_path / ".cursorrules").write_text("# rules", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_via_rules_dir(tmp_path: Path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_false_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# collect() — .cursorrules (DISPATCH)
# ---------------------------------------------------------------------------


def test_collect_dispatch_from_cursorrules(tmp_path: Path):
    (tmp_path / ".cursorrules").write_text("# Global rules", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.DISPATCH
    assert files[0].adapter == "cursor"
    assert files[0].path.name == ".cursorrules"


def test_collect_dispatch_content_read_correctly(tmp_path: Path):
    content = "Always write tests.\n"
    (tmp_path / ".cursorrules").write_text(content, encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert files[0].content == content
    assert files[0].lines == ["Always write tests."]


# ---------------------------------------------------------------------------
# collect() — .cursor/rules/*.mdc (SKILL)
# ---------------------------------------------------------------------------


def test_collect_skill_from_mdc_file(tmp_path: Path):
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "testing.mdc").write_text("# Testing rules", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.SKILL
    assert files[0].adapter == "cursor"
    assert files[0].path.name == "testing.mdc"


def test_collect_multiple_mdc_files(tmp_path: Path):
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "alpha.mdc").write_text("# Alpha", encoding="utf-8")
    (rules_dir / "beta.mdc").write_text("# Beta", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    names = {f.path.name for f in files}
    assert names == {"alpha.mdc", "beta.mdc"}
    assert all(f.role == Role.SKILL for f in files)


def test_collect_mdc_frontmatter_parsed(tmp_path: Path):
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "style.mdc").write_text(
        "---\ndescription: Style rules\n---\n# Style", encoding="utf-8"
    )
    files = _ADAPTER.collect(tmp_path)
    assert files[0].metadata.get("description") == "Style rules"


def test_md_files_in_rules_dir_not_collected(tmp_path: Path):
    # CursorAdapter only collects *.mdc, not *.md
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "note.md").write_text("# Note", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert files == []


# ---------------------------------------------------------------------------
# collect() — combined
# ---------------------------------------------------------------------------


def test_collect_dispatch_and_skill_together(tmp_path: Path):
    (tmp_path / ".cursorrules").write_text("# Global", encoding="utf-8")
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "one.mdc").write_text("# One", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 2
    assert any(f.role == Role.DISPATCH for f in files)
    assert any(f.role == Role.SKILL for f in files)


def test_collect_empty_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.collect(tmp_path) == []
