"""Shared types and file helpers for comparators."""

from __future__ import annotations

import enum
import gzip
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class Verdict(str, enum.Enum):
    IDENTICAL = "identical"
    EQUIVALENT = "equivalent"
    ACCEPTED = "accepted"
    DIVERGENT = "divergent"
    MISSING = "missing"
    EXTRA = "extra"
    ERROR = "error"


EXIT_CODES = {
    Verdict.IDENTICAL: 0,
    Verdict.EQUIVALENT: 0,
    Verdict.ACCEPTED: 0,
    Verdict.DIVERGENT: 1,
    Verdict.MISSING: 2,
    Verdict.EXTRA: 2,
    Verdict.ERROR: 3,
}


def exit_code(verdicts) -> int:
    return max((EXIT_CODES[Verdict(v)] for v in verdicts), default=0)


@dataclass
class Result:
    verdict: Verdict
    summary: str = ""
    examples: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class Comparator:
    """Base class. Subclasses set `name` and implement `compare`."""

    name = "base"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        raise NotImplementedError

    def mutations(self, ref: Path, options: dict, workdir: Path) -> list[tuple[str, Path]]:
        """Return (description, mutated file) pairs that `compare` must flag as divergent."""
        return []


def is_gzip(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def read_bytes(path: Path) -> bytes:
    """File content, transparently decompressed when gzip/bgzip."""
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8", errors="replace")


def read_lines(path: Path) -> list[str]:
    return read_text(path).splitlines()


def write_mutation(workdir: Path, ref: Path, tag: str, data: bytes) -> Path:
    """Write mutated content next to a tag directory, keeping gzip-ness of the source."""
    directory = workdir / tag
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ref.name
    if is_gzip(ref):
        data = gzip.compress(data, mtime=0)
    destination.write_bytes(data)
    return destination
