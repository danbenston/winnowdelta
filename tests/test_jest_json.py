"""Phase 3: shared Jest/Vitest JSON parser (pure)."""

from __future__ import annotations

import json

from winnowdelta.core import jest_json
from winnowdelta.core.model import Status


def _doc(*test_results: dict) -> str:
    return json.dumps({"testResults": list(test_results)})


def test_jest_style_failure() -> None:
    blob = (
        "Error: expect(received).toBe(expected) // Object.is equality\n\n"
        "Expected: 3\nReceived: 2\n"
        "    at Object.<anonymous> (/abs/src/math.test.ts:5:20)\n"
    )
    doc = _doc(
        {
            "name": "/abs/src/math.test.ts",
            "assertionResults": [
                {"status": "passed", "fullName": "math adds"},
                {
                    "status": "failed",
                    "fullName": "math subtracts wrong",
                    "failureMessages": [blob],
                    "location": None,
                },
            ],
        }
    )
    run = jest_json.parse_jest_json(doc)
    assert run.status is Status.FAILED
    assert run.summary.passed == 1
    assert run.summary.failed == 1

    f = run.failures[0]
    assert f.test_id == "math subtracts wrong"
    assert f.file == "/abs/src/math.test.ts"
    assert f.line == 5
    assert f.expected == "3"
    assert f.received == "2"
    assert "toBe" in f.message


def test_vitest_style_failure_phrasing() -> None:
    blob = "AssertionError: expected 2 to be 3\n ❯ src/calc.test.ts:11:8\n"
    doc = _doc(
        {
            "name": "/abs/src/calc.test.ts",
            "assertionResults": [
                {
                    "status": "failed",
                    "ancestorTitles": ["calc"],
                    "title": "computes",
                    "failureMessages": [blob],
                }
            ],
        }
    )
    run = jest_json.parse_jest_json(doc)
    f = run.failures[0]
    assert f.test_id == "calc > computes"
    assert f.file == "src/calc.test.ts"
    assert f.line == 11
    assert f.received == "2"
    assert f.expected == "3"


def test_skipped_counted_not_failed() -> None:
    doc = _doc(
        {
            "name": "x.test.ts",
            "assertionResults": [
                {"status": "passed", "title": "a"},
                {"status": "pending", "title": "b"},
                {"status": "todo", "title": "c"},
            ],
        }
    )
    run = jest_json.parse_jest_json(doc)
    assert run.status is Status.OK
    assert run.summary.passed == 1
    assert run.summary.skipped == 2
    assert run.failures == []


def test_relativizes_to_base(tmp_path) -> None:
    test_file = tmp_path / "src" / "a.test.ts"
    blob = f"Error: boom\n at ({test_file}:9:1)\n"
    doc = _doc(
        {
            "name": str(test_file),
            "assertionResults": [
                {"status": "failed", "title": "t", "failureMessages": [blob]}
            ],
        }
    )
    run = jest_json.parse_jest_json(doc, base=tmp_path)
    assert run.failures[0].file == str(tmp_path.joinpath("src", "a.test.ts").relative_to(tmp_path))
    assert run.failures[0].line == 9


def test_malformed_json_is_error() -> None:
    run = jest_json.parse_jest_json("{not json")
    assert run.status is Status.ERROR
    assert run.error is not None
