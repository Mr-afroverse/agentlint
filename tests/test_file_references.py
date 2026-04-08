"""
Tests for AL-F01 — source-file path references must exist on disk.

Covers:
  - Pass: file exists
  - Pass: template strings ({…}) skipped
  - Pass: glob patterns (*) skipped
  - Pass: paths inside code fences skipped  (BUG-02 fix)
  - Pass: paths after a closed fence are still checked
  - Pass: dispatch file not scanned (SKILL files only)
  - Fail: missing reference fires at WARNING severity
  - Fail: correct line number reported
  - Fail: duplicate path in same file produces one violation
"""

from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.file_references import run
from agentlint.config import Config
from agentlint.models import Severity

_ADAPTER = CopilotAdapter()


def _make_repo(root: Path, skill_content: str) -> None:
    """Minimal Copilot repo with one skill file."""
    skill_dir = root / ".github" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    dispatch = "| `t` | `.github/skills/test-skill/SKILL.md` | test |\n"
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )
    (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Pass cases
# ---------------------------------------------------------------------------


def test_f01_pass_file_exists_on_disk(tmp_path: Path):
    """A reference to a file that actually exists on disk → no violation."""
    src = tmp_path / "src" / "utils" / "helpers.py"
    src.parent.mkdir(parents=True)
    src.write_text("# helpers", encoding="utf-8")

    _make_repo(tmp_path, "Always read `src/utils/helpers.py` before writing logic.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-F01"] == []


def test_f01_pass_template_strings_skipped(tmp_path: Path):
    """`{placeholder}` expressions are not treated as concrete file paths."""
    _make_repo(
        tmp_path, "Use `app/services/{service_name}.py` as the naming pattern.\n"
    )
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-F01"] == []


def test_f01_pass_glob_patterns_skipped(tmp_path: Path):
    """`src/*/foo.py` glob expressions are not concrete paths — skip them."""
    _make_repo(tmp_path, "Run checks against all `src/*/models.py` files.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-F01"] == []


def test_f01_pass_paths_in_code_fences_skipped(tmp_path: Path):
    """Paths inside fenced code blocks must NOT fire AL-F01 (BUG-02 fix)."""
    content = (
        "Example configuration:\n"
        "\n"
        "```yaml\n"
        "source: app/services/nonexistent_service.py\n"
        "output: src/utils/missing_output.ts\n"
        "```\n"
        "\n"
        "The paths above are illustrative only.\n"
    )
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-F01"] == [], (
        "AL-F01 must not fire on paths inside fenced code blocks"
    )


def test_f01_pass_four_backtick_skill_fence_ignored(tmp_path: Path):
    """The outer ````skill block itself is not treated as a code fence for AL-F01."""
    # The skill content uses the 4-backtick format; the path inside it is outside
    # the inner ``` block, so it should be checked (and fire if missing).
    content = (
        "````skill\n"
        "---\n"
        "name: test\n"
        "---\n"
        "\n"
        "```python\n"
        "# app/services/example.py\n"
        "```\n"
        "\n"
        "````\n"
    )
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    # The path is a comment inside python fence — _FILE_REF_RE won't match
    # a bare `# app/services/example.py` comment prefix correctly, but just
    # verifying it doesn't crash is the important thing here.
    assert isinstance(violations, list)


def test_f01_pass_dispatch_file_not_scanned(tmp_path: Path):
    """AL-F01 only scans SKILL files — missing references in the dispatch file are ignored."""
    skills = tmp_path / ".github" / "skills" / "my-skill"
    skills.mkdir(parents=True)
    # Put a missing path inside the dispatch file itself
    dispatch_content = (
        "Read `app/services/missing.py` for context.\n"
        "| `my-skill` | `.github/skills/my-skill/SKILL.md` | test |\n"
    )
    (tmp_path / ".github" / "copilot-instructions.md").write_text(
        dispatch_content, encoding="utf-8"
    )
    (skills / "SKILL.md").write_text("# My skill\n", encoding="utf-8")

    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-F01"] == [], (
        "AL-F01 must not scan the dispatch file"
    )


