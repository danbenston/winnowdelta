"""Phase 4: diagnostic parsers (pure)."""

from __future__ import annotations

import json

import pytest

from winnowdelta.core import diagnostics


def test_parse_tsc() -> None:
    text = (
        "src/app.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        "src/util.ts(3,10): warning TS6133: 'x' is declared but never used.\n"
        "Found 2 errors.\n"
    )
    diags = diagnostics.parse_tsc(text)
    assert len(diags) == 2
    first = diags[0]
    assert first.file == "src/app.ts"
    assert (first.line, first.col) == (12, 5)
    assert first.rule == "TS2322"
    assert first.severity == "error"
    assert "not assignable" in first.message
    assert diags[1].severity == "warning"


def test_parse_eslint_json() -> None:
    payload = json.dumps(
        [
            {
                "filePath": "/proj/src/a.ts",
                "messages": [
                    {"ruleId": "no-unused-vars", "severity": 2, "message": "x unused",
                     "line": 4, "column": 7},
                    {"ruleId": "eqeqeq", "severity": 1, "message": "use ===",
                     "line": 9, "column": 1},
                ],
            },
            {"filePath": "/proj/src/clean.ts", "messages": []},
        ]
    )
    diags = diagnostics.parse_eslint_json(payload)
    assert len(diags) == 2
    assert diags[0].severity == "error" and diags[0].rule == "no-unused-vars"
    assert diags[1].severity == "warning" and diags[1].line == 9


def test_parse_eslint_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        diagnostics.parse_eslint_json("not json")


def test_parse_prettier_list() -> None:
    text = "src/a.ts\nsrc/b.tsx\n\n"
    diags = diagnostics.parse_prettier_list(text)
    assert [d.file for d in diags] == ["src/a.ts", "src/b.tsx"]
    assert all(d.rule == "prettier" and d.severity == "warning" for d in diags)
