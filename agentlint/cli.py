from __future__ import annotations

import io
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
from agentlint.adapters.copilot import CopilotAdapter
from agentlint.adapters.continudev import ContinueAdapter
from agentlint.adapters.cursor import CursorAdapter
from agentlint.adapters.windsurf import WindsurfAdapter
from agentlint.checks import (
    dispatch_coverage,
    file_references,
    forbidden_patterns,
    number_sourcing,
    trigger_overlap,
    value_extraction,
)
from agentlint.checks import config_parity, consistency, ground_truth
from agentlint.config import Config
from agentlint.models import InstructionFile, LintResult, Role
from agentlint import report as rep

_ADAPTERS = [
    CopilotAdapter(),
    CursorAdapter(),
    WindsurfAdapter(),
    AiderAdapter(),
    ContinueAdapter(),
]
# Unique checks — each function runs once per adapter.
_UNIQUE_CHECKS = [
    ("dispatch-coverage", dispatch_coverage.run),
    ("file-references", file_references.run),
    ("number-sourcing", number_sourcing.run),
    ("trigger-overlap", trigger_overlap.run),
    ("forbidden-patterns", forbidden_patterns.run),
    ("value-extraction", value_extraction.run),
]

# File extensions that can contain instruction content worth watching.
_WATCH_EXTENSIONS = frozenset({".md", ".mdc", ".yml", ".yaml"})


# Checks that also run against extra_paths documentation files.
_DOCS_CHECKS = [
    ("file-references", file_references.run),
    ("forbidden-patterns", forbidden_patterns.run),
    ("value-extraction", value_extraction.run),
]

# Standalone checks driven entirely by config (not by adapter-collected files).
_STANDALONE_CHECKS = [
    ("config-parity", config_parity.run),
    ("consistency-groups", consistency.run),
    ("ground-truth", ground_truth.run),
]


def _rel_str(p: Path, root: Path) -> str:
    """Return *p* as a POSIX string relative to *root*."""
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _collect_extra(
    root: Path, config: Config, already: set[Path]
) -> list[InstructionFile]:
    """Glob extra_paths, dedup against *already*-collected files, return DOCS-role files."""
    extra: list[InstructionFile] = []
    for pattern in config.extra_paths:
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve()
            if not path.is_file() or resolved in already:
                continue
            # Respect ignore_paths
            rel = path.relative_to(root).as_posix()
            if any(ign in rel for ign in config.ignore_paths):
                continue
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
    return extra


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
        extra_files = _collect_extra(root, config, already_seen)
        total_files += len(extra_files)
        for f in extra_files:
            scanned_paths.append(f.path)
        for check_key, check_fn in _DOCS_CHECKS:
            if config.checks.get(check_key, True):
                all_violations.extend(check_fn(extra_files, config, root))

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
    type=click.Choice(["text", "json", "sarif", "badge"]),
    help="Output format (default: text). 'badge' writes agentlint-badge.svg to disk.",
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
    type=click.Choice(["copilot", "cursor", "windsurf", "aider", "continue", "auto"]),
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
def main(
    path: str,
    output_format: str | None,
    config_path: str | None,
    adapter: str,
    fail_on_warnings: bool,
    init: bool,
    watch: bool,
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
        for v in all_violations:
            if v.check_id in config.severity_overrides:
                from agentlint.models import Severity as _Sev

                new_sev = config.severity_overrides[v.check_id]
                v.severity = _Sev.ERROR if new_sev == "error" else _Sev.WARNING

    # Guard: exit 2 when nothing was collected — covers both "no adapter matched"
    # in auto mode, and "adapter named but repo has no instruction files yet".
    # Skip guard if standalone checks (AL-E01, AL-C01) found violations.
    if total_files == 0 and not all_violations:
        if adapter == "auto":
            click.echo(
                "[agentlint] No supported instruction format detected.\n"
                "  Looked for: .github/copilot-instructions.md, .cursorrules, .cursor/rules/,"
                " .windsurfrules, .windsurf/rules/, .aider.conf.yml, .aider/rules/,"
                " .continuerules, .continue/rules/\n"
                "  Use --adapter copilot/cursor/windsurf/aider/continue to force.",
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
    else:
        click.echo(rep.format_text(result, root))

    if watch:
        _watch_loop(root, active, config)
        return

    if not result.passed or (config.fail_on_warnings and result.warnings):
        sys.exit(1)


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
            from agentlint.models import Severity as _Sev

            for v in all_violations:
                if v.check_id in config.severity_overrides:
                    new_sev = config.severity_overrides[v.check_id]
                    v.severity = _Sev.ERROR if new_sev == "error" else _Sev.WARNING
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
