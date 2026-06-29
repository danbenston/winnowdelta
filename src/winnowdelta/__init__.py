"""winnowdelta — run-and-filter feedback tool.

Executes a project's test / build / lint commands and returns only the
structured, filtered delta (failures and new-vs-baseline diagnostics) instead
of raw, verbose console output.
"""

__version__ = "0.1.0"
