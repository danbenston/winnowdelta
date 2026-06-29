# winnowdelta

A standalone CLI/MCP tool that **executes** a project's test, build, and lint
commands and returns only the **structured, filtered delta** — the failures and
the new-vs-baseline diagnostics — instead of raw, verbose console output.

It *runs and reads*; it never edits code and never *selects* which files matter
(that's [codegraft](run-and-filter-feedback-tool.md)). Its job is to collapse
thousands of tokens of rendered DOM trees, stack traces, and pre-existing-warning
spam into the minimal machine-actionable signal a coding agent needs to decide
what to fix next.

## Status

Early development. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the
phased build-out and [run-and-filter-feedback-tool.md](run-and-filter-feedback-tool.md)
for the full concept and V1 scope.

## Install (development)

```sh
pip install -e ".[dev]"
```

## Usage

```sh
winnowdelta --help
winnowdelta --version
winnowdelta test            # Phase 0: emits the empty output envelope
```

## Develop

```sh
pytest        # tests
ruff check .  # lint
mypy          # types
```
