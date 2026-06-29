"""Phase 1: normalized model + output emitter."""

from __future__ import annotations

import json

from winnowdelta.core import output
from winnowdelta.core.model import Diagnostic, Failure, NormalizedRun, Status, Summary


def test_empty_run_envelope() -> None:
    env = output.to_envelope(NormalizedRun.empty("test"))
    assert env["schema_version"] == output.SCHEMA_VERSION
    assert env["command"] == "test"
    assert env["status"] == "ok"
    assert env["failures"] == []
    assert env["diagnostics"] == []


def test_failure_envelope_roundtrips_json() -> None:
    run = NormalizedRun(
        command="test",
        status=Status.FAILED,
        failures=[
            Failure(
                test_id="tests/test_x.py::test_add",
                file="tests/test_x.py",
                line=12,
                message="assert 3 == 4",
                expected="4",
                received="3",
            )
        ],
        summary=Summary(total=2, passed=1, failed=1),
        duration_s=0.123456,
    )
    payload = json.loads(output.to_json(run))
    assert payload["status"] == "failed"
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 1, "skipped": 0}
    assert payload["duration_s"] == 0.123
    assert payload["failures"][0]["test_id"] == "tests/test_x.py::test_add"
    assert payload["failures"][0]["line"] == 12


def test_text_render_failure() -> None:
    run = NormalizedRun(
        command="test",
        status=Status.FAILED,
        failures=[Failure(test_id="t::a", file="t.py", line=5, message="boom")],
        summary=Summary(total=1, failed=1),
    )
    text = output.to_text(run)
    assert "FAIL t::a" in text
    assert "t.py:5" in text
    assert "1 failed, 0 passed" in text


def test_text_render_diagnostic() -> None:
    run = NormalizedRun(
        command="lint",
        status=Status.FAILED,
        diagnostics=[
            Diagnostic(file="a.ts", line=3, col=7, rule="no-unused", severity="error",
                       message="x is unused")
        ],
    )
    text = output.to_text(run)
    assert "ERROR a.ts:3:7" in text
    assert "[no-unused]" in text


def test_text_render_error_status() -> None:
    run = NormalizedRun.errored("test", "pytest not found")
    assert output.to_text(run) == "ERROR (test): pytest not found"
    assert output.to_envelope(run)["error"] == "pytest not found"
