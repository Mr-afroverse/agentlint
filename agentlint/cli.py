from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import click

# Ensure stdout can handle Unicode on Windows (cp1252 terminals would crash on ✖/⚠).
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding=sys.stdout.encoding, errors="replace"
    )

from agentlint import __version__
from agentlint.adapters.aider import AiderAdapter
from agentlint.adapters.claudecode import ClaudeCodeAdapter
from agentlint.adapters.copilot import CopilotAdapter
from agentlint.adapters.continudev import ContinueAdapter
from agentlint.adapters.cursor import CursorAdapter
from agentlint.adapters.gemini import GeminiAdapter
from agentlint.adapters.windsurf import WindsurfAdapter
from agentlint.checks import (
    circular_refs,
    dead_anchors,
    deprecated_patterns,
    dispatch_coverage,
    duplicate_content,
    encoding_check,
    file_references,
    forbidden_patterns,
    freshness,
    frontmatter_schema,
    inverse_claims,
    min_content,
    number_sourcing,
    role_coverage,
    secret_detection,
    semantic_conflict,
    token_budget,
    trigger_overlap,
    vague_instructions,
    value_extraction,
)
from agentlint.checks import config_parity, consistency, ground_truth
from agentlint.config import Config
from agentlint.models import InstructionFile, LintResult, Role, Severity
from agentlint import report as rep

_ADAPTERS = [
    CopilotAdapter(),
    CursorAdapter(),
    WindsurfAdapter(),
    AiderAdapter(),
    ContinueAdapter(),
    ClaudeCodeAdapter(),
    GeminiAdapter(),
]
# Unique checks — each function runs once per adapter.
_UNIQUE_CHECKS = [
    ("dispatch-coverage", dispatch_coverage.run),
    ("deprecated-patterns", deprecated_patterns.run),
    ("circular-refs", circular_refs.run),
    ("role-coverage", role_coverage.run),
    ("file-references", file_references.run),
    ("number-sourcing", number_sourcing.run),
    ("trigger-overlap", trigger_overlap.run),
    ("forbidden-patterns", forbidden_patterns.run),
    ("value-extraction", value_extraction.run),
    ("secret-detection", secret_detection.run),
    ("inverse-claims", inverse_claims.run),
    ("dead-anchors", dead_anchors.run),
    ("vague-instructions", vague_instructions.run),
    ("token-budget", token_budget.run),
    ("encoding-check", encoding_check.run),
    ("min-content", min_content.run),
    ("frontmatter-schema", frontmatter_schema.run),
    ("duplicate-content", duplicate_content.run),
    ("semantic-conflict", semantic_conflict.run),
    ("freshness", freshness.run),
]

# File extensions that can contain instruction content worth watching.
_WATCH_EXTENSIONS = frozenset({".md", ".mdc", ".yml", ".yaml"})


# Checks that also run against extra_paths documentation files.
_DOCS_CHECKS = [
    ("file-references", file_references.run),
    ("forbidden-patterns", forbidden_patterns.run),
    ("deprecated-patterns", deprecated_patterns.run),
    ("value-extraction", value_extraction.run),
    ("secret-detection", secret_detection.run),
    ("inverse-claims", inverse_claims.run),
    ("dead-anchors", dead_anchors.run),
    ("encoding-check", encoding_check.run),
    ("freshness", freshness.run),
]

# Standalone checks driven entirely by config (not by adapter-collected files).
_STANDALONE_CHECKS = [
    ("config-parity", config_parity.run),
    ("consistency-groups", consistency.run),
    ("ground-truth", ground_truth.run),
]


def _apply_severity_overrides(violations: list, overrides: dict) -> None:
    """Mutate violation severities according to config severity_overrides."""
    for v in violations:
        if v.check_id in overrides:
            new_sev = overrides[v.check_id]
            v.severity = Severity.ERROR if new_sev == "error" else Severity.WARNING


