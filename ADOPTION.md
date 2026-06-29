# Adoption plan — getting winnowdelta used in Claude Code sessions

The tool is built and validated, but a fresh session won't use it until it's
(a) on `PATH`, (b) something instructs the agent to prefer it, and (c) optionally
wired in as an MCP tool. These steps are ordered; each is independent enough to
do on its own, but later steps assume the install in Step 1.

Paths below assume the repo at `D:\Development\PycharmProjects\winnowdelta`.

---

## Step 1 — Install globally so it's on PATH everywhere

Editable pipx install with the MCP extra, so `winnowdelta` and `winnowdelta-mcp`
are available in every project (not just this dev venv) and track the repo as it
changes.

```powershell
pipx install --editable "D:\Development\PycharmProjects\winnowdelta[mcp]"
```

**Verify:**
```powershell
winnowdelta --version          # -> winnowdelta 0.1.0
where.exe winnowdelta-mcp       # resolves to a pipx shim
```

If `pipx` isn't installed: `python -m pip install --user pipx; python -m pipx ensurepath`
(then reopen the shell).

---

## Step 2 — Register the MCP server with Claude Code (user scope)

Makes `run_tests`, `build_lint_delta`, `capture_baseline`, `clear_baseline`
first-class tools the agent can call directly, with structured results instead
of parsed Bash output. The server defaults `root` to the session's working
directory, so it works per-project with no extra config.

```powershell
claude mcp add winnowdelta --scope user -- winnowdelta-mcp
```

**Verify:** `claude mcp list` shows `winnowdelta`; in a new session the tools
appear as `mcp__winnowdelta__run_tests`, etc.

> CLI vs MCP: both surfaces share one engine and emit the identical envelope.
> The MCP route is preferred inside Claude Code (structured tool results); the
> CLI route via Bash is the fallback and is what CI uses.

---

## Step 3 — Tell sessions to prefer it (CLAUDE.md guidance) — highest impact

Add a block to the **global** `C:\Users\Dan\.claude\CLAUDE.md`, parallel to the
existing codegraft read-side block. This is what actually changes agent behavior
session to session.

Proposed text:

```markdown
## winnowdelta — run-and-filter feedback tool

When you run a project's tests / build / lint to verify a change, prefer
winnowdelta over the raw runner — it returns only the structured delta
(failures, new-vs-baseline diagnostics) instead of verbose console output.

- Verifying a change → `winnowdelta test` (only failures with file:line +
  assertion) and `winnowdelta check` (only diagnostics new vs a captured
  baseline). Capture the baseline with `winnowdelta baseline capture` *before*
  editing so `check` shows just what you introduced.
- Fast inner loop → it consumes codegraft's selection: the pipe is
  `codegraft.impact_of(changed) ∩ test_paths → winnowdelta test --tests-from -`.
  This is an accelerator, not a gate: run `winnowdelta test --full` before merge.
- It runs and reads; it never edits code and never selects which files matter
  (that's codegraft). Supported V1 stacks: pytest · Django · Vitest · Jest;
  tsc · ESLint · Prettier for build/lint deltas.
- If a stack/tool isn't covered, fall back to the raw runner.
```

**Verify:** start a fresh session and ask it to run the tests in a pytest repo;
it should invoke `winnowdelta test`.

---

## Step 4 — Per-project config for oracle-rex (multi-root)

oracle-rex is a two-root monorepo; a `winnowdelta.toml` at its root removes
autodetect ambiguity and encodes the Django app-label workaround (its root
`__init__.py` + hyphenated dir name breaks stock Django discovery).

Write `D:\Development\PycharmProjects\oracle-rex\winnowdelta.toml`:

```toml
[subproject.backend]
stack = "django"
cwd   = "."
test  = ".venv/Scripts/python.exe manage.py test core"

[subproject.frontend]
stack = "vitest"
cwd   = "frontend"
tools = ["eslint", "prettier", "tsc"]
```

**Verify (in oracle-rex):**
```powershell
winnowdelta test frontend
winnowdelta check frontend --kind lint --all
```

(Adjust the Django `test` app label(s) to match where backend tests actually live.)

---

## Step 5 — Permission allowlist (stop the prompts)

Add to `C:\Users\Dan\.claude\settings.json` under `permissions.allow` so it runs
without prompting:

```json
{
  "permissions": {
    "allow": [
      "Bash(winnowdelta:*)",
      "mcp__winnowdelta__run_tests",
      "mcp__winnowdelta__build_lint_delta",
      "mcp__winnowdelta__capture_baseline",
      "mcp__winnowdelta__clear_baseline"
    ]
  }
}
```

(The `/update-config` skill can apply this safely if you'd rather not hand-edit.)

---

## Optional / later

- **meshimate (Jest/jest-expo)** — the only V1 stack with no live validation yet.
  Run `winnowdelta test` in that repo once to confirm the jest-expo preset parses;
  the JSON parser is shared with the live-tested Vitest path.
- **Publish** — if you want it on other machines without the local checkout,
  build a wheel (`python -m build`) and `pipx install` the artifact.
- **CI gate** — wire `winnowdelta test --full` into each repo's CI so the fast
  selection loop never replaces a full pre-merge run.

## Suggested order

1 (install) → 3 (CLAUDE.md, the behavior change) → 2 (MCP) → 5 (permissions) →
4 (oracle-rex config). Steps 3 and 4 are the ones that touch files outside this
repo; the rest are local/global tooling.
