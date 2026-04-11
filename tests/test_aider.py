from __future__ import annotations

from pathlib import Path

from agentlint.adapters.aider import AiderAdapter
from agentlint.models import Role

_ADAPTER = AiderAdapter()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_via_conf_yml(tmp_path: Path):
    (tmp_path / ".aider.conf.yml").write_text("model: gpt-4o\n", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_via_rules_dir(tmp_path: Path):
    (tmp_path / ".aider" / "rules").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_false_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# collect() — .aider.conf.yml (DISPATCH)
# ---------------------------------------------------------------------------


def test_collect_dispatch_from_conf_yml(tmp_path: Path):
    (tmp_path / ".aider.conf.yml").write_text("model: gpt-4o\n", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.DISPATCH
    assert files[0].adapter == "aider"
    assert files[0].path.name == ".aider.conf.yml"


def test_collect_dispatch_content_read_correctly(tmp_path: Path):
    content = "model: gpt-4o\nauto-commits: false\n"
    (tmp_path / ".aider.conf.yml").write_text(content, encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert files[0].content == content


# ---------------------------------------------------------------------------
# collect() — .aider/rules/*.md (SKILL)
# ---------------------------------------------------------------------------


def test_collect_skill_from_rules_dir(tmp_path: Path):
    rules_dir = tmp_path / ".aider" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "conventions.md").write_text("# Conventions", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.SKILL
    assert files[0].adapter == "aider"
    assert files[0].path.name == "conventions.md"


def test_collect_multiple_rule_files(tmp_path: Path):
    rules_dir = tmp_path / ".aider" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "alpha.md").write_text("# Alpha", encoding="utf-8")
    (rules_dir / "beta.md").write_text("# Beta", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    names = {f.path.name for f in files}
    assert names == {"alpha.md", "beta.md"}
    assert all(f.role == Role.SKILL for f in files)


def test_collect_frontmatter_parsed(tmp_path: Path):
    rules_dir = tmp_path / ".aider" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "style.md").write_text(
        "---\nname: aider-style\n---\n# Style", encoding="utf-8"
    )
    files = _ADAPTER.collect(tmp_path)
    assert files[0].metadata.get("name") == "aider-style"


# ---------------------------------------------------------------------------
# collect() — combined
# ---------------------------------------------------------------------------


def test_collect_dispatch_and_skill_together(tmp_path: Path):
    (tmp_path / ".aider.conf.yml").write_text("model: gpt-4o\n", encoding="utf-8")
    rules_dir = tmp_path / ".aider" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "one.md").write_text("# One", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 2
    assert any(f.role == Role.DISPATCH for f in files)
    assert any(f.role == Role.SKILL for f in files)


def test_collect_empty_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.collect(tmp_path) == []
