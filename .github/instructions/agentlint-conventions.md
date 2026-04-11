# agentlint — Developer Conventions

## Check authorship

Every check lives in `agentlint/checks/<name>.py` and exposes a single module-level function:

```python
def run(files: list[InstructionFile], config: Config, root: Path) -> list[Violation]:
```

Parameter order is always `files, config, root`. Never swap `config` and `root`.

## Adding a new check

1. Create `agentlint/checks/<name>.py` with the `run()` function.
2. Register it in `agentlint/checks/__init__.py` — both the `from` import and `__all__`.
3. Add it to the appropriate list in `agentlint/cli.py`: `_UNIQUE_CHECKS`, `_DOCS_CHECKS`, or `_STANDALONE_CHECKS`.
4. Write tests in `tests/test_<name>.py`.

## Configuration

New config keys belong in the `Config` dataclass in `agentlint/config.py` (add the field with a default) and in `_from_file()` (add the parser branch). Config is loaded from `.agentlint.yml` at the project root.

## Entry point

The CLI is defined in `agentlint/cli.py`. The package version is the single source of truth in `agentlint/__init__.py` — never hardcode version strings elsewhere.

## Testing

Run the suite with:

```
python -m pytest -k "not watch_exits"
```

The `watch_exits` test requires the optional `watchdog` dependency and is intentionally excluded from the default run.
