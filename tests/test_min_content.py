from __future__ import annotations

from pathlib import Path

from agentlint.checks.min_content import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role


def _skill(tmp_path: Path, content: str) -> InstructionFile:
    p = tmp_path / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )


def _dispatch(tmp_path: Path, content: str) -> InstructionFile:
    p = tmp_path / "copilot-instructions.md"
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="copilot",
        role=Role.DISPATCH,
        metadata={},
    )


# ---------------------------------------------------------------------------
# disabled by default (min_content_tokens = 0 or 10 but content is fine)
# ---------------------------------------------------------------------------


def test_disabled_when_zero(tmp_path: Path):
    config = Config()
    config.min_content_tokens = 0
    f = _skill(tmp_path, "# Title\nsome content here please ignore")
    assert run([f], config, tmp_path) == []


def test_passes_with_sufficient_content(tmp_path: Path):
    config = Config()  # default min_content_tokens = 10
    f = _skill(tmp_path, "# Rule\n" + "A" * 80)
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# fires on stub files
# ---------------------------------------------------------------------------


def test_fires_on_empty_file(tmp_path: Path):
    config = Config()
    f = _skill(tmp_path, "")
    violations = run([f], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-LEN01"


def test_fires_on_near_empty_file(tmp_path: Path):
    config = Config()
    # 10 chars ≈ 2 tokens — well below default threshold of 10
    f = _skill(tmp_path, "# Hi\n")
    violations = run([f], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-LEN01"


def test_message_includes_token_counts(tmp_path: Path):
    config = Config()
    f = _skill(tmp_path, "Hi")
    violations = run([f], config, tmp_path)
    assert "10" in violations[0].message  # threshold mentioned


# ---------------------------------------------------------------------------
# only SKILL files are checked
# ---------------------------------------------------------------------------


def test_dispatch_file_not_checked(tmp_path: Path):
    config = Config()
    f = _dispatch(tmp_path, "")  # empty dispatch — should not fire
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# configurable threshold
# ---------------------------------------------------------------------------


def test_custom_threshold(tmp_path: Path):
    config = Config()
    config.min_content_tokens = 100  # very high threshold
    f = _skill(tmp_path, "# Rule\n" + "A" * 80)  # ≈ 21 tokens — below 100
    violations = run([f], config, tmp_path)
    assert len(violations) == 1


def test_ignore_paths_respected(tmp_path: Path):
    config = Config()
    config.ignore_paths = ["SKILL.md"]
    f = _skill(tmp_path, "")
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# Regression: int(None) crash in config._from_file (bug fixed 2026-04-11)
# A blank `min_content_tokens:` in YAML is parsed as None.  Before the fix,
# int(None) raised TypeError.  After the fix it falls back to default (10).
# ---------------------------------------------------------------------------


def test_config_min_content_tokens_blank_yaml(tmp_path: Path):
    """min_content_tokens: with no value in YAML must not crash; uses default."""
    from agentlint.config import Config

    cfg_file = tmp_path / ".agentlint.yml"
    cfg_file.write_text("min_content_tokens:\n", encoding="utf-8")
    cfg = Config._from_file(cfg_file)
    # Must not raise; must fall back to the dataclass default (10)
    assert cfg.min_content_tokens == 10


def test_config_min_content_tokens_string_yaml(tmp_path: Path):
    """min_content_tokens: 'abc' in YAML must not crash; uses default."""
    from agentlint.config import Config

    cfg_file = tmp_path / ".agentlint.yml"
    cfg_file.write_text("min_content_tokens: 'not_a_number'\n", encoding="utf-8")
    cfg = Config._from_file(cfg_file)
    assert cfg.min_content_tokens == 10
