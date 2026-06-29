"""Phase 2: shared JUnit XML parser (pure, no subprocess)."""

from __future__ import annotations

from winnowdelta.core import junit
from winnowdelta.core.model import Status

# Captured from a real `pytest --junitxml` run (passing, failing-assert,
# erroring, and skipped cases).
SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="2" \
skipped="1" tests="4" time="0.033">
<testcase classname="pkg.test_sample" name="test_passes" time="0.001" />
<testcase classname="pkg.test_sample" name="test_fails_equality" time="0.001">\
<failure message="assert 2 == 3">def test_fails_equality():
        result = 1 + 1
&gt;       assert result == 3
E       assert 2 == 3

D:\\proj\\pkg\\test_sample.py:7: AssertionError</failure></testcase>
<testcase classname="pkg.test_sample" name="test_errors" time="0.000">\
<failure message="RuntimeError: kaboom">def test_errors():
&gt;       raise RuntimeError("kaboom")
E       RuntimeError: kaboom

D:\\proj\\pkg\\test_sample.py:11: RuntimeError</failure></testcase>
<testcase classname="pkg.test_sample" name="test_skipped" time="0.000">\
<skipped type="pytest.skip" message="not today">\
D:\\proj\\pkg\\test_sample.py:17: not today</skipped></testcase>
</testsuite></testsuites>"""


def test_summary_counts() -> None:
    run = junit.parse_junit_xml(SAMPLE)
    assert run.status is Status.FAILED
    assert run.summary.total == 4
    assert run.summary.passed == 1
    assert run.summary.failed == 2
    assert run.summary.skipped == 1


def test_only_failures_kept() -> None:
    run = junit.parse_junit_xml(SAMPLE)
    ids = [f.test_id for f in run.failures]
    assert ids == ["pkg.test_sample::test_fails_equality", "pkg.test_sample::test_errors"]


def test_crash_location_extracted_through_windows_drive_colon() -> None:
    run = junit.parse_junit_xml(SAMPLE)
    f = run.failures[0]
    assert f.file == r"D:\proj\pkg\test_sample.py"
    assert f.line == 7


def test_assertion_expected_received_parsed() -> None:
    run = junit.parse_junit_xml(SAMPLE)
    f = run.failures[0]
    assert f.message == "assert 2 == 3"
    assert f.received == "2"
    assert f.expected == "3"


def test_error_case_has_no_expected_received() -> None:
    run = junit.parse_junit_xml(SAMPLE)
    err = run.failures[1]
    assert err.message == "RuntimeError: kaboom"
    assert err.expected is None and err.received is None


def test_all_pass_is_ok() -> None:
    xml = (
        '<testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="t" name="ok" />'
        "</testsuite>"
    )
    run = junit.parse_junit_xml(xml)
    assert run.status is Status.OK
    assert run.failures == []
    assert run.summary.passed == 1


def test_malformed_xml_is_error_status() -> None:
    run = junit.parse_junit_xml("<not-closed")
    assert run.status is Status.ERROR
    assert run.error is not None
