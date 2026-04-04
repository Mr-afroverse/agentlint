"""
Integration tests for the agentlint CLI.

Uses click.testing.CliRunner — no subprocess spawning, no filesystem side effects
beyond tmp_path. Covers:

  - Exit codes: 0 (pass), 1 (errors), 1 (fail-on-warnings), 2 (no adapter)
  - BUG-01 fix: --adapter cursor on Copilot repo → exit 2 (detect() required)
  - BUG-06 fix: --config with custom filename loads correctly
  - --init: creates / does not overwrite SKILL_HEALTH_CHECK.md
  - Aider adapter: auto-detect, explicit, rules dir, no-files exit 2
  - Continue adapter: auto-detect, explicit, rules dir, no-files exit 2
  - severity_overrides config: re-classifies violation severity before reporting
  - --format badge: writes agentlint-badge.svg, correct grade colour
  - --format json: valid JSON with correct structure
  - --fail-on-warnings: flag escalates warnings to exit 1
  - --adapter copilot: explicit adapter on matching repo
  - --version: reports 0.1.0
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agentlint.cli import main

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Repo builders
# ---------------------------------------------------------------------------


def _make_clean_copilot_repo(root: Path) -> None:
    """Minimal Copilot repo — all checks pass."""
    skill_dir = root / ".github" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\nWrite tests first.\n", encoding="utf-8"
    )
    dispatch = "| `my-skill` | `.github/skills/my-skill/SKILL.md` | any feature |\n"
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )


def _make_error_copilot_repo(root: Path) -> None:
    """Repo with an AL-D01 error: dispatch references a skill file that does not exist."""
    skill_dir = root / ".github" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    dispatch = (
        "| `my-skill` | `.github/skills/my-skill/SKILL.md` | any feature |\n"
        "| `ghost` | `.github/skills/ghost/SKILL.md` | ghost skill |\n"
    )
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )


def _make_warning_copilot_repo(root: Path) -> None:
    """Repo with an AL-N01 warning: unsourced percentage threshold."""
    skill_dir = root / ".github" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "The score must be ≥ 90% to pass.\n", encoding="utf-8"
    )
    dispatch = "| `my-skill` | `.github/skills/my-skill/SKILL.md` | scoring |\n"
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


def test_cli_exit_0_on_clean_repo(tmp_path: Path):
    """Clean repo → exit 0 and PASS in output."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_exit_1_on_error(tmp_path: Path):
    """Errors (AL-D01) → exit 1 and check ID visible in output."""
    _make_error_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 1
    assert "AL-D01" in result.output


def test_cli_exit_2_no_adapter_detected(tmp_path: Path):
    """Empty directory → no adapter detected → exit 2."""
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 2


def test_cli_exit_2_explicit_cursor_adapter_on_copilot_repo(tmp_path: Path):
    """--adapter cursor on a Copilot-only repo → detect() fails → exit 2 (BUG-01 fix)."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "cursor", str(tmp_path)])
    assert result.exit_code == 2


def test_cli_exit_0_warnings_without_fail_flag(tmp_path: Path):
    """Warnings alone do not cause exit 1 unless --fail-on-warnings is passed."""
    _make_warning_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "warning" in result.output.lower()


def test_cli_exit_1_fail_on_warnings_flag(tmp_path: Path):
    """--fail-on-warnings escalates warnings to exit 1."""
    _make_warning_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--fail-on-warnings", str(tmp_path)])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# --init
# ---------------------------------------------------------------------------


def test_cli_init_creates_health_check(tmp_path: Path):
    """--init creates SKILL_HEALTH_CHECK.md inside .github/skills/."""
    result = _RUNNER.invoke(main, ["--init", str(tmp_path)])
    assert result.exit_code == 0
    dest = tmp_path / ".github" / "skills" / "SKILL_HEALTH_CHECK.md"
    assert dest.exists(), "SKILL_HEALTH_CHECK.md should have been created"
    assert dest.stat().st_size > 0, "Created file should not be empty"


def test_cli_init_does_not_overwrite(tmp_path: Path):
    """Running --init twice leaves the original file intact."""
    _RUNNER.invoke(main, ["--init", str(tmp_path)])
    dest = tmp_path / ".github" / "skills" / "SKILL_HEALTH_CHECK.md"
    original = dest.read_text(encoding="utf-8")

    result = _RUNNER.invoke(main, ["--init", str(tmp_path)])
    assert "not overwriting" in result.output
    assert dest.read_text(encoding="utf-8") == original, "File should not be modified"


# ---------------------------------------------------------------------------
# --format json
# ---------------------------------------------------------------------------


def test_cli_format_json_valid_and_complete(tmp_path: Path):
    """--format json produces valid JSON with all required top-level keys."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "json", str(tmp_path)])
    assert result.exit_code == 0

    data = json.loads(result.output)  # raises json.JSONDecodeError if invalid
    for key in (
        "grade",
        "adapter",
        "files_scanned",
        "scanned_files",
        "errors",
        "warnings",
        "violations",
    ):
        assert key in data, f"JSON output missing key: {key!r}"

    assert data["grade"] == "A"
    assert data["errors"] == 0
    assert data["violations"] == []
    assert isinstance(data["scanned_files"], list)
    assert len(data["scanned_files"]) == data["files_scanned"]