def _rel_str(p: Path, root: Path) -> str:
    """Return *p* as a POSIX string relative to *root*."""
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _collect_extra(
    root: Path, config: Config, already: set[Path]
) -> tuple[list[InstructionFile], dict[Path, set[str]]]:
    """Glob extra_paths, dedup against *already*-collected files, return DOCS-role files.

    Returns a tuple of (files, suppressed) where *suppressed* maps a resolved
    file Path to the set of check keys that are suppressed for that file.
    Files whose ignore_paths entry has a "checks" sub-key are collected but
    tagged; files without a "checks" sub-key are blanket-ignored (skipped).
    """
    extra: list[InstructionFile] = []
    suppressed: dict[Path, set[str]] = {}
    for pattern in config.extra_paths:
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve()
            if not path.is_file() or resolved in already:
                continue
            # Respect ignore_paths
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                # Symlink or glob result that resolves outside root — skip.
                continue
            matched_ign = next((ign for ign in config.ignore_paths if ign in rel), None)
            if matched_ign is not None:
                if matched_ign not in config.ignore_checks:
                    # Blanket ignore — skip collection entirely.
                    continue
                # Per-check suppression — collect the file but record which
                # checks should not run against it.
                suppressed[resolved] = set(config.ignore_checks[matched_ign])
            already.add(resolved)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            extra.append(
                InstructionFile(
                    path=path,
                    content=content,
                    lines=content.splitlines(),
                    adapter="docs",
                    role=Role.DOCS,
                    metadata={},
                )
            )
    return extra, suppressed


