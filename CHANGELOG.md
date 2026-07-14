# Changelog

## 0.1.3

- Add: every build/lint/check envelope now carries **`checked`** — the list of
  diagnostic tools that actually ran (e.g. `["tsc", "eslint"]`). This removes a
  real ambiguity: an empty `diagnostics` with a non-empty `checked` means "ran
  and clean", while an empty `checked` means "nothing was checked" (no tool for
  the requested `kind`, or none detected). Previously both looked identical (a
  bare `0`), which pushed agents to shell out to a raw `tsc`/`eslint` just to get
  an unambiguous "it compiled" signal. Additive to the frozen `1.0` schema; the
  text renderer now prints `no new diagnostics — ran tsc, eslint` (or `no tools
  ran — nothing to check`) instead of a bare `no new diagnostics`.
- Docs: clarified the `build_lint_delta` MCP tool docstring so `all=True` reads
  as what it is — the absolute "does this build/lint from scratch?" check that
  **returns empty when clean** (right for brand-new files/packages), with an
  explicit note that it is noisy in an already-dirty tree. The old wording
  ("reports every current diagnostic") read as high-output and got avoided.

## 0.1.2

- Fix: the `tsc` diagnostic adapter now detects **TypeScript project references
  / composite builds** (a `tsconfig.json` with a non-empty `references` array or
  `composite: true`) and drives them through `tsc -b`. Previously it always ran
  plain `tsc --noEmit`, which ignores project references — against a
  solution-style root (`files: []` + `references`) it type-checked *nothing* and
  reported a false-clean, silently missing every type error. Flat projects are
  unchanged (`tsc --noEmit`); an explicit `build` command in `winnowdelta.toml`
  still wins. Verified end-to-end against a composite monorepo (CrucibleQL).

## 0.1.1

- Fix: a configured command with a relative executable (e.g.
  `.venv/Scripts/python.exe`) now resolves against the subproject's `cwd`
  instead of failing with WinError 2 on Windows. Found while wiring oracle-rex's
  multi-root config (backend 136 passed, frontend 79 passed).

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
