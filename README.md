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

v1 (schema frozen at `1.0`). Supported V1 stacks: pytest · Django · Vitest ·
Jest for tests, and tsc · ESLint · Prettier for build/lint deltas.

- [docs/configuration.md](docs/configuration.md) — `winnowdelta.toml` reference,
  multi-root example, invocation quirks.
- [docs/schema.md](docs/schema.md) — the v1 output envelope.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — phased build-out;
  [run-and-filter-feedback-tool.md](run-and-filter-feedback-tool.md) — full concept.

The point: collapse a verbose run into the minimal machine-actionable signal.
On a trivial 4-test suite `--text` output is already ~80% smaller than raw
pytest output; the saving grows with suite size, since winnowdelta's output
tracks only the failures while raw output grows with every passing test and
rendered trace.

## Install (development)

```sh
pip install -e ".[dev]"
```

## Usage

```sh
winnowdelta --help
winnowdelta --version

# Tests — report only failures (file:line + assertion), no passing/banner noise
winnowdelta test                      # whole suite (autodetects the runner)
winnowdelta test --text               # human-readable instead of JSON

# Build/lint deltas — only diagnostics introduced since the baseline
winnowdelta baseline capture          # snapshot current diagnostics before editing
winnowdelta check                     # ...then report only what's new
winnowdelta check --kind lint --all   # all current diagnostics, ignore baseline

# Test-impact running — run only the affected tests
winnowdelta test --only path/to/test.py::test_x
codegraft-impact | winnowdelta test --tests-from -   # consume an affected-tests list
winnowdelta test --full               # CI gate: ignore selection, run everything
```

### The codegraft pipe

Selection is upstream (codegraft decides *what* matters); winnowdelta only
*executes*. The natural pipeline is:

```
codegraft.impact_of(changed) ∩ test_paths  →  winnowdelta test --tests-from -
```

Because the selection is heuristic and can miss tests, `--tests-from`/`--only`
is a fast inner-loop accelerator only. A CI gate must run `winnowdelta test
--full` before merge.

## MCP server

The same engine is exposed over MCP (stdio) so a coding agent gets identical
filtered deltas. Install the extra and run the server:

```sh
pip install -e ".[mcp]"
winnowdelta-mcp            # or: python -m winnowdelta.mcp.server
```

Tools: `run_tests` (with `selection` / `full` for impact running),
`build_lint_delta` (with `kind` / `all`), `capture_baseline`, `clear_baseline`.
Each takes an optional `root` (defaults to the server's working directory) and
returns the same versioned envelope as the CLI.

## Develop

```sh
pytest        # tests
ruff check .  # lint
mypy          # types
```
