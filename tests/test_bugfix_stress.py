"""
Stress tests for the P1/P5/P6/P7/P8 bug-fix batch.

Run with:  python -m pytest tests/test_bugfix_stress.py -v
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from agentlint.checks import circular_refs, config_parity, freshness, semantic_conflict
from agentlint.config import Config
from agentlint.models import InstructionFile, Role


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_file(
    path: Path,
    content: str,
    role: Role = Role.SKILL,
    adapter: str = "copilot",
) -> InstructionFile:
    path.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=path,
        content=content,
        lines=content.splitlines(keepends=False),
        adapter=adapter,
        role=role,
    )


def _make_ifile(
    path: Path,
    content: str,
    role: Role = Role.SKILL,
    adapter: str = "copilot",
    write: bool = False,
) -> InstructionFile:
    """Build an InstructionFile without needing the file to exist on disk."""
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=path,
        content=content,
        lines=content.splitlines(keepends=False),
        adapter=adapter,
        role=role,
    )


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 3 – B-01: Quoted numeric config values  (token_budget, stale_days,
#                number_source_lookback, trigger_overlap_threshold,
#                duplicate_threshold, min_content_tokens)
# ---------------------------------------------------------------------------


class TestQuotedNumericConfig:
    def test_token_budget_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "token_budget: '2000'\n")
        cfg = Config.load(tmp_path)
        assert cfg.token_budget == 2000, f"Expected 2000, got {cfg.token_budget!r}"

    def test_stale_days_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "stale_days: '30'\n")
        cfg = Config.load(tmp_path)
        assert cfg.stale_days == 30, f"Expected 30, got {cfg.stale_days!r}"

    def test_number_source_lookback_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "number_source_lookback: '20'\n")
        cfg = Config.load(tmp_path)
        assert cfg.number_source_lookback == 20

    def test_trigger_overlap_threshold_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "trigger_overlap_threshold: '0.7'\n")
        cfg = Config.load(tmp_path)
        assert abs(cfg.trigger_overlap_threshold - 0.7) < 1e-9

    def test_duplicate_threshold_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "duplicate_threshold: '0.9'\n")
        cfg = Config.load(tmp_path)
        assert abs(cfg.duplicate_threshold - 0.9) < 1e-9

    def test_min_content_tokens_as_string(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "min_content_tokens: '5'\n")
        cfg = Config.load(tmp_path)
        assert cfg.min_content_tokens == 5

    def test_all_quoted_at_once_no_crash(self, tmp_path):
        """All numeric fields as quoted strings simultaneously — must not raise."""
        _write_yaml(
            tmp_path / ".agentlint.yml",
            textwrap.dedent("""\
                token_budget: "2000"
                stale_days: "30"
                number_source_lookback: "20"
                trigger_overlap_threshold: "0.7"
                duplicate_threshold: "0.85"
                min_content_tokens: "5"
            """),
        )
        cfg = Config.load(tmp_path)
        assert cfg.token_budget == 2000
        assert cfg.stale_days == 30
        assert cfg.number_source_lookback == 20
        assert abs(cfg.trigger_overlap_threshold - 0.7) < 1e-9
        assert abs(cfg.duplicate_threshold - 0.85) < 1e-9
        assert cfg.min_content_tokens == 5


# ---------------------------------------------------------------------------
# Test 4 – B-03: Malformed checks key (checks: true)
# ---------------------------------------------------------------------------


class TestMalformedChecksKey:
    def test_checks_true_no_crash(self, tmp_path):
        """checks: true must not crash — treated as no-op."""
        _write_yaml(tmp_path / ".agentlint.yml", "checks: true\n")
        cfg = Config.load(tmp_path)
        # All defaults should remain intact
        assert cfg.checks["dispatch-coverage"] is True

    def test_checks_int_no_crash(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "checks: 42\n")
        cfg = Config.load(tmp_path)
        assert cfg.checks["dispatch-coverage"] is True

    def test_checks_string_no_crash(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", 'checks: "all"\n')
        cfg = Config.load(tmp_path)
        assert cfg.checks["dispatch-coverage"] is True


# ---------------------------------------------------------------------------
# Test 5 – B-02: source_markers as scalar
# ---------------------------------------------------------------------------


class TestSourceMarkersScalar:
    def test_source_markers_string_no_crash(self, tmp_path):
        """source_markers: 'heuristic' must not crash — treated as no-op."""
        _write_yaml(tmp_path / ".agentlint.yml", "source_markers: heuristic\n")
        cfg = Config.load(tmp_path)
        # Should keep the defaults only
        assert len(cfg.source_markers) > 0

    def test_source_markers_int_no_crash(self, tmp_path):
        _write_yaml(tmp_path / ".agentlint.yml", "source_markers: 99\n")
        cfg = Config.load(tmp_path)
        assert len(cfg.source_markers) > 0


# ---------------------------------------------------------------------------
# Test 6 – B-04: forbidden_patterns with bare string entry
# ---------------------------------------------------------------------------


class TestForbiddenPatternsBareString:
    def test_bare_string_skipped_dict_entry_compiled(self, tmp_path):
        """A bare string in forbidden_patterns is skipped; a valid dict entry still compiles."""
        _write_yaml(
            tmp_path / ".agentlint.yml",
            textwrap.dedent("""\
                forbidden_patterns:
                  - "foo"
                  - id: "AL-P99"
                    pattern: "bar"
                    reason: "test"
            """),
        )
        cfg = Config.load(tmp_path)
        ids = {p["id"] for p in cfg.forbidden_patterns}
        assert "AL-P99" in ids, f"AL-P99 not found in {ids}"

    def test_all_bare_strings_no_crash(self, tmp_path):
        _write_yaml(
            tmp_path / ".agentlint.yml",
            textwrap.dedent("""\
                forbidden_patterns:
                  - "just a string"
                  - "another string"
            """),
        )
        cfg = Config.load(tmp_path)
        # Bare strings are dropped; only DEFAULT_FORBIDDEN remains
        assert all(isinstance(p, dict) for p in cfg.forbidden_patterns)


# ---------------------------------------------------------------------------
# Test 7 – B-17: Path traversal in config_parity
# ---------------------------------------------------------------------------


class TestConfigParityPathTraversal:
    def test_traversal_source_skipped_silently(self, tmp_path):
        cfg = Config()
        # Craft a rule pointing outside the tmp root
        cfg.config_parity = [
            {
                "source": "../../Windows/System32/drivers/etc/hosts",
                "template": "docs/template.env",
            }
        ]
        violations = config_parity.run([], cfg, tmp_path)
        assert violations == [], (
            f"config_parity should skip traversal paths silently; got {violations}"
        )

    def test_traversal_template_skipped_silently(self, tmp_path):
        cfg = Config()
        # Create a real source file within root
        src = tmp_path / ".env"
        src.write_text("DB_HOST=localhost\n")
        cfg.config_parity = [
            {
                "source": ".env",
                "template": "../../Windows/System32/drivers/etc/hosts",
            }
        ]
        violations = config_parity.run([], cfg, tmp_path)
        assert violations == []

    def test_absolute_unix_path_skipped(self, tmp_path):
        cfg = Config()
        cfg.config_parity = [
            {
                "source": "/etc/passwd",
                "template": "docs/template.env",
            }
        ]
        violations = config_parity.run([], cfg, tmp_path)
        assert violations == []


# ---------------------------------------------------------------------------
# Test 8 – B-15: circular_refs on a deep linear chain (no RecursionError)
# ---------------------------------------------------------------------------


class TestCircularRefsDeepChain:
    def test_linear_chain_1500_no_recursion_error(self, tmp_path):
        """1500-node linear chain must complete without RecursionError."""
        N = 1500
        root = tmp_path
        files = []
        paths = [root / f"skill_{i:04d}.md" for i in range(N)]

        for i, p in enumerate(paths):
            if i < N - 1:
                content = f"# Skill {i}\nSee `skill_{i + 1:04d}.md`.\n"
            else:
                content = f"# Skill {i}\nThis is the last skill.\n"
            p.write_text(content, encoding="utf-8")
            files.append(
                InstructionFile(
                    path=p,
                    content=content,
                    lines=content.splitlines(),
                    adapter="copilot",
                    role=Role.SKILL,
                )
            )

        cfg = Config()
        # Should NOT raise RecursionError, should return no violations (chain, no cycle)
        try:
            violations = circular_refs.run(files, cfg, root)
        except RecursionError:
            pytest.fail("circular_refs.run raised RecursionError on a 1500-node chain")
        assert violations == [], (
            f"Expected 0 violations in linear chain, got {violations}"
        )

    def test_cycle_in_large_graph_detected(self, tmp_path):
        """A cycle at the tail of a 100-node chain is still detected."""
        N = 100
        root = tmp_path
        paths = [root / f"cyc_{i:03d}.md" for i in range(N)]
        files = []

        for i, p in enumerate(paths):
            next_i = (i + 1) % N  # last node points back to first → cycle
            content = f"# Skill {i}\nSee `cyc_{next_i:03d}.md`.\n"
            p.write_text(content, encoding="utf-8")
            files.append(
                InstructionFile(
                    path=p,
                    content=content,
                    lines=content.splitlines(),
                    adapter="copilot",
                    role=Role.SKILL,
                )
            )

        cfg = Config()
        try:
            violations = circular_refs.run(files, cfg, root)
        except RecursionError:
            pytest.fail("circular_refs.run raised RecursionError on 100-node cycle")
        assert len(violations) >= 1, "Expected at least one cycle violation"
        assert all(v.check_id == "AL-D03" for v in violations)


# ---------------------------------------------------------------------------
# Test 9 – B-14: semantic_conflict dedup — same predicate, two lines in file A
# ---------------------------------------------------------------------------


class TestSemanticConflictDedup:
    def test_two_positive_lines_same_predicate_one_violation(self, tmp_path):
        """
        File A: 'Always use semicolons.' AND 'Always use semicolons at line end.'
        File B: 'Never use semicolons.'
        → Should produce exactly ONE violation (not two), because both lines in
          file A normalise to the same canonical topic.
        """
        root = tmp_path
        path_a = root / "skill_a.md"
        path_b = root / "skill_b.md"

        content_a = textwrap.dedent("""\
            # Skill A
            Always use semicolons.
            Always use semicolons at line end.
        """)
        content_b = textwrap.dedent("""\
            # Skill B
            Never use semicolons.
        """)

        file_a = _make_ifile(path_a, content_a, Role.SKILL, write=True)
        file_b = _make_ifile(path_b, content_b, Role.SKILL, write=True)

        cfg = Config()
        violations = semantic_conflict.run([file_a, file_b], cfg, root)
        conf01 = [v for v in violations if v.check_id == "AL-CONF01"]

        assert len(conf01) == 1, (
            f"Expected exactly 1 AL-CONF01 violation, got {len(conf01)}: "
            + "\n".join(v.message for v in conf01)
        )

    def test_distinct_predicates_produce_separate_violations(self, tmp_path):
        """Genuinely different predicates produce separate violations — sanity check."""
        root = tmp_path
        path_a = root / "skill_a2.md"
        path_b = root / "skill_b2.md"

        content_a = textwrap.dedent("""\
            # Skill A
            Always use semicolons.
            Always use tabs for indentation.
        """)
        content_b = textwrap.dedent("""\
            # Skill B
            Never use semicolons.
            Never use tabs for indentation.
        """)

        file_a = _make_ifile(path_a, content_a, Role.SKILL, write=True)
        file_b = _make_ifile(path_b, content_b, Role.SKILL, write=True)

        cfg = Config()
        violations = semantic_conflict.run([file_a, file_b], cfg, root)
        conf01 = [v for v in violations if v.check_id == "AL-CONF01"]
        # Expect 2 distinct violations (semicolons + tabs), possibly more due to
        # predicate overlap — but at least 2 distinct subjects
        topics = {v.message.split("'")[1] for v in conf01}
        assert len(topics) >= 2, (
            f"Expected ≥2 distinct topics in violations, got {topics}"
        )


# ---------------------------------------------------------------------------
# Test 10 – B-12: freshness code-fence exclusion (indented fence)
# ---------------------------------------------------------------------------


class TestFreshnessCodeFence:
    def test_date_inside_indented_fence_not_flagged(self, tmp_path):
        """A date inside an indented ``` code fence must not trigger AL-FRESH01."""
        root = tmp_path
        content = textwrap.dedent("""\
            # Docs

            Here is an example:

                ```
                Updated: 2020-01-15
                ```

            No stale date here.
        """)
        path = root / "dispatch.md"
        f = _make_ifile(path, content, Role.DISPATCH, write=True)

        cfg = Config()
        cfg.stale_days = 30  # enable freshness check aggressively

        violations = freshness.run([f], cfg, root)
        fresh_v = [v for v in violations if v.check_id == "AL-FRESH01"]
        assert fresh_v == [], (
            f"Date inside code fence was incorrectly flagged: {[v.message for v in fresh_v]}"
        )

    def test_date_outside_fence_flagged(self, tmp_path):
        """Control: a date OUTSIDE any fence must be flagged."""
        root = tmp_path
        content = textwrap.dedent("""\
            # Docs

            Last updated: 2020-01-15

            No fence here.
        """)
        path = root / "dispatch2.md"
        f = _make_ifile(path, content, Role.DISPATCH, write=True)

        cfg = Config()
        cfg.stale_days = 30

        violations = freshness.run([f], cfg, root)
        fresh_v = [v for v in violations if v.check_id == "AL-FRESH01"]
        assert len(fresh_v) >= 1, "Expected date outside fence to be flagged"

    def test_date_inside_non_indented_fence_not_flagged(self, tmp_path):
        """Date inside a normal (non-indented) ``` fence must also be skipped."""
        root = tmp_path
        content = textwrap.dedent("""\
            # Docs

            ```
            date: 2020-03-22
            ```
        """)
        path = root / "dispatch3.md"
        f = _make_ifile(path, content, Role.DISPATCH, write=True)

        cfg = Config()
        cfg.stale_days = 30

        violations = freshness.run([f], cfg, root)
        fresh_v = [v for v in violations if v.check_id == "AL-FRESH01"]
        assert fresh_v == [], (
            f"Date inside non-indented fence was incorrectly flagged: {[v.message for v in fresh_v]}"
        )
