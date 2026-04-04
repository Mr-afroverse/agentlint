# Contributing to agentlint

Thank you for your interest. This guide covers how to add new adapters and checks — the two main extension points.

---

## Setup

```bash
git clone https://github.com/Mr-afroverse/agentlint
cd agentlint
pip install -e ".[dev]"
pytest   # all 155 tests should pass
```

---

## Adding an adapter

Adapters detect and parse instruction files for a specific AI assistant.

1. Create `agentlint/adapters/<name>.py`:

```python
from pathlib import Path
from .base import BaseAdapter
from ..models import InstructionFile, Role

class MyAdapter(BaseAdapter):
    name = "myadapter"

    def detect(self, root: Path) -> bool:
        return (root / ".myrules").exists() or (root / ".my" / "rules").is_dir()

    def collect(self, root: Path) -> list[InstructionFile]:
        files = []
        dispatch = root / ".myrules"
        if dispatch.exists():
            content, lines = self._read(dispatch)
            files.append(InstructionFile(
                path=dispatch, content=content, lines=lines,
                adapter=self.name, role=Role.DISPATCH,
            ))
        for skill in (root / ".my" / "rules").glob("*.md"):
            content, lines = self._read(skill)
            files.append(InstructionFile(
                path=skill, content=content, lines=lines,
                adapter=self.name, role=Role.SKILL,
            ))
        return files
```

2. Export from `agentlint/adapters/__init__.py`:
```python
from .myadapter import MyAdapter
```

3. Register in `agentlint/cli.py` `_ADAPTERS` list:
```python
_ADAPTERS = [CopilotAdapter(), CursorAdapter(), WindsurfAdapter(), AiderAdapter(), ContinueAdapter(), MyAdapter()]
```

4. Add to the `--adapter` Choice in `cli.py` and add tests in `tests/test_cli.py`.

---

## Adding a check

Checks receive a list of `InstructionFile` objects and return `Violation` objects.

1. Create `agentlint/checks/<name>.py`:

```python
from pathlib import Path
from ..models import InstructionFile, Violation, Severity
from ..config import Config

CHECK_ID = "AL-X01"

def run(files: list[InstructionFile], config: Config, root: Path) -> list[Violation]:
    violations = []
    for f in files:
        for i, line in enumerate(f.lines, 1):
            if "bad_pattern" in line:
                violations.append(Violation(
                    check_id=CHECK_ID,
                    severity=Severity.WARNING,
                    file=f.path,
                    line=i,
                    message="Found bad_pattern.",
                    fix_hint="Replace with good_pattern.",
                ))
    return violations
```

2. Register in `agentlint/checks/__init__.py`.

3. Wire into the check loop in `agentlint/cli.py`.

4. Add tests in `tests/test_<name>.py`.

---

## Check IDs

| Range | Category |
|---|---|
| AL-D* | Dispatch coverage |
| AL-F* | File references |
| AL-N* | Number sourcing |
| AL-T* | Trigger overlap |
| AL-P* | Forbidden patterns |
| AL-X* | Reserved for community checks |

Pick the next available ID in your category and document it in the README checks table.

---

## Pull request checklist

- [ ] Tests added / updated (`pytest` passes)
- [ ] New check ID documented in README table
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] No new runtime dependencies (only `click` and `pyyaml` allowed)

---

## Reporting issues

Open an issue at [github.com/Mr-afroverse/agentlint/issues](https://github.com/Mr-afroverse/agentlint/issues). Include:
- `agentlint --version` output
- The command you ran
- The full output (text or JSON)
