"""Phase 3: Django JUnit runner internals (stdlib only, no Django needed).

Exercises the result collector against a real unittest run and the XML builder,
then round-trips through the shared core.junit parser to confirm the
file/line-attribute path works end to end.
"""

from __future__ import annotations

import io
import unittest

from winnowdelta import django_runner
from winnowdelta.core import junit
from winnowdelta.core.model import Status


class _Sample(unittest.TestCase):
    # Prevent pytest from collecting this fixture TestCase as real tests; it is
    # a sample we run by hand through the JUnitResult collector.
    __test__ = False

    def test_ok(self) -> None:
        self.assertEqual(1 + 1, 2)

    def test_bad(self) -> None:
        self.assertEqual(1 + 1, 3)

    def test_boom(self) -> None:
        raise RuntimeError("kaboom")

    @unittest.skip("nope")
    def test_skip(self) -> None:  # pragma: no cover - skipped
        pass


def _run_sample() -> django_runner.JUnitResult:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(_Sample)
    runner = unittest.TextTestRunner(
        resultclass=django_runner.JUnitResult, stream=io.StringIO()
    )
    return runner.run(suite)  # type: ignore[return-value]


def test_result_collects_all_outcomes() -> None:
    result = _run_sample()
    by_status: dict[str, int] = {}
    for rec in result.records:
        by_status[rec.status] = by_status.get(rec.status, 0) + 1
    assert by_status.get("passed") == 1
    assert by_status.get("failed") == 1
    assert by_status.get("error") == 1
    assert by_status.get("skipped") == 1


def test_records_carry_source_location() -> None:
    result = _run_sample()
    bad = next(r for r in result.records if r.name == "test_bad")
    assert bad.file is not None and bad.file.endswith("test_django_runner.py")
    assert isinstance(bad.line, int)


def test_xml_roundtrips_through_junit_parser() -> None:
    result = _run_sample()
    xml = django_runner.build_junit_xml(result.records)
    run = junit.parse_junit_xml(xml, command="test")

    assert run.status is Status.FAILED
    assert run.summary.passed == 1
    assert run.summary.skipped == 1
    assert run.summary.failed == 2  # failure + error

    failing = {f.test_id.split("::")[-1] for f in run.failures}
    assert failing == {"test_bad", "test_boom"}
    # file/line attributes set by the builder survive the parser.
    bad = next(f for f in run.failures if f.test_id.endswith("test_bad"))
    assert bad.file is not None and bad.file.endswith("test_django_runner.py")
    assert bad.line is not None