def test_cli_format_json_contains_violation_details(tmp_path: Path):
    """JSON output with violations includes per-violation fields."""
    _make_error_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "json", str(tmp_path)])

    data = json.loads(result.output)
    assert data["errors"] >= 1
    assert len(data["violations"]) >= 1

    v = data["violations"][0]
    for field in (
        "check_id",
        "severity",
        "file",
        "line",
        "message",
        "fix_hint",
        "auto_fixable",
    ):
        assert field in v, f"Violation JSON missing field: {field!r}"


# ---------------------------------------------------------------------------
# --config explicit path (BUG-06 fix)
# ---------------------------------------------------------------------------


def test_cli_config_explicit_custom_filename_loaded(tmp_path: Path):
    """--config /path/to/custom-name.yml loads the file even with a non-standard name."""
    _make_warning_copilot_repo(tmp_path)

    # A config that sets fail_on_warnings — stored under a custom filename
    config_file = tmp_path / "custom-lint.yml"
    config_file.write_text("fail_on_warnings: true\n", encoding="utf-8")

    # Without --config: warnings do not cause exit 1
    result_no_cfg = _RUNNER.invoke(main, [str(tmp_path)])
    assert result_no_cfg.exit_code == 0

    # With --config pointing directly to the custom file: fail_on_warnings applied → exit 1
    result_with_cfg = _RUNNER.invoke(
        main, ["--config", str(config_file), str(tmp_path)]
    )
    assert result_with_cfg.exit_code == 1


# ---------------------------------------------------------------------------
# --adapter explicit (passing case)
# ---------------------------------------------------------------------------


