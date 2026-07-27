# Changelog

## Unreleased

Code-review pass. No change to the `1.0` JSON envelope shape.

**Fixed — output was wrong or misleading**

- A corrupt or schema-drifted baseline file crashed the engine instead of
  degrading to "no baseline", tracebacking out of the CLI (exit 1, not the
  documented 2) and the MCP server. Baselines are now written atomically, so an
  interrupted capture can no longer create that corruption.
- Error diagnosis preferred stderr over stdout, so a missing toolchain reported
  npm's changelog notice instead of the cause. It now prefers stdout, drops
  `npm notice`/`npm warn` chatter, strips ANSI escapes that were leaking into
  the JSON, and always includes the exit code.
- The Django adapter put winnowdelta's parent directory (site-packages, under a
  normal pip install) on the target's `PYTHONPATH`, which could shadow the
  project's own dependencies. It now stages a standalone copy of the JUnit
  runner and exposes only that.
- `duration_s` was always `0.0` on `check` and `baseline` — per-tool timings
  were discarded rather than summed.
- An unhandled error in the CLI (e.g. an unreadable `--tests-from` file)
  tracebacked out with exit 1 instead of an ERROR envelope and exit 2.
- `baseline clear` printed "no baseline to clear" and exited 0 when the config
  could not be resolved. The MCP `clear_baseline` result gained an `error` key
  to tell the two apart.
- `--text` dropped the `error` caveat on a FAILED check, so a tree where one
  tool broke looked fully checked.
- `checked` was lost whenever a check ended in ERROR, discarding the record of
  tools that had already run cleanly.
- Two subproject names that sanitize alike (`api/web`, `api_web`) shared one
  baseline file, each seeing the other's diagnostics as newly introduced.
- After a timeout kill, `run` waited unbounded for the process to die, which
  could reintroduce the hang the timeout exists to prevent.

**Changed**

- `--only` is now repeatable (`--only a --only b`) instead of variadic. As
  `nargs="+"` it silently swallowed the trailing `subproject` positional:
  `test --only a::b backend` ran the default subproject with `backend` treated
  as a test ID.
- Unknown keys in a `[subproject.*]` table are rejected instead of ignored, and
  `stack` is required and must be non-empty. A typo like `tool = [...]` for
  `tools = [...]` previously produced a silent "no tools ran".
- Diagnostic commands can be overridden per tool (`eslint = [...]`,
  `prettier = [...]`, `tsc = [...]`), which wins over the kind key. A kind key
  applies to every tool of that kind, so `lint` alone could not target one of
  eslint/prettier — and prettier ignored configuration entirely.

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