def _collect_and_lint(
    root: Path, active: list, config: Config
) -> tuple[int, list, list[Path]]:
    """Run all checks against *active* adapters. Returns (total_files, violations, scanned_paths)."""
    all_violations: list = []
    total_files = 0
    already_seen: set[Path] = set()
    scanned_paths: list[Path] = []

    for a in active:
        instruction_files = a.collect(root)
        total_files += len(instruction_files)
        for f in instruction_files:
            already_seen.add(f.path.resolve())
            scanned_paths.append(f.path)
        for check_key, check_fn in _UNIQUE_CHECKS:
            if config.checks.get(check_key, True):
                all_violations.extend(check_fn(instruction_files, config, root))

    # Extra paths — run only docs-safe checks (AL-P*, AL-F01, AL-V01)
    if config.extra_paths:
        extra_files, suppressed = _collect_extra(root, config, already_seen)
        total_files += len(extra_files)
        for f in extra_files:
            scanned_paths.append(f.path)
        for check_key, check_fn in _DOCS_CHECKS:
            if config.checks.get(check_key, True):
                # Filter out files where this specific check is suppressed.
                filtered_files = [
                    f
                    for f in extra_files
                    if check_key not in suppressed.get(f.path.resolve(), set())
                ]
                if filtered_files:
                    all_violations.extend(check_fn(filtered_files, config, root))

    # Standalone config-driven checks (AL-E01, AL-C01, AL-G01)
    for check_key, check_fn in _STANDALONE_CHECKS:
        if config.checks.get(check_key, True):
            all_violations.extend(check_fn([], config, root))

    return total_files, all_violations, scanned_paths


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--format",
    "output_format",
    default=None,
    type=click.Choice(["text", "json", "sarif", "badge", "html"]),
    help="Output format (default: text). 'badge' writes agentlint-badge.svg; 'html' writes agentlint-report.html.",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to .agentlint.yml config file.",
)
@click.option(
    "--adapter",
    default="auto",
    type=click.Choice(
        [
            "copilot",
            "cursor",
            "windsurf",
            "aider",
            "continue",
            "claudecode",
            "gemini",
            "auto",
        ]
    ),
    help="Force a specific adapter (default: auto-detect).",
)
@click.option(
    "--fail-on-warnings",
    is_flag=True,
    default=False,
    help="Exit 1 when warnings are present (overrides config).",
)
@click.option(
    "--init",
    is_flag=True,
    default=False,
    help="Copy SKILL_HEALTH_CHECK.md template into .github/skills/.",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Re-run on file changes. Requires: pip install 'instruction-lint[watch]'.",
)
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(),
    help="Baseline file — suppress violations already recorded there. See --update-baseline.",
)
@click.option(
    "--update-baseline",
    "update_baseline_path",
    default=None,
    type=click.Path(),
    help="Snapshot current violations to PATH and exit 0.",
)
@click.option(
    "--fix",
    "apply_fix",
    is_flag=True,
    default=False,
    help="Auto-fix violations that have a deterministic fix. Modifies files in-place.",
)
def main(
    path: str,
    output_format: str | None,
    config_path: str | None,
    adapter: str,
    fail_on_warnings: bool,
    init: bool,
    watch: bool,
    baseline_path: str | None,
    update_baseline_path: str | None,
    apply_fix: bool,
) -> None:
    """agentlint — audit AI coding assistant instruction files.

    \b
    Checks GitHub Copilot skills, Cursor rules, and more for:
      - broken path references
      - skills missing from the dispatch table
      - threshold numbers without source pointers
      - overlapping trigger descriptions
      - forbidden / drift-prone patterns
    """
    root = Path(path).resolve()

    if init:
        _run_init(root)
        return

    # Load config
    if config_path:
        config = Config._from_file(Path(config_path))
    else:
        config = Config.load(root)
    if output_format:
        config.output_format = output_format
    if fail_on_warnings:
        config.fail_on_warnings = True

    # Detect adapters:
    #   auto  → run detect() on every adapter, include those that match
    #   named → trust the user, skip detect() (same contract as eslint --parser)
    active = [
        a
        for a in _ADAPTERS
        if (adapter == "auto" and a.detect(root))
        or (adapter != "auto" and a.name == adapter)
    ]

    total_files, all_violations, scanned_paths = _collect_and_lint(root, active, config)

    # Apply per-check severity overrides from config
    if config.severity_overrides:
        _apply_severity_overrides(all_violations, config.severity_overrides)

    # Guard: exit 2 when nothing was collected — covers both "no adapter matched"
    # in auto mode, and "adapter named but repo has no instruction files yet".
    # Skip guard if standalone checks (AL-E01, AL-C01) found violations.
    if total_files == 0 and not all_violations:
        if adapter == "auto":
            click.echo(
                "[agentlint] No supported instruction format detected.\n"
                "  Looked for: .github/copilot-instructions.md, .cursorrules, .cursor/rules/,"
                " .windsurfrules, .windsurf/rules/, .aider.conf.yml, .aider/rules/,"
                " .continuerules, .continue/rules/, CLAUDE.md, .claude/,"
                " GEMINI.md, .gemini/\n"
                "  Use --adapter copilot/cursor/windsurf/aider/continue/claudecode/gemini"
                " to force.",
                err=True,
            )
        else:
            click.echo(
                f"[agentlint] No instruction files found for adapter '{adapter}'.\n"
                f"  Check that the expected files exist in {root.as_posix()}",
                err=True,
            )
        sys.exit(2)

    result = LintResult(
        root=root,
        files_scanned=total_files,
        violations=all_violations,
        adapter="+".join(a.name for a in active),
        scanned_files=[_rel_str(p, root) for p in scanned_paths],
    )

    # --fix: apply auto-fixes before any output or baseline logic
    if apply_fix:
        from agentlint.fixer import apply_fixes

        applied, skipped = apply_fixes(result.violations, root)
        fixed_ids = {id(v) for v in applied}
        remaining = [v for v in result.violations if id(v) not in fixed_ids]
        result = LintResult(
            root=result.root,
            files_scanned=result.files_scanned,
            violations=remaining,
            adapter=result.adapter,
            scanned_files=result.scanned_files,
        )
        if applied:
            click.echo(
                f"[agentlint] Fixed {len(applied)} violation(s). "
                f"{len(remaining)} remaining.",
                err=True,
            )
        else:
            click.echo("[agentlint] No auto-fixable violations found.", err=True)

    # --update-baseline: snapshot and exit before any filtering or output
    if update_baseline_path:
        bp = Path(update_baseline_path)
        _save_baseline(bp, result.violations, root)
        click.echo(
            f"[agentlint] Baseline written to {bp.as_posix()}"
            f"  ({len(result.violations)} violation(s) recorded)"
        )
        return

    # --baseline: suppress violations already in the baseline
    if baseline_path:
        bp = Path(baseline_path)
        known = _load_baseline(bp)
        new_violations = [
            v
            for v in result.violations
            if (v.check_id, _rel_str(v.file, root), v.message) not in known
        ]
        suppressed = len(result.violations) - len(new_violations)
        result = LintResult(
            root=result.root,
            files_scanned=result.files_scanned,
            violations=new_violations,
            adapter=result.adapter,
            scanned_files=result.scanned_files,
        )
        if suppressed:
            click.echo(
                f"[agentlint] Baseline: {suppressed} pre-existing violation(s) suppressed.",
                err=True,
            )

    if config.output_format == "json":
        click.echo(rep.format_json(result, root))
    elif config.output_format == "sarif":
        click.echo(rep.format_sarif(result, root))
    elif config.output_format == "badge":
        svg = rep.format_badge(result)
        badge_path = root / "agentlint-badge.svg"
        badge_path.write_text(svg, encoding="utf-8")
        click.echo(
            f"[agentlint] Badge written to {badge_path.as_posix()}  (Grade: {result.grade()})"
        )
    elif config.output_format == "html":
        html = rep.format_html(result, root)
        report_path = root / "agentlint-report.html"
        report_path.write_text(html, encoding="utf-8")
        click.echo(
            f"[agentlint] HTML report written to {report_path.as_posix()}  (Grade: {result.grade()})"
        )
    else:
        click.echo(rep.format_text(result, root))

    if watch:
        _watch_loop(root, active, config)
        return

    if not result.passed or (config.fail_on_warnings and result.warnings):
        sys.exit(1)