def test_cli_adapter_copilot_explicit_on_copilot_repo(tmp_path: Path):
    """--adapter copilot on a Copilot repo detects correctly and passes."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "copilot", str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


def test_cli_version_shows_0_1_0():
    from agentlint import __version__

    result = _RUNNER.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


# ---------------------------------------------------------------------------
# Windsurf adapter
# ---------------------------------------------------------------------------


def _make_clean_windsurf_repo(root: Path) -> None:
    """Minimal Windsurf repo with a monolithic .windsurfrules file."""
    (root / ".windsurfrules").write_text(
        "# Windsurf global rules\nAlways write tests first.\n",
        encoding="utf-8",
    )


def _make_windsurf_with_rules_dir(root: Path) -> None:
    """Windsurf repo with .windsurf/rules/*.md skill files."""
    rules_dir = root / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "my-rule.md").write_text(
        "---\ntrigger: Write tests first\n---\n# My Rule\nContent here.\n",
        encoding="utf-8",
    )


def test_cli_windsurf_auto_detect(tmp_path: Path):
    """Auto mode picks up .windsurfrules without --adapter flag."""
    _make_clean_windsurf_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_windsurf_explicit_adapter(tmp_path: Path):
    """--adapter windsurf works on a Windsurf repo."""
    _make_clean_windsurf_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "windsurf", str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_windsurf_rules_dir_collected(tmp_path: Path):
    """Files under .windsurf/rules/ are collected and scanned."""
    _make_windsurf_with_rules_dir(tmp_path)
    result = _RUNNER.invoke(
        main, ["--adapter", "windsurf", "--format", "json", str(tmp_path)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["files_scanned"] >= 1
    assert data["adapter"] == "windsurf"


def test_cli_windsurf_no_files_exit2(tmp_path: Path):
    """--adapter windsurf on a repo without Windsurf files exits 2."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "windsurf", str(tmp_path)])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# --format sarif
# ---------------------------------------------------------------------------


def test_cli_format_sarif_is_valid_json(tmp_path: Path):
    """--format sarif produces valid JSON."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "sarif", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["version"] == "2.1.0"
    assert "runs" in data
    assert len(data["runs"]) == 1


def test_cli_format_sarif_top_level_keys(tmp_path: Path):
    """SARIF output has expected top-level keys."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "sarif", str(tmp_path)])
    data = json.loads(result.output)
    run = data["runs"][0]
    assert "tool" in run
    assert "results" in run
    assert run["tool"]["driver"]["name"] == "agentlint"


def test_cli_format_sarif_violation_fields(tmp_path: Path):
    """SARIF results contain expected keys for each violation."""
    _make_error_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "sarif", str(tmp_path)])
    data = json.loads(result.output)
    results = data["runs"][0]["results"]
    assert len(results) >= 1
    v = results[0]
    assert "ruleId" in v
    assert "level" in v
    assert "message" in v
    assert "locations" in v


def test_cli_format_sarif_clean_run_empty_results(tmp_path: Path):
    """A clean repo produces SARIF with an empty results array."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "sarif", str(tmp_path)])
    data = json.loads(result.output)
    assert data["runs"][0]["results"] == []


# ---------------------------------------------------------------------------
# --watch
# ---------------------------------------------------------------------------


def test_watch_flag_in_help():
    """--watch appears in the help text."""
    result = _RUNNER.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--watch" in result.output


def test_watch_no_watchdog_prints_install_hint(tmp_path: Path, monkeypatch):
    """--watch without watchdog installed exits 1 with an install hint."""
    _make_clean_copilot_repo(tmp_path)

    import builtins

    real_import = builtins.__import__

    def _patched(name, *args, **kwargs):
        if "watchdog" in name:
            raise ImportError(f"Mocked: no module '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _patched)
    result = _RUNNER.invoke(main, ["--watch", str(tmp_path)])
    assert result.exit_code == 1
    assert "watchdog" in result.output


def test_watch_exits_0_when_observer_stops(tmp_path: Path, monkeypatch):
    """--watch exits 0 and prints watching/stopped messages (observer exits immediately)."""
    _make_clean_copilot_repo(tmp_path)

    from unittest.mock import MagicMock
    import watchdog.observers as _wo

    mock_obs = MagicMock()
    mock_obs.is_alive.return_value = False  # while-loop exits before first sleep
    monkeypatch.setattr(_wo, "Observer", lambda: mock_obs)

    result = _RUNNER.invoke(main, ["--watch", str(tmp_path)])
    assert result.exit_code == 0
    assert "Watching" in result.output
    assert "Watch stopped" in result.output


# ---------------------------------------------------------------------------
# Aider adapter
# ---------------------------------------------------------------------------


def _make_clean_aider_repo(root: Path) -> None:
    """Minimal Aider repo with a .aider.conf.yml config file."""
    (root / ".aider.conf.yml").write_text(
        "# Aider configuration\nmodel: gpt-4o\n",
        encoding="utf-8",
    )


def _make_aider_with_rules_dir(root: Path) -> None:
    """Aider repo with .aider/rules/*.md convention files."""
    rules_dir = root / ".aider" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "conventions.md").write_text(
        "# Coding conventions\nAlways write tests first.\n",
        encoding="utf-8",
    )


def test_cli_aider_auto_detect(tmp_path: Path):
    """Auto mode picks up .aider.conf.yml without --adapter flag."""
    _make_clean_aider_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_aider_explicit_adapter(tmp_path: Path):
    """--adapter aider works on an Aider repo."""
    _make_clean_aider_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "aider", str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_aider_rules_dir_collected(tmp_path: Path):
    """Files under .aider/rules/ are collected and scanned."""
    _make_aider_with_rules_dir(tmp_path)
    result = _RUNNER.invoke(
        main, ["--adapter", "aider", "--format", "json", str(tmp_path)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["files_scanned"] >= 1
    assert data["adapter"] == "aider"


def test_cli_aider_no_files_exit2(tmp_path: Path):
    """--adapter aider on a repo without Aider files exits 2."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "aider", str(tmp_path)])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Continue.dev adapter
# ---------------------------------------------------------------------------


def _make_clean_continue_repo(root: Path) -> None:
    """Minimal Continue.dev repo with a monolithic .continuerules file."""
    (root / ".continuerules").write_text(
        "# Continue global rules\nAlways write tests first.\n",
        encoding="utf-8",
    )


def _make_continue_with_rules_dir(root: Path) -> None:
    """Continue.dev repo with .continue/rules/*.md rule files."""
    rules_dir = root / ".continue" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "my-rule.md").write_text(
        "---\ntrigger: Write tests first\n---\n# My Rule\nContent here.\n",
        encoding="utf-8",
    )


def test_cli_continue_auto_detect(tmp_path: Path):
    """Auto mode picks up .continuerules without --adapter flag."""
    _make_clean_continue_repo(tmp_path)
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_continue_explicit_adapter(tmp_path: Path):
    """--adapter continue works on a Continue.dev repo."""
    _make_clean_continue_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "continue", str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_cli_continue_rules_dir_collected(tmp_path: Path):
    """Files under .continue/rules/ are collected and scanned."""
    _make_continue_with_rules_dir(tmp_path)
    result = _RUNNER.invoke(
        main, ["--adapter", "continue", "--format", "json", str(tmp_path)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["files_scanned"] >= 1
    assert data["adapter"] == "continue"


def test_cli_continue_no_files_exit2(tmp_path: Path):
    """--adapter continue on a repo without Continue files exits 2."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--adapter", "continue", str(tmp_path)])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# severity_overrides config key
# ---------------------------------------------------------------------------


def test_severity_override_warning_to_error(tmp_path: Path):
    """severity_overrides can promote a warning check to error, causing exit 1."""
    _make_warning_copilot_repo(tmp_path)

    # Without override: AL-N01 is a warning → exit 0
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0

    # With severity_overrides: {AL-N01: error} → AL-N01 becomes error → exit 1
    cfg = tmp_path / ".agentlint.yml"
    cfg.write_text("severity_overrides:\n  AL-N01: error\n", encoding="utf-8")
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 1


def test_severity_override_error_to_warning(tmp_path: Path):
    """severity_overrides can demote an error check to warning, allowing exit 0."""
    _make_error_copilot_repo(tmp_path)

    # Without override: AL-D01 is an error → exit 1
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 1

    # With severity_overrides: {AL-D01: warning} → exit 0
    cfg = tmp_path / ".agentlint.yml"
    cfg.write_text("severity_overrides:\n  AL-D01: warning\n", encoding="utf-8")
    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --format badge
# ---------------------------------------------------------------------------


def test_cli_format_badge_writes_svg(tmp_path: Path):
    """--format badge writes agentlint-badge.svg to the scanned directory."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "badge", str(tmp_path)])
    assert result.exit_code == 0
    badge = tmp_path / "agentlint-badge.svg"
    assert badge.exists(), "agentlint-badge.svg should be created"
    content = badge.read_text(encoding="utf-8")
    assert content.startswith("<svg"), "Badge file should be an SVG"
    assert "Grade: A" in content


def test_cli_format_badge_grade_in_output(tmp_path: Path):
    """--format badge echoes the grade to stdout."""
    _make_clean_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "badge", str(tmp_path)])
    assert "Grade: A" in result.output


def test_cli_format_badge_error_repo(tmp_path: Path):
    """--format badge still writes the badge even when errors cause exit 1."""
    _make_error_copilot_repo(tmp_path)
    result = _RUNNER.invoke(main, ["--format", "badge", str(tmp_path)])
    # exit 1 because of errors
    assert result.exit_code == 1
    badge = tmp_path / "agentlint-badge.svg"
    assert badge.exists(), "Badge should be written even on a failing run"
    content = badge.read_text(encoding="utf-8")
    assert content.startswith("<svg"), "Badge file should be valid SVG"
    assert "agentlint" in content
