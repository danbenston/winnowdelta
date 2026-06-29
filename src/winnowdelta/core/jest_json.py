"""Jest/Vitest JSON test-result parser.

Vitest copied Jest's ``--json`` schema, so one parser serves both: a top-level
object with per-file ``testResults``, each holding ``assertionResults`` with a
``status`` and ``failureMessages``. Neither reliably populates ``location`` for
failures (Vitest leaves it null), so ``file:line`` is recovered from the failure
message's stack frame; expected/received are pulled from the matcher diff in a
way tolerant of both Jest (``Expected:``/``Received:``) and Vitest
(``expected X to be Y``) phrasings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .model import Failure, NormalizedRun, Status, Summary

_SKIPPED = {"pending", "skipped", "todo", "disabled"}

# A `file:line:col` reference inside a stack frame (jest: "(path:1:2)";
# vitest: "❯ path:1:2"). Restricted to JS/TS source extensions.
_STACK_LOC = re.compile(r"([^\s()]+\.(?:tsx?|jsx?|mjs|cjs)):(\d+):(\d+)")

_JEST_EXPECTED = re.compile(r"^\s*Expected:?\s*(.+?)\s*$", re.MULTILINE)
_JEST_RECEIVED = re.compile(r"^\s*Received:?\s*(.+?)\s*$", re.MULTILINE)
# vitest: "expected 2 to be 3", "expected 'a' to equal 'b'"
_VITEST_EQ = re.compile(r"expected (.+?) to (?:be|equal|deeply equal|strictly equal) (.+)")


def _test_id(assertion: dict[str, object]) -> str:
    full = assertion.get("fullName")
    if isinstance(full, str) and full:
        return full
    parts: list[str] = []
    ancestors = assertion.get("ancestorTitles")
    if isinstance(ancestors, list):
        parts.extend(str(p) for p in ancestors)
    title = assertion.get("title")
    if isinstance(title, str):
        parts.append(title)
    return " > ".join(parts) if parts else "<unknown>"


def _relativize(path: str, base: Path | None) -> str:
    if base is None:
        return path
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except (ValueError, OSError):
        return path


def _location(
    assertion: dict[str, object], test_file: str | None, blob: str, base: Path | None
) -> tuple[str | None, int | None]:
    loc = assertion.get("location")
    if isinstance(loc, dict) and test_file:
        ln = loc.get("line")
        if isinstance(ln, int):
            return _relativize(test_file, base), ln

    matches = _STACK_LOC.findall(blob)
    if not matches:
        return (_relativize(test_file, base) if test_file else None), None
    # Prefer the frame in the test file itself; otherwise the first frame.
    chosen = matches[0]
    if test_file:
        stem = Path(test_file).name
        for m in matches:
            if Path(m[0]).name == stem:
                chosen = m
                break
    return _relativize(chosen[0], base), int(chosen[1])


def _expected_received(blob: str) -> tuple[str | None, str | None]:
    exp = _JEST_EXPECTED.search(blob)
    rec = _JEST_RECEIVED.search(blob)
    if exp and rec:
        return exp.group(1), rec.group(1)
    vi = _VITEST_EQ.search(blob)
    if vi:
        return vi.group(2), vi.group(1)  # "expected <received> to be <expected>"
    return None, None


def _first_line(blob: str) -> str:
    for line in blob.splitlines():
        stripped = line.strip()
        if stripped:
            return re.sub(r"^(?:Error|AssertionError):\s*", "", stripped)
    return ""


def parse_jest_json(
    text: str,
    command: str = "test",
    *,
    base: Path | None = None,
    duration_s: float = 0.0,
) -> NormalizedRun:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return NormalizedRun.errored(command, f"could not parse JSON report: {exc}")

    failures: list[Failure] = []
    passed = skipped = 0

    results = data.get("testResults", []) if isinstance(data, dict) else []
    for tr in results:
        if not isinstance(tr, dict):
            continue
        name = tr.get("name")
        test_file = name if isinstance(name, str) else None
        for assertion in tr.get("assertionResults", []):
            if not isinstance(assertion, dict):
                continue
            status = assertion.get("status")
            if status == "passed":
                passed += 1
                continue
            if status in _SKIPPED:
                skipped += 1
                continue

            blob = "\n".join(assertion.get("failureMessages") or [])
            file_path, line = _location(assertion, test_file, blob, base)
            expected, received = _expected_received(blob)
            failures.append(
                Failure(
                    test_id=_test_id(assertion),
                    file=file_path,
                    line=line,
                    message=_first_line(blob) or _test_id(assertion),
                    expected=expected,
                    received=received,
                )
            )

    failed = len(failures)
    summary = Summary(total=failed + passed + skipped, passed=passed, failed=failed,
                      skipped=skipped)
    status = Status.FAILED if failed else Status.OK
    return NormalizedRun(
        command=command,
        status=status,
        failures=failures,
        summary=summary,
        duration_s=duration_s,
    )
