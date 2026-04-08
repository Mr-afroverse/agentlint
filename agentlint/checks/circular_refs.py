"""
AL-D03  Circular file references.

Detects cycles in the reference graph built from backtick-quoted file paths
across instruction files (DISPATCH and SKILL roles).

A cycle such as DISPATCH → SKILL-A → DISPATCH is subtle but real — it means
a skill routes back to the main dispatch file in its own instructions, creating
a circular dependency that confuses agents trying to follow the reference chain.

SKILL → SKILL → ... → SKILL cycles are also detected.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity, Violation

# Any backtick-quoted relative path: `some/path/to/file.ext`
_BACKTICK_PATH_RE = re.compile(r"`([^`\n]+\.[a-zA-Z]{1,10})`")


def run(
    files: list[InstructionFile],
    config: Config,
    root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    relevant = [f for f in files if f.role in (Role.DISPATCH, Role.SKILL)]
    if len(relevant) < 2:
        return violations

    # Map relative POSIX path → absolute Path for instruction files only.
    rel_map: dict[str, Path] = {
        f.path.relative_to(root).as_posix(): f.path for f in relevant
    }

    # Build directed adjacency: abs_path → set[abs_path]
    graph: dict[Path, set[Path]] = {f.path: set() for f in relevant}
    for f in relevant:
        for m in _BACKTICK_PATH_RE.finditer(f.content):
            ref = m.group(1)
            if ref in rel_map:
                target = rel_map[ref]
                if target != f.path:
                    graph[f.path].add(target)

    # DFS cycle detection using recursion-stack colouring.
    WHITE, GRAY, BLACK = 0, 1, 2
    state: dict[Path, int] = {p: WHITE for p in graph}
    path: list[Path] = []
    reported: set[frozenset] = set()

    def _dfs(node: Path) -> None:
        state[node] = GRAY
        path.append(node)
        for nb in sorted(graph.get(node, set()), key=str):
            nb_state = state.get(nb, WHITE)
            if nb_state == GRAY:
                # Back-edge found — extract cycle.
                idx = path.index(nb)
                cycle = path[idx:]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    cycle_str = (
                        " → ".join(p.relative_to(root).as_posix() for p in cycle)
                        + f" → {nb.relative_to(root).as_posix()}"
                    )
                    violations.append(
                        Violation(
                            check_id="AL-D03",
                            severity=Severity.ERROR,
                            file=cycle[0],
                            line=None,
                            message=f"Circular reference detected: {cycle_str}",
                            fix_hint="Remove the back-reference to break the cycle.",
                        )
                    )
            elif nb_state == WHITE and nb in state:
                _dfs(nb)
        path.pop()
        state[node] = BLACK

    for node in list(graph.keys()):
        if state[node] == WHITE:
            _dfs(node)

    return violations
