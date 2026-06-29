# Output schema (v1)

Every command emits one JSON envelope. `schema_version` is `"1.0"` and is frozen
for v1 — it only changes on an incompatible change. The same envelope is
returned by the CLI (stdout) and the MCP tools.

```jsonc
{
  "schema_version": "1.0",
  "command": "test",          // "test" | "lint" | "build" | "check" | "baseline"
  "status": "failed",         // "ok" | "failed" | "error"
  "summary": {                // coarse counts; zeros for non-test commands
    "total": 4,
    "passed": 1,
    "failed": 2,
    "skipped": 1
  },
  "failures": [               // test failures only (no passing tests)
    {
      "test_id": "test_sample::test_fails_equality",
      "file": "test_sample.py",   // relative to cwd; may be null
      "line": 7,                  // may be null
      "message": "assert 2 == 3",
      "expected": "3",            // best-effort; may be null
      "received": "2"             // best-effort; may be null
    }
  ],
  "diagnostics": [            // build/lint diagnostics (check), new-vs-baseline
    {
      "file": "src/app.ts",
      "severity": "error",        // "error" | "warning"
      "message": "Type 'x' is not assignable to type 'y'.",
      "line": 12,                 // may be null
      "col": 5,                   // may be null
      "rule": "TS2322"            // may be null
    }
  ],
  "duration_s": 0.313,
  "error": null               // populated only when status == "error"
}
```

## Status semantics

- **`ok`** — the command ran and found nothing to report (no failures / no new
  diagnostics).
- **`failed`** — the command ran and reported failures or new diagnostics. This
  is "your code has a problem."
- **`error`** — winnowdelta could not run or parse the command (missing
  toolchain, timeout, unparseable output, unknown subproject). This is "I
  couldn't do my job," and is kept distinct from `failed` on purpose.

## Process exit codes (CLI)

`0` = ok · `1` = failed (failures/diagnostics found) · `2` = error.
