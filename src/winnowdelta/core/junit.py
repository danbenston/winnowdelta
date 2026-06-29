"""JUnit XML parser → NormalizedRun.

Pure and producer-agnostic, so it is fully snapshot-testable without spawning a
test runner. Shared by the pytest adapter (built-in ``--junitxml``) and, in
Phase 3, the Django adapter (``unittest-xml-reporting``).

pytest's JUnit XML does not put ``file``/``line`` on ``<testcase>``; the crash
location lives in the failure body's trailing ``path:line: Exception`` line, and
the short assertion is in the failure ``message`` attribute. We recover both.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from .model import Failure, NormalizedRun, Status, Summary

# Trailing crash line, e.g. ``D:\proj\test_x.py:7: AssertionError``. Non-greedy
# file segment with a digit-anchored line number tolerates the drive-letter
# colon on Windows paths. We take the LAST match (the actual crash site).
_CRASH_LINE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): ", re.MULTILINE)

# pytest assertion rewrite short form: ``assert <received> == <expected>``.
_ASSERT_EQ = re.compile(r"^assert (?P<received>.+?) == (?P<expected>.+)$")


def _crash_location(text: str | None) -> tuple[str | None, int | None]:
    if not text:
        return None, None
    matches = list(_CRASH_LINE.finditer(text))
    if not matches:
        return None, None
    last = matches[-1]
    return last.group("file"), int(last.group("line"))


def _expected_received(message: str) -> tuple[str | None, str | None]:
    m = _ASSERT_EQ.match(message.strip())
    if not m:
        return None, None
    return m.group("expected"), m.group("received")


def _relativize(path: str | None, base: Path | None) -> str | None:
    if path is None or base is None:
        return path
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except (ValueError, OSError):
        return path


def _test_id(case: ET.Element) -> str:
    name = case.get("name", "<unknown>")
    classname = case.get("classname") or ""
    return f"{classname}::{name}" if classname else name


def parse_junit_xml(
    xml_text: str,
    command: str = "test",
    *,
    base: Path | None = None,
    duration_s: float = 0.0,
) -> NormalizedRun:
    """Parse JUnit XML into a NormalizedRun, keeping only failures/errors.

    *base*, when given, relativizes crash-location file paths to it.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return NormalizedRun.errored(command, f"could not parse JUnit XML: {exc}")

    failures: list[Failure] = []
    passed = skipped = 0

    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            if case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1
            continue

        message = (problem.get("message") or "").strip()
        file_path, line = _crash_location(problem.text)
        expected, received = _expected_received(message)
        failures.append(
            Failure(
                test_id=_test_id(case),
                file=_relativize(file_path, base),
                line=line,
                message=message,
                expected=expected,
                received=received,
            )
        )

    failed = len(failures)
    summary = Summary(
        total=failed + passed + skipped,
        passed=passed,
        failed=failed,
        skipped=skipped,
    )
    status = Status.FAILED if failed else Status.OK
    return NormalizedRun(
        command=command,
        status=status,
        failures=failures,
        summary=summary,
        duration_s=duration_s,
    )
