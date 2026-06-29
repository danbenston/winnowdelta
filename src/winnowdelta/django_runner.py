"""Dependency-free JUnit reporter for Django's test runner.

``manage.py test`` runs plain unittest with no structured reporter, and the
oracle-rex venv does not carry ``unittest-xml-reporting``. So instead of
requiring that package, winnowdelta injects this runner via
``--testrunner=winnowdelta.django_runner.JUnitRunner`` (with this package on
``PYTHONPATH``). It records each test's outcome and source location and writes a
JUnit XML file to the path in ``$WINNOWDELTA_JUNIT`` — which the shared
``core.junit`` parser then reads, honoring the explicit ``file``/``line``
attributes we set here.

The XML builder and the result collector are plain stdlib (unittest), so they
are unit-testable without Django installed. Django is imported lazily; when it
is absent ``JUnitRunner`` degrades to a harmless stub.
"""

from __future__ import annotations

import inspect
import os
import traceback
import unittest
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

ENV_OUTPUT = "WINNOWDELTA_JUNIT"


@dataclass
class CaseResult:
    test_id: str
    classname: str
    name: str
    status: str  # "passed" | "failed" | "error" | "skipped"
    file: str | None = None
    line: int | None = None
    message: str = ""
    text: str = ""


def _test_location(test: unittest.TestCase) -> tuple[str | None, int | None]:
    try:
        method = getattr(type(test), test._testMethodName)
        source = inspect.getsourcefile(method)
        _, line = inspect.getsourcelines(method)
        return source, line
    except (OSError, TypeError, AttributeError):
        return None, None


def _identify(test: unittest.TestCase) -> tuple[str, str, str]:
    cls = type(test)
    classname = f"{cls.__module__}.{cls.__qualname__}"
    name = getattr(test, "_testMethodName", str(test))
    return f"{classname}::{name}", classname, name


def build_junit_xml(cases: list[CaseResult]) -> str:
    """Render collected results as a single JUnit XML document."""
    failures = sum(1 for c in cases if c.status == "failed")
    errors = sum(1 for c in cases if c.status == "error")
    skipped = sum(1 for c in cases if c.status == "skipped")

    suite = ET.Element(
        "testsuite",
        {
            "name": "django",
            "tests": str(len(cases)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
        },
    )
    for case in cases:
        tc = ET.SubElement(
            suite,
            "testcase",
            {"classname": case.classname, "name": case.name},
        )
        if case.file:
            tc.set("file", case.file)
        if case.line is not None:
            tc.set("line", str(case.line))
        if case.status in ("failed", "error"):
            tag = "failure" if case.status == "failed" else "error"
            el = ET.SubElement(tc, tag, {"message": case.message})
            el.text = case.text
        elif case.status == "skipped":
            ET.SubElement(tc, "skipped", {"message": case.message})

    return ET.tostring(suite, encoding="unicode")


class JUnitResult(unittest.TextTestResult):
    """Collects per-test outcomes with source locations."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.records: list[CaseResult] = []

    def _record(
        self,
        test: unittest.TestCase,
        status: str,
        err: object = None,
        message: str = "",
    ) -> None:
        test_id, classname, name = _identify(test)
        file_, line = _test_location(test)
        text = ""
        if err is not None and isinstance(err, tuple):
            exc_type, exc_value, exc_tb = err
            text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            message = str(exc_value) or getattr(exc_type, "__name__", "error")
        self.records.append(
            CaseResult(
                test_id=test_id,
                classname=classname,
                name=name,
                status=status,
                file=file_,
                line=line,
                message=message,
                text=text,
            )
        )

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test: unittest.TestCase, err: object) -> None:
        super().addFailure(test, err)  # type: ignore[arg-type]
        self._record(test, "failed", err)

    def addError(self, test: unittest.TestCase, err: object) -> None:
        super().addError(test, err)  # type: ignore[arg-type]
        self._record(test, "error", err)

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._record(test, "skipped", message=reason)


def _write_report(result: object) -> None:
    path = os.environ.get(ENV_OUTPUT)
    if path and isinstance(result, JUnitResult):
        Path(path).write_text(build_junit_xml(result.records), encoding="utf-8")


try:  # pragma: no cover - exercised only inside a Django project
    import django.test.runner as _dtr  # type: ignore[import-not-found]

    _DiscoverRunner = _dtr.DiscoverRunner

    class JUnitRunner(_DiscoverRunner):  # type: ignore[misc,valid-type]
        """DiscoverRunner that emits JUnit XML via JUnitResult."""

        def get_resultclass(self) -> type[JUnitResult]:
            return JUnitResult

        def run_suite(self, suite: object, **kwargs: object) -> object:
            result = super().run_suite(suite, **kwargs)
            _write_report(result)
            return result

except Exception:  # pragma: no cover - Django not installed (e.g. dev env)
    class JUnitRunner:  # type: ignore[no-redef]
        """Stub used when Django is unavailable; never invoked in that case."""