def _load_baseline(path: Path) -> set[tuple[str, str, str]]:
    """Load a baseline JSON file. Returns a set of (check_id, file_rel, message) tuples."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        click.echo(
            f"[agentlint] Warning: could not read baseline '{path}' "
            "— treating all violations as new.",
            err=True,
        )
        return set()
    return {
        (v["check_id"], v["file"], v["message"])
        for v in data.get("violations", [])
        if isinstance(v, dict) and "check_id" in v and "file" in v and "message" in v
    }


def _save_baseline(path: Path, violations: list, root: Path) -> None:
    """Serialize violations to a baseline JSON file."""
    entries = [
        {
            "check_id": v.check_id,
            "file": _rel_str(v.file, root),
            "message": v.message,
        }
        for v in violations
    ]
    payload = {
        "_comment": "agentlint baseline — commit to suppress pre-existing violations",
        "violations": entries,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_init(root: Path) -> None:
    from agentlint import TEMPLATES_DIR

    src = TEMPLATES_DIR / "SKILL_HEALTH_CHECK.md"
    if not src.exists():
        click.echo("[agentlint] Template not found — reinstall agentlint.", err=True)
        sys.exit(1)

    dest_dir = root / ".github" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL_HEALTH_CHECK.md"

    if dest.exists():
        click.echo(f"[agentlint] {dest} already exists — not overwriting.")
    else:
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        click.echo(f"[agentlint] Created {dest}")

    _run_config_wizard(root)


def _run_config_wizard(root: Path) -> None:
    """Generate a starter .agentlint.yml by probing the repo layout."""
    cfg_file = root / ".agentlint.yml"
    if cfg_file.exists():
        click.echo(f"[agentlint] {cfg_file} already exists — not overwriting.")
        return

    # Probe filesystem
    has_src = (root / "src").is_dir()
    has_app = (root / "app").is_dir()
    has_docs = (root / "docs").is_dir()
    has_readme = (root / "README.md").exists()

    source_root_lines = ['  - "."']
    if has_src:
        source_root_lines.append('  - "src"')
    if has_app:
        source_root_lines.append('  - "app"')

    extra_path_hints: list[str] = []
    if has_readme:
        extra_path_hints.append('#   - "README.md"')
    if has_docs:
        extra_path_hints.append('#   - "docs/**/*.md"')

    extra_paths_block = "# extra_paths:\n"
    if extra_path_hints:
        extra_paths_block += "\n".join(extra_path_hints) + "\n"

    source_roots_yaml = "\n".join(source_root_lines)

    yaml_out = (
        "# .agentlint.yml -- generated by agentlint --init\n"
        "# Review, adjust, and commit this file.\n"
        "# Full reference: https://github.com/Mr-afroverse/agentlint#configuration\n"
        "\n"
        "source_roots:\n"
        f"{source_roots_yaml}\n"
        "\n"
        "ignore_paths:\n"
        '  - "archive/"\n'
        '  - "node_modules/"\n'
        '  - ".venv/"\n'
        "\n"
        "fail_on_warnings: false\n"
        "\n"
        "# Lint extra documentation files with AL-P* and AL-F01.\n"
        f"{extra_paths_block}"
        "\n"
        "# Warn when an instruction file exceeds this estimated token count (0 = disabled).\n"
        "# token_budget: 8000\n"
    )

    cfg_file.write_text(yaml_out, encoding="utf-8")
    click.echo(f"[agentlint] Created {cfg_file}")


def _watch_loop(root: Path, active: list, config: Config) -> None:
    """Block until Ctrl+C, re-linting whenever a watched file changes."""
    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore[import]
        from watchdog.observers import Observer  # type: ignore[import]
    except ImportError:
        click.echo(
            "[agentlint] --watch requires watchdog.\n"
            "  Install it: pip install 'instruction-lint[watch]'",
            err=True,
        )
        sys.exit(1)

    import threading
    import time

    _lock = threading.Lock()
    _pending_timer: threading.Timer | None = None

    def _schedule_rerun() -> None:
        nonlocal _pending_timer
        with _lock:
            if _pending_timer is not None:
                _pending_timer.cancel()
            _pending_timer = threading.Timer(0.3, _do_lint)
            _pending_timer.start()

    def _do_lint() -> None:
        total_files, all_violations, scanned = _collect_and_lint(root, active, config)
        # Apply severity overrides — mirrors the logic in main()
        if config.severity_overrides:
            _apply_severity_overrides(all_violations, config.severity_overrides)
        result = LintResult(
            root=root,
            files_scanned=total_files,
            violations=all_violations,
            adapter="+".join(a.name for a in active),
            scanned_files=[_rel_str(p, root) for p in scanned],
        )
        click.echo("\n" + "\u2500" * 60)
        if config.output_format == "json":
            click.echo(rep.format_json(result, root))
        elif config.output_format == "sarif":
            click.echo(rep.format_sarif(result, root))
        else:
            click.echo(rep.format_text(result, root))

    class _Handler(FileSystemEventHandler):
        def _maybe_rerun(self, event) -> None:
            if (
                not event.is_directory
                and Path(event.src_path).suffix in _WATCH_EXTENSIONS
            ):
                _schedule_rerun()

        def on_modified(self, event) -> None:
            self._maybe_rerun(event)

        def on_created(self, event) -> None:
            self._maybe_rerun(event)

        def on_deleted(self, event) -> None:
            self._maybe_rerun(event)

    observer = Observer()
    observer.schedule(_Handler(), str(root), recursive=True)
    observer.start()
    click.echo(f"[agentlint] Watching {root.as_posix()} \u2014 press Ctrl+C to stop.")

    try:
        while observer.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        with _lock:
            if _pending_timer is not None:
                _pending_timer.cancel()
        observer.stop()
        observer.join()
    click.echo("\n[agentlint] Watch stopped.")


if __name__ == "__main__":
    main()
