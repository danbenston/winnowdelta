# Configuration — `winnowdelta.toml`

winnowdelta runs with **zero config** in a single-stack repo: it autodetects the
test runner (pytest / Vitest / Jest / Django) and the diagnostic tools (tsc /
ESLint / Prettier) by sniffing the directory. A `winnowdelta.toml` at the repo
root is needed only for multi-root monorepos or to override commands.

## Subprojects

Each `[subproject.<name>]` table declares one runnable unit:

| Key | Meaning | Default |
|---|---|---|
| `stack` | Test runner: `pytest` \| `django` \| `vitest` \| `jest` | — (required) |
| `cwd` | Working directory, relative to the repo root | `"."` |
| `test` / `lint` / `build` | Override the command for that kind (string or list) | autodetected |
| `tools` | Explicit diagnostic tools, e.g. `["eslint","prettier","tsc"]` | autodetected from `cwd` |

Commands are a TOML string (shlex-split, backslashes preserved) or a list
(preferred for paths with spaces):

```toml
test  = ".venv/Scripts/python.exe manage.py test"   # string
build = ["tsc", "-b"]                                # list
```

When a single subproject is configured (or autodetected), commands that take a
`subproject` argument may omit it.

## Multi-root example (oracle-rex)

A two-root monorepo: a Django backend at the root and a Vite/React frontend
under `frontend/`.

```toml
[subproject.backend]
stack = "django"
cwd   = "."
# Must be the test PACKAGE label `core.tests`, not the app label `core` — see
# "Known quirk" below: `manage.py test core` ALSO fails discovery on this repo.
test  = [".venv/Scripts/python.exe", "manage.py", "test", "core.tests"]

[subproject.frontend]
stack = "vitest"
cwd   = "frontend"
tools = ["eslint", "prettier", "tsc"]
```

Run a specific subproject:

```sh
winnowdelta test backend
winnowdelta check frontend --kind lint
```

## TypeScript project references (composite builds)

The `tsc` adapter sniffs the subproject's `tsconfig.json`. If it declares a
non-empty `references` array or `compilerOptions.composite = true`, the adapter
runs `tsc -b` (build mode, which follows the reference graph) instead of the
default `tsc --noEmit`. This is automatic — no config needed.

Why it matters: plain `tsc --noEmit` ignores project references, so against a
solution-style root (`"files": []` + `"references": [...]`) it type-checks
nothing and reports a false-clean. Build mode is portable across TypeScript
versions but emits `.tsbuildinfo` + declarations as a side effect. To customize
(e.g. add `--noEmit`, supported in build mode on TypeScript >= 5.6), set an
explicit `build` command, which always wins over detection:

```toml
[subproject.web]
stack = "vitest"
build = ["npx", "tsc", "-b", "--noEmit", "--pretty", "false"]
```

## Invocation quirks handled for you

- **Windows node shims** — `npm`/`npx`/`yarn`/`pnpm` are `.cmd` files; winnowdelta
  routes them through `ComSpec` (`cmd.exe /c npm.cmd …`) so they run on Windows.
- **Project venv** — when a subproject has a `.venv`, its Python is used for
  pytest/Django invocations.
- **Per-subproject cwd** — every command runs in its own `cwd`; no single-root
  assumption.

## Known quirk: Django test discovery

Django's `manage.py test` auto-discovery walks **up** from the start directory
while a package (`__init__.py`) is present. If your repo root has an
`__init__.py` *and* a non-identifier directory name (e.g. a hyphen, as in
`oracle-rex`), discovery builds an invalid module path and fails to import —
this happens with the stock runner too, not just winnowdelta.

Work around it by giving `test` an explicit label that points **into** the test
package. On oracle-rex (verified 2026-07-03):

| Command | Result |
|---|---|
| `manage.py test` (adapter default) | ❌ `ModuleNotFoundError: No module named 'oracle-rex.core'` |
| `manage.py test core` (app label) | ❌ same discovery failure — climbing past the root still trips the hyphen |
| `manage.py test core.tests` (package label) | ✅ runs all 145 tests |

So the app label alone is **not** enough here; use the deeper `core.tests`. The
adapter's zero-config default (bare `manage.py test`) cannot run this repo — an
explicit `test` in `winnowdelta.toml` is required, not just recommended. See
[known-issues.md](known-issues.md) for the related MCP-server hang.
