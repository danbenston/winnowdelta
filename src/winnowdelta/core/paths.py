"""Small path helpers shared across parsers."""

from __future__ import annotations

from pathlib import Path


def relativize(path: str | None, base: Path | None) -> str | None:
    """Return *path* relative to *base* when possible, else unchanged."""
    if path is None or base is None:
        return path
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except (ValueError, OSError):
        return path