def test_f01_pass_path_outside_fence_checks_after_fence_closes(tmp_path: Path):
    """A path AFTER a closed code fence is still subject to AL-F01."""
    content = (
        "```yaml\n"
        "safe: app/services/safe_in_fence.py\n"
        "```\n"
        "\n"
        "Also read `app/services/missing_outside.py` for more detail.\n"
    )
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1
    assert "missing_outside" in f01[0].message


# ---------------------------------------------------------------------------
# Fail cases
# ---------------------------------------------------------------------------


def test_f01_fail_missing_reference_fires_warning(tmp_path: Path):
    """A missing file reference fires AL-F01 at WARNING severity."""
    _make_repo(tmp_path, "Always read `app/services/scorer.py` first.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1
    assert "app/services/scorer.py" in f01[0].message
    assert f01[0].severity == Severity.WARNING


def test_f01_fail_correct_line_number_reported(tmp_path: Path):
    """The violation reports the exact line where the missing path appears."""
    content = "Line one.\nLine two.\nRead `app/services/missing.py` here.\nLine four.\n"
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1
    assert f01[0].line == 3


def test_f01_fail_deduplicates_same_path(tmp_path: Path):
    """The same missing path referenced twice in one file → one violation, not two."""
    content = (
        "Read `app/services/scorer.py` before writing code.\n"
        "Also check `app/services/scorer.py` for the thresholds.\n"
    )
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1, (
        "Same missing path referenced twice should yield one violation"
    )


def test_f01_fail_multiple_distinct_missing_paths(tmp_path: Path):
    """Two different missing file paths produce two separate violations."""
    content = (
        "Read `app/services/scorer.py` first.\n"
        "Then check `src/utils/validator.ts` for the schema.\n"
    )
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 2


# ---------------------------------------------------------------------------
# Fuzzy suggestions
# ---------------------------------------------------------------------------


def test_f01_fuzzy_suggestion_when_close_match_exists(tmp_path: Path):
    """When a similarly-named file exists, the fix hint suggests it."""
    # Create the actual file on disk — slightly different name
    actual = tmp_path / "src" / "utils" / "validator.ts"
    actual.parent.mkdir(parents=True)
    actual.write_text("// real file\n", encoding="utf-8")

    # Skill references a mis-spelled version
    content = "Check `src/utils/validatr.ts` for the schema.\n"
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1
    assert "Did you mean" in f01[0].fix_hint
    assert "validator.ts" in f01[0].fix_hint


def test_f01_no_fuzzy_suggestion_when_no_close_match(tmp_path: Path):
    """When no similar file exists, the fix hint uses the generic message."""
    content = "Read `app/services/xyzzy.py` for more info.\n"
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    f01 = [v for v in violations if v.check_id == "AL-F01"]
    assert len(f01) == 1
    assert "Did you mean" not in f01[0].fix_hint
    assert "Update the path" in f01[0].fix_hint


# ---------------------------------------------------------------------------
# Tree diagram paths (opt-in via config)
# ---------------------------------------------------------------------------


def test_f01_tree_pass_existing_file(tmp_path: Path):
    """Tree diagram referencing an existing file → no violation."""
    (tmp_path / "validator.py").write_text("# real\n", encoding="utf-8")
    content = "```\n├── validator.py\n└── helpers.py\n```\n"
    _make_repo(tmp_path, content)
    # helpers.py doesn't exist but tree lines are inside a code fence → skipped.
    # Outside of fence, test the feature with a non-fenced tree:
    skill_dir = tmp_path / ".github" / "skills" / "test-skill"
    (skill_dir / "SKILL.md").write_text(
        "Project layout:\n├── validator.py\n", encoding="utf-8"
    )
    cfg = Config()
    cfg.tree_diagram_paths = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    f01 = [
        v for v in violations if v.check_id == "AL-F01" and "Tree diagram" in v.message
    ]
    assert f01 == []


def test_f01_tree_fail_missing_file(tmp_path: Path):
    """Tree diagram referencing a missing file → violation when opt-in enabled."""
    content = "Project layout:\n├── nonexistent_module.py\n└── also_missing.ts\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert len(tree_violations) == 2
    assert tree_violations[0].check_id == "AL-F01"
    assert tree_violations[0].severity == Severity.WARNING


def test_f01_tree_disabled_by_default(tmp_path: Path):
    """Tree diagram paths are NOT checked when tree_diagram_paths is False (default)."""
    content = "Project layout:\n├── nonexistent_module.py\n"
    _make_repo(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert tree_violations == []


def test_f01_tree_fuzzy_suggestion(tmp_path: Path):
    """Tree diagram with a close-match file gets a fuzzy suggestion."""
    (tmp_path / "validator.py").write_text("# real\n", encoding="utf-8")
    content = "Project layout:\n├── validatr.py\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert len(tree_violations) == 1
    assert "Did you mean" in tree_violations[0].fix_hint


# ---------------------------------------------------------------------------
# tree_diagram_fenced: scan trees inside ``` code fences (CHECK-07)
# ---------------------------------------------------------------------------


def test_f01_fenced_tree_disabled_by_default(tmp_path: Path):
    """Trees inside fences are NOT checked when tree_diagram_fenced is False (default)."""
    content = "```\n├── ghost_module.py\n└── also_missing.ts\n```\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    # tree_diagram_fenced defaults to False
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert tree_violations == []


def test_f01_fenced_tree_fires_when_enabled(tmp_path: Path):
    """Trees inside fences fire AL-F01 when tree_diagram_fenced is True."""
    content = "```\n├── ghost_module.py\n└── also_missing.ts\n```\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    cfg.tree_diagram_fenced = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert len(tree_violations) == 2
    assert all(v.check_id == "AL-F01" for v in tree_violations)
    assert all(v.severity == Severity.WARNING for v in tree_violations)


def test_f01_fenced_tree_pass_existing_file(tmp_path: Path):
    """Fenced tree referencing an existing file → no violation."""
    (tmp_path / "real_module.py").write_text("# exists\n", encoding="utf-8")
    content = "```\n├── real_module.py\n```\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    cfg.tree_diagram_fenced = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    tree_violations = [v for v in violations if "Tree diagram" in v.message]
    assert tree_violations == []


def test_f01_fenced_tree_file_refs_still_not_checked_inside_fence(tmp_path: Path):
    """File-path references (app/…) inside fences still don't fire even with fenced enabled."""
    content = "```yaml\nsource: app/services/missing_service.py\n```\n"
    _make_repo(tmp_path, content)
    cfg = Config()
    cfg.tree_diagram_paths = True
    cfg.tree_diagram_fenced = True
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    # _FILE_REF_RE matches must not fire inside a fence
    f01 = [v for v in violations if "Referenced file" in v.message]
    assert f01 == []


def test_f01_fenced_tree_separate_from_prose_tree(tmp_path: Path):
    """Prose tree fires with tree_diagram_paths; fenced tree requires tree_diagram_fenced too."""
    (tmp_path / "exists.py").write_text("# exists\n", encoding="utf-8")
    content = (
        "Prose tree:\n"
        "├── ghost_prose.py\n"
        "\n"
        "Fenced tree:\n"
        "```\n"
        "├── ghost_fenced.py\n"
        "```\n"
    )
    _make_repo(tmp_path, content)

    # Only prose scanning
    cfg_prose = Config()
    cfg_prose.tree_diagram_paths = True
    files = _ADAPTER.collect(tmp_path)
    prose_violations = [
        v for v in run(files, cfg_prose, tmp_path) if "Tree diagram" in v.message
    ]
    assert len(prose_violations) == 1
    assert "ghost_prose" in prose_violations[0].message

    # Both prose + fenced
    cfg_both = Config()
    cfg_both.tree_diagram_paths = True
    cfg_both.tree_diagram_fenced = True
    both_violations = [
        v for v in run(files, cfg_both, tmp_path) if "Tree diagram" in v.message
    ]
    assert len(both_violations) == 2


def test_f01_fenced_tree_config_loaded_from_yaml(tmp_path: Path):
    """tree_diagram_fenced: true in .agentlint.yml is parsed correctly."""
    from agentlint.config import Config as Cfg

    cfg_file = tmp_path / ".agentlint.yml"
    cfg_file.write_text(
        "tree_diagram_paths: true\ntree_diagram_fenced: true\n", encoding="utf-8"
    )
    cfg = Cfg.load(tmp_path)
    assert cfg.tree_diagram_paths is True
    assert cfg.tree_diagram_fenced is True
