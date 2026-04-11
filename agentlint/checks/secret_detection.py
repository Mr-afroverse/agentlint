"""
AL-S01   Secret / credential detection.

Flags lines in instruction files and docs that appear to contain real API
keys, tokens, or private key material.  Reports are warnings by default —
false positives are possible.  The matched value is redacted in output.

Patterns cover the top credential formats seen in production codebases:
  AWS access key, GitHub tokens, OpenAI key, Anthropic key, JWT, PEM block,
  generic high-entropy assignments (32+ hex chars after '=').
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Severity, Violation

# ---------------------------------------------------------------------------
# Pattern registry — each entry: (check_sub_id, description, compiled_regex)
# Note: patterns deliberately avoid matching common placeholder/example values
# such as "your-api-key-here", "xxxx…", "<TOKEN>", etc.
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "AL-S01-AWS",
        "Possible AWS Access Key ID",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "AL-S01-GH",
        "Possible GitHub classic token (ghp_)",
        re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    ),
    (
        "AL-S01-GH-PAT",
        "Possible GitHub fine-grained PAT",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{59}\b"),
    ),
    (
        "AL-S01-OPENAI",
        "Possible OpenAI API key",
        re.compile(r"\bsk-[A-Za-z0-9]{48}\b"),
    ),
    (
        "AL-S01-OPENAI-PROJ",
        "Possible OpenAI project API key",
        re.compile(r"\bsk-proj-[A-Za-z0-9_-]{130,}\b"),
    ),
    (
        "AL-S01-ANTHROPIC",
        "Possible Anthropic API key",
        re.compile(r"\bsk-ant-(?:api03-)[A-Za-z0-9_-]{93}\b"),
    ),
    (
        "AL-S01-JWT",
        "Possible JWT token",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    (
        "AL-S01-PEM",
        "PEM private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "AL-S01-HEX",
        "Possible secret: high-entropy hex string assigned to a key-like variable",
        re.compile(
            r"(?i)(?:api[-_]?key|secret[-_]?key|access[-_]?token|auth[-_]?token)"
            r'\s*[=:]\s*["\']?[0-9a-f]{32,}["\']?'
        ),
    ),
]

# Common placeholder patterns — skip these to reduce false positives
_PLACEHOLDER = re.compile(
    r"(?i)(?:your|example|placeholder|fake|test|dummy|sample|xxxx|<[^>]+>)"
)


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    for f in files:
        normalized = f.path.as_posix()
        if any(ign in normalized for ign in config.ignore_paths):
            continue

        for lineno, line in enumerate(f.lines, start=1):
            # Skip lines that look like comments explaining what a secret looks like
            if _PLACEHOLDER.search(line):
                continue

            for check_id, description, pattern in _PATTERNS:
                if pattern.search(line):
                    new_line = pattern.sub("<REDACTED>", line)
                    violations.append(
                        Violation(
                            check_id=check_id,
                            severity=Severity.WARNING,
                            file=f.path,
                            line=lineno,
                            message=f"{description} found in instruction file.",
                            fix_hint=(
                                "Remove the credential and rotate it immediately. "
                                "Use an environment variable reference instead."
                            ),
                            auto_fixable=True,
                            fix_data={"old_line": line, "new_line": new_line},
                        )
                    )
                    break  # one violation per line — avoid duplicate alerts

    return violations
