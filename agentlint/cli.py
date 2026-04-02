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
from agentlint.adapters.copilot import CopilotAdapter
from agentlint.adapters.cursor import CursorAdapter
from agentlint.adapters.windsurf import WindsurfAdapter
from agentlint.checks import dispatch_coverage, file_references, forbidden_patterns, number_sourcing, trigger_overlap
from agentlint.config import Config
from agentlint.models import LintResult
from agentlint import report as rep

_ADAPTERS = [CopilotAdapter(), CursorAdapter(), WindsurfAdapter()]
# Unique checks — each function runs once per adapter.
_UNIQUE_CHECKS = [
    ("dispatch-coverage",  dispatch_coverage.run),
    ("file-references",    file_references.run),
    ("number-sourcing",    number_sourcing.run),
    ("trigger-overlap",    trigger_overlap.run),
    ("forbidden-patterns", forbidden_patterns.run),
]


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--format", "output_format",
    default=None,
    type=click.Choice(["text", "json", "sarif"]),
    help="Output format (default: text).",
)
@click.option(
    "--config", "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to .agentlint.yml config file.",
)
@click.option(
    "--adapter",
    default="auto",
    type=click.Choice(["copilot", "cursor", "windsurf", "auto"]),
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
def main(
    path: str,
    output_format: str | None,
    config_path: str | None,
    adapter: str,
    fail_on_warnings: bool,
    init: bool,
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
        a for a in _ADAPTERS
        if (adapter == "auto" and a.detect(root)) or (adapter != "auto" and a.name == adapter)
    ]

    all_violations = []
    total_files = 0

    for a in active:
        instruction_files = a.collect(root)
        total_files += len(instruction_files)

        for check_key, check_fn in _UNIQUE_CHECKS:
            if config.checks.get(check_key, True):
                all_violations.extend(check_fn(instruction_files, config, root))

    # Guard: exit 2 when nothing was collected — covers both "no adapter matched"
    # in auto mode, and "adapter named but repo has no instruction files yet".
    if total_files == 0:
        if adapter == "auto":
            click.echo(
                "[agentlint] No supported instruction format detected.\n"
                "  Looked for: .github/copilot-instructions.md, .cursorrules, .cursor/rules/,"
                " .windsurfrules, .windsurf/rules/\n"
                "  Use --adapter copilot, --adapter cursor, or --adapter windsurf to force.",
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
    )

    if config.output_format == "json":
        click.echo(rep.format_json(result, root))
    elif config.output_format == "sarif":
        click.echo(rep.format_sarif(result, root))
    else:
        click.echo(rep.format_text(result, root))

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


if __name__ == "__main__":
    main()
