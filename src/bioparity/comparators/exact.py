from __future__ import annotations

from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, read_bytes, write_mutation


@register
class Exact(Comparator):
    """Byte identity; gzip files fall back to comparing decompressed content."""

    name = "exact"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        if ref.read_bytes() == cand.read_bytes():
            return Result(Verdict.IDENTICAL, "byte-identical")
        a, b = read_bytes(ref), read_bytes(cand)
        if a == b:
            return Result(Verdict.EQUIVALENT, "identical after decompression")
        offset = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        return Result(Verdict.DIVERGENT, f"content differs at byte {offset} ({len(a)} vs {len(b)} bytes)")

    def mutations(self, ref: Path, options: dict, workdir: Path):
        data = read_bytes(ref)
        if not data:
            return []
        flipped = bytearray(data)
        flipped[len(data) // 2] = (flipped[len(data) // 2] + 1) % 256
        out = [("flip one byte", write_mutation(workdir, ref, "flip", bytes(flipped)))]
        if len(data) > 1:
            out.append(("truncate last byte", write_mutation(workdir, ref, "truncate", data[:-1])))
        return out
