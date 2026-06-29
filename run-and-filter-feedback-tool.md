# Tool concept: run-and-filter feedback tool (new repo)

> **Scope.** A standalone CLI/MCP tool that *executes* a project's test, build, and
> lint commands and returns only the **structured, filtered delta** — the
> failures and the new-vs-baseline diagnostics — instead of the raw, verbose
> console output. Its whole reason to exist is to collapse thousands of tokens of
> rendered DOM trees, stack traces, and pre-existing-warning spam into the minimal
> machine-actionable signal a coding agent needs to decide what to fix next.
>
> It **runs and reads**; it never edits code and never *selects* which files
> matter (that's codegraft). It is the highest-ROI feedback tool observed in the
> field, which is exactly why it deserves to be its own well-built thing rather
> than a bolt-on.

**Status: concept (2026-06-16).** Surfaced from oracle-rex loop friction. Bundles
field proposals #4, #7, and the *execution* half of #5.

## Why it is not codegraft

It violates the codegraft line on every axis: it **executes the project** (needs
the test runner, build system, linter, and toolchain present), it **keeps a
baseline state** to diff against, and its failure surface is flakiness and
environment setup — not ranking. Folding it into codegraft would destroy
codegraft's defining property ("everything except one LLM call is testable without
a model, with no per-request cost"). Clean boundary instead: this tool *consumes*
codegraft's `impact_of` test selection, then runs it.

## Features

### 1. Structured test reporter (#4) — the headline

Run the suite through its **machine reporter** (not human console output) and
return only what failed.

- **Input:** the project's test command (or an autodetected default).
- **Mechanism:** invoke via each framework's JSON/structured reporter
  (`pytest --json`/`pytest-reportlog`, `jest`/`vitest --reporter=json`, `go test
  -json`, …) behind per-framework adapters.
- **Output:** per failure — test name, `file:line`, expected vs. received, and the
  single relevant assertion message. No passing tests, no rendered-DOM dumps, no
  framework banner.
- **Win:** cuts thousands of tokens and a grep-the-output round-trip per failed
  run.

### 2. Filtered build / lint deltas (#7)

Return only **new** diagnostics relative to a saved baseline.

- **Mechanism:** run the build/linter, parse diagnostics, diff against a baseline
  snapshot captured before the agent's edits.
- **Output:** only diagnostics introduced by the current change set — so the agent
  never re-reads a wall of pre-existing warnings (LF→CRLF spam, Dependabot
  notices, legacy lint debt).
- **State note:** the baseline is this tool's own state; it is *not* cross-session
  project memory in the codegraft-forbidden sense — it's a scratch snapshot scoped
  to one edit cycle.

### 3. Test-impact running (#5, execution half)

Consume an **affected-tests list** (e.g. from codegraft's `impact_of(changed) ∩
test_paths`) and run only those, then report via feature #1.

- **Boundary:** *selection* is upstream (codegraft); this tool only executes.
- **Safety:** because selection is heuristic and can miss tests, this is a
  fast-inner-loop accelerator — it must offer (and a CI gate must use) a
  full-suite mode before merge.

## V1 scope — adapters for languages we currently use

Scoped (2026-06-28) to the stacks actually in play across the current projects —
**codegraft**, **oracle-rex** (a two-root monorepo), and **meshimate**. Two
languages (Python, TypeScript), but four test runners and three lint/build tools,
because oracle-rex carries a Django backend *and* a Vite frontend.

| Repo | Stack | Test runner | Lint / format | Build / typecheck |
|---|---|---|---|---|
| codegraft | Python | pytest | ruff | — (library) |
| oracle-rex (root) | Python / Django | Django test runner (`manage.py test`, unittest) | — | `manage.py validate_data` gate |
| oracle-rex `/frontend` | TS / React (Vite) | Vitest (`vitest run`) | ESLint + Prettier | `tsc -b` + vite build |
| meshimate | TS / React Native (Expo) | Jest (`jest-expo` preset) | — | `tsc` |

**Test reporter adapters (Feature #1):** pytest · **Django/unittest** · Vitest · Jest.

- pytest, Vitest, and Jest all expose native machine reporters
  (`pytest --json`/`pytest-reportlog`, `vitest --reporter=json`, `jest --json`).
- **Django is the exception and the biggest under-scope in the original concept:**
  `manage.py test` runs plain unittest with *no* built-in structured reporter. V1
  builds a real adapter via `unittest-xml-reporting` (xmlrunner XML) — or a custom
  `TestRunner` subclass — so oracle-rex's backend (where most test churn lives) gets
  the same `file:line` + assertion compression as the rest. This is a distinct
  adapter, not a flag on the pytest one.

**Build / lint delta adapters (Feature #2):** ESLint · Prettier · tsc.

- No Python linter is wired into any repo's CI today (ruff exists in codegraft's
  dev deps but isn't a pipeline gate), so a Python-lint delta adapter is **out of
  v1 scope** by the "languages we currently use" rule — defer with go test.

**Invocation quirks the runner must handle from day one:**

- **Multi-root monorepo (oracle-rex):** Django at the repo root, JS under
  `frontend/`. Adapters must take a per-subproject `cwd` + command, not assume one
  root (CI uses `working-directory: frontend`).
- **Windows npm shim:** invoke JS tooling through `npm.cmd` (via `ComSpec`), not
  bare `npm` — the bare shim is a Unix file and fails on Windows (see oracle-rex
  `dev.ps1`). This tool is developed/run on Windows.
- **Project venv (oracle-rex backend):** test invocation uses
  `.venv\Scripts\python.exe manage.py test`, plus a `validate_data` management
  command that behaves like a pre-test gate.

**Deferred past v1:** go test; any Python-lint delta (ruff/flake8); Expo "build".

## Boundaries — what this tool does NOT do

- It does not pick which files are relevant to a request (codegraft).
- It does not edit code or apply fixes.
- It does not resolve symbols / references / types (the code-intelligence bridge).
- It does not summarize git diffs for review (`/code-review`).

## Relationship to codegraft

Adjacent and complementary. codegraft narrows *what to look at*; this tool
compresses *what happened when you ran it*. The natural pipe is
`codegraft.impact_of → this.test-impact-run → this.structured-report`.
