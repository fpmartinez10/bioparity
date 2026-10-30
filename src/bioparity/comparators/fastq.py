from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, read_bytes, write_mutation


def records(path: Path) -> list[tuple[str, ...]]:
    lines = read_bytes(path).decode("utf-8", errors="replace").splitlines()
    return [tuple(lines[i:i + 4]) for i in range(0, len(lines) - len(lines) % 4, 4)]


@register
class Fastq(Comparator):
    """FASTQ record comparison (gzip-aware); `ordered: false` compares as a multiset."""

    name = "fastq"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        if ref.read_bytes() == cand.read_bytes():
            return Result(Verdict.IDENTICAL, "byte-identical")
        a, b = records(ref), records(cand)
        ordered = options.get("ordered", True)
        if ordered:
            if a == b:
                return Result(Verdict.EQUIVALENT, f"{len(a)} records identical after decompression")
            first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            example = [f"record {first + 1}: reference={a[first][0] if first < len(a) else '<none>'} "
                       f"candidate={b[first][0] if first < len(b) else '<none>'}"]
            return Result(Verdict.DIVERGENT, f"records differ: {len(a)} vs {len(b)} records, first difference at record {first + 1}", example)
        ca, cb = Counter(a), Counter(b)
        if ca == cb:
            return Result(Verdict.EQUIVALENT, f"{len(a)} records identical as a multiset (order differs)")
        return Result(Verdict.DIVERGENT, f"{sum((ca - cb).values())} records only in reference, {sum((cb - ca).values())} only in candidate")

    def mutations(self, ref: Path, options: dict, workdir: Path):
        recs = records(ref)
        if not recs:
            return []
        mid = len(recs) // 2
        base = list(recs[mid])
        seq = base[1]
        base[1] = ("A" if seq[:1] != "A" else "C") + seq[1:]
        changed = recs[:mid] + [tuple(base)] + recs[mid + 1:]
        dropped = recs[:-1]
        enc = lambda rs: ("\n".join("\n".join(r) for r in rs) + "\n").encode()
        return [
            ("change one base", write_mutation(workdir, ref, "base", enc(changed))),
            ("drop last record", write_mutation(workdir, ref, "drop", enc(dropped))),
        ]
