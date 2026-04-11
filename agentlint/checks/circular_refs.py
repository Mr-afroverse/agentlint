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
    _root_resolved = root.resolve()
    for f in relevant:
        for m in _BACKTICK_PATH_RE.finditer(f.content):
            ref = m.group(1)
            target: Path | None = None
            # 1. Exact repo-root-relative match (most common: `.github/skills/x/SKILL.md`)
            if ref in rel_map:
                target = rel_map[ref]
            else:
                # 2. Resolve relative to the containing file's parent directory.
                #    Catches references written as file-relative paths, e.g.
                #    `../skill-b/SKILL.md` inside `.github/skills/skill-a/SKILL.md`.
                try:
                    norm_rel = (
                        (f.path.parent / ref)
                        .resolve()
                        .relative_to(_root_resolved)
                        .as_posix()
                    )
                    target = rel_map.get(norm_rel)
                except ValueError:
                    pass
            if target is not None and target != f.path:
                graph[f.path].add(target)

    # Iterative DFS cycle detection using explicit colour stack.
    # Avoids Python recursion-limit crashes on deeply nested reference graphs.
    WHITE, GRAY, BLACK = 0, 1, 2
    state: dict[Path, int] = {p: WHITE for p in graph}
    reported: set[frozenset] = set()

    for start in list(graph.keys()):
        if state[start] != WHITE:
            continue
        # Each stack frame: (node, iterator-over-neighbours, path-so-far)
        _iter_stack: list[tuple[Path, object, list[Path]]] = [
            (start, iter(sorted(graph.get(start, set()), key=str)), [])
        ]
        state[start] = GRAY
        _path: list[Path] = [start]

        while _iter_stack:
            node, nb_iter, _ = _iter_stack[-1]
            try:
                nb = next(nb_iter)  # type: ignore[call-overload]
            except StopIteration:
                # Finished all neighbours of node — colour BLACK and pop
                state[node] = BLACK
                _path.pop()
                _iter_stack.pop()
                continue

            nb_state = state.get(nb, WHITE)
            if nb_state == GRAY:
                # Back-edge: cycle found
                idx = _path.index(nb)
                cycle = _path[idx:]
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
                state[nb] = GRAY
                _path.append(nb)
                _iter_stack.append(
                    (nb, iter(sorted(graph.get(nb, set()), key=str)), [])
                )

    return violations
