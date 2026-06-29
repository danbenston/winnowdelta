# Changelog

## 0.1.0 — v1

First usable release. Output schema frozen at `1.0`.

### Features
- **Structured test reporter** — run pytest, Django, Vitest, or Jest through its
  machine reporter and return only failures (`test_id`, `file:line`, assertion,
  expected/received). No passing tests, no banners, no rendered-DOM dumps.
- **Filtered build/lint deltas** — `baseline capture` then `check` reports only
  diagnostics introduced since the baseline (tsc / ESLint / Prettier). The diff
  is position-insensitive so line shifts don't re-flag pre-existing warnings.
- **Test-impact running** — `test --only` / `--tests-from -` runs only a
  caller-supplied affected-tests selection (the codegraft pipe); `--full` forces
  the whole suite for the CI gate.
- **Two surfaces** — CLI and an MCP server (`winnowdelta-mcp`), sharing one
  engine and emitting the identical versioned envelope.

### Platform
- Windows-first: routes node shims through `ComSpec`, resolves project venvs,
  per-subproject `cwd` for monorepos.
- Django needs no extra package — a dependency-free JUnit runner is injected via
  `--testrunner`.

### Validated live against
- oracle-rex/frontend — Vitest (79 tests) and Prettier deltas.
- oracle-rex backend — Django adapter end-to-end (Django 5.1.7).
- Missing-toolchain and adapter-crash paths report a clean `error` status.
