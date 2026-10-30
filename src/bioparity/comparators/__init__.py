"""Comparator registry. Third-party comparators register via the
`bioparity.comparators` entry-point group."""

from __future__ import annotations

from importlib import metadata

from .base import Comparator, Result, Verdict, exit_code  # noqa: F401

_REGISTRY: dict[str, Comparator] = {}
_PLUGINS_LOADED = False


def register(cls):
    _REGISTRY[cls.name] = cls()
    return cls


def _load_plugins() -> None:
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return
    _PLUGINS_LOADED = True
    for entry in metadata.entry_points(group="bioparity.comparators"):
        try:
            register(entry.load())
        except Exception:  # a broken plugin must not break the built-ins
            continue


def get(name: str) -> Comparator:
    _load_plugins()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown comparator '{name}'. available: {', '.join(sorted(_REGISTRY))}") from None


def names() -> list[str]:
    _load_plugins()
    return sorted(_REGISTRY)


from . import exact, fastq, fields, metrics, structural, table, text  # noqa: E402,F401
