# Winnowdelta — Implementation Plan

The repo name `winnowdelta` fits the concept: *winnow* the noise, return the *delta*.
This plan builds the run-and-filter feedback tool described in
[run-and-filter-feedback-tool.md](run-and-filter-feedback-tool.md) from the ground up.

## Guiding architecture

Three user-facing features, but one internal pipeline:

```
invoke command (cwd/env aware)  →  capture structured output
   →  parse via per-framework adapter  →  NormalizedResult
   →  filter (failures only / baseline delta)  →  emit compact JSON
```

Everything funnels through a single **normalized result model** and a single
**adapter protocol**. Add a language/tool = write one adapter, not a new pipeline.
Two surfaces (CLI + MCP) wrap the same core.

**Cross-cutting decisions to lock in Phase 0–1 (they ripple through everything):**

- **Output schema** is the product contract — design it once, version it, snapshot-test it.
- **Config file** (`winnowdelta.toml`) declares subprojects (`cwd` + commands) so the
  monorepo (oracle-rex: Django root + `frontend/`) works without guessing.
- **Execution layer** centralizes the Windows quirks (`npm.cmd` via `ComSpec`, project
  `.venv` python, per-subproject `cwd`) so no adapter re-solves them.

---

## Phase 0 — Scaffolding & the tool's own test harness

**Goal:** a real Python package that builds, tests, and runs an empty command end-to-end.

- Replace `main.py` stub with package layout: `src/winnowdelta/`
  (`__init__`, `cli`, `core/`, `adapters/`, `mcp/`).
- `pyproject.toml`: package metadata, `console_scripts` entry point (`winnowdelta`),
  dev deps (pytest, ruff, mypy).
- CI skeleton (GitHub Actions) running on **Windows** runner — this tool is
  Windows-developed/run, so CI must be too.
- `.gitignore`, README stub, license. First commit (repo has zero commits).
- **Exit criteria:** `pip install -e .`, `winnowdelta --help`, and `pytest` all work in CI.

## Phase 1 — Execution core + normalized model (the foundation)

**Goal:** reliably run *any* command in the right place and represent the result,
before any framework is parsed.

- **Runner abstraction** (`core/runner.py`): takes `(command, cwd, env)`, returns
  `(exit_code, stdout, stderr, duration)`. Handles:
  - Windows `npm.cmd`/`npx.cmd` invocation through `ComSpec` (bare `npm` is a Unix shim → fails).
  - Project venv resolution (`.venv\Scripts\python.exe`).
  - Per-subproject `cwd` (no single-root assumption).
  - Timeouts and clean process-tree kill.
- **Normalized model** (`core/model.py`): `NormalizedRun`,
  `Failure(test_id, file, line, expected, received, message)`,
  `Diagnostic(file, line, col, rule, severity, message)`.
- **Adapter protocol** (`core/adapter.py`): `build_command(config)` + `parse(run) -> NormalizedRun`.
- **Config loader** (`core/config.py`): `winnowdelta.toml` → subproject definitions
  (stack, cwd, test/lint/build commands), plus framework **autodetection** fallback.
- **Output schema + emitter** (`core/output.py`): stable, versioned JSON; one
  human-readable text renderer.
- **Exit criteria:** can execute a trivial command in a configured subproject
  (incl. a `frontend/` cwd and a venv python) and emit the empty-but-valid schema.

## Phase 2 — First vertical slice: pytest reporter + CLI

**Goal:** Feature #1 working end-to-end for one framework — proves the whole pipeline
and freezes the contract.

- `adapters/pytest_adapter.py`: invoke via `pytest-reportlog`/`--json`, parse to
  `Failure[]` (test name, `file:line`, expected vs received, the one assertion message).
  Drop passes, banners, captured stdout.
- `cli.py`: `winnowdelta test [subproject]` → runs pytest adapter → compact JSON/text.
- Snapshot tests against fixture projects (passing suite, failing suite,
  error/collection failure).
