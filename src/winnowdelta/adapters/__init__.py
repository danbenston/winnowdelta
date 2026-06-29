"""Per-framework adapters.

Importing this package registers all built-in adapters (test + diagnostic) into
the ``core.adapter`` registries as an import side effect. The engine imports it
once to make adapters discoverable.
"""

from . import (  # noqa: F401  (registration side effects)
    django_adapter,
    eslint_adapter,
    jest_adapter,
    prettier_adapter,
    pytest_adapter,
    tsc_adapter,
    vitest_adapter,
)

__all__ = [
    "django_adapter",
    "eslint_adapter",
    "jest_adapter",
    "prettier_adapter",
    "pytest_adapter",
    "tsc_adapter",
    "vitest_adapter",
]