- **Exit criteria:** on a sample failing pytest project, output is just the failures —
  measurably a fraction of raw console tokens.

## Phase 3 — Remaining test adapters

**Goal:** cover the V1 stacks. Reuse the Phase 2 contract; each is just a new adapter.

- **Vitest** (`vitest run --reporter=json`) and **Jest** (`jest --json`, `jest-expo`
  preset) — exercise the `npm.cmd`/`ComSpec` path and `frontend/` cwd.
- **Django/unittest** — the hard one (no native structured reporter). Build a real
  adapter via `unittest-xml-reporting` (xmlrunner XML) or a custom `TestRunner`
  subclass; honor the `.venv` python and the `validate_data` pre-test gate. This is a
  *distinct* adapter, not a pytest flag.
- **Exit criteria:** all four runners produce identical-shape normalized output; each
  has fixture snapshot tests.

## Phase 4 — Build/lint delta engine + baseline state (Feature #2)

**Goal:** return only *new* diagnostics vs. a saved baseline.

- **Baseline store** (`core/baseline.py`): capture/store a diagnostics snapshot keyed by
  project+subproject; scratch state scoped to one edit cycle (not cross-session memory).
  CLI: `winnowdelta baseline capture`.
- **Delta engine**: parse current diagnostics, diff against baseline, emit only
  introduced ones (kills LF→CRLF spam, legacy lint debt, Dependabot notices).
- **Diagnostic adapters:** `tsc` (`tsc -b` / `tsc`), **ESLint** (`--format json`),
  **Prettier** (`--check`). (No Python-lint adapter — out of V1 scope per the spec.)
- **Exit criteria:** introduce one new TS type error / ESLint violation against a
  baseline and see *only* that diagnostic returned.

## Phase 5 — Test-impact running + codegraft pipe (Feature #3)

**Goal:** run only affected tests, with a mandatory full-suite escape hatch.

- Accept an **affected-tests list** (file paths / node IDs) and map it to per-runner
  selection invocations (pytest node IDs, vitest/jest path filters, Django labels).
- Wire the `codegraft.impact_of(changed) ∩ test_paths → winnowdelta` pipe (selection
  stays upstream; this tool only executes).
- **Safety:** `--full` mode and a documented CI gate requirement — heuristic selection
  can miss tests, so full-suite must run before merge.
- **Exit criteria:** changed-file input runs only the relevant subset and reports via
  the Phase 2 path; `--full` runs everything.

## Phase 6 — MCP server surface

**Goal:** expose the same core as MCP tools, mirroring the codegraft model.

- `mcp/server.py`: tools like `run_tests`, `build_lint_delta`, `capture_baseline`,
  `impact_run` — thin wrappers over the core, returning the structured JSON.
- Stdio server + registration docs.
- **Exit criteria:** an agent can call the tools and get the same filtered deltas as the CLI.

## Phase 7 — Hardening & release

**Goal:** production-ready for daily use across codegraft, oracle-rex, meshimate.

- **Flakiness/env handling:** clear errors for missing toolchain, partial output,
  non-zero-but-no-failures, optional retry.
- Monorepo multi-root validated against a real oracle-rex-shaped config; meshimate
  Expo/Jest validated.
- Token-savings measurement, `winnowdelta.toml` reference, per-adapter docs,
  packaging/version tag.
- **Exit criteria:** runs clean on all three real projects; output schema documented
  and frozen at v1.

---

## Deferred past V1 (per spec)

`go test`; any Python-lint delta (ruff/flake8); Expo "build".

## Sequencing notes

- Phases 2→3 and the adapters within them are independently parallelizable once
  Phase 1's protocol lands.
- Phase 4 is independent of Phase 3 (could overlap), but both depend on Phase 1's
  runner/config.
- Phase 6 (MCP) intentionally comes after the CLI core is stable so both surfaces
  share one tested implementation.
