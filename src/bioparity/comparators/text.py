from __future__ import annotations

import difflib
import re
from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, read_bytes, write_mutation


def significant(line: str, opts: dict) -> bool:
    """True when the line takes part in the comparison."""
    text = line.strip() if opts.get("strip", True) else line
    if opts.get("skip_blank", True) and not text.strip():
        return False
    if any(line.startswith(p) for p in opts.get("ignore_prefixes", [])):
        return False
    return not any(re.search(rx, line) for rx in opts.get("ignore_lines", []))


def normalise(lines: list[str], opts: dict) -> list[str]:
    kept = [ln.strip() if opts.get("strip", True) else ln for ln in lines if significant(ln, opts)]
    return sorted(kept) if opts.get("sort", False) else kept


def alter_line(line: str) -> str:
    """Change one alphanumeric character so the line is guaranteed to differ."""
    for i, ch in enumerate(line):
        if ch.isdigit():
            return line[:i] + str((int(ch) + 1) % 10) + line[i + 1:]
        if ch.isalpha():
            return line[:i] + (ch.lower() if ch.isupper() else ch.upper()) + line[i + 1:]
    return line + "x"


@register
class Text(Comparator):
    """Line-oriented comparison with ignorable lines (headers, versions, timestamps)."""

    name = "text"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        if ref.read_bytes() == cand.read_bytes():
            return Result(Verdict.IDENTICAL, "byte-identical")
        a = read_bytes(ref).decode("utf-8", errors="replace").splitlines()
        b = read_bytes(cand).decode("utf-8", errors="replace").splitlines()
        na, nb = normalise(a, options), normalise(b, options)
        if na == nb:
            return Result(Verdict.EQUIVALENT, f"equal after normalisation ({len(na)} lines compared)")
        diff = [
            ln for ln in difflib.unified_diff(na, nb, "reference", "candidate", lineterm="", n=0)
            if not ln.startswith(("---", "+++", "@@"))
        ]
        limit = options.get("max_examples", 10)
        return Result(
            Verdict.DIVERGENT,
            f"{len(diff)} differing lines (reference {len(na)} vs candidate {len(nb)} lines)",
            diff[:limit],
        )

    def mutations(self, ref: Path, options: dict, workdir: Path):
        lines = read_bytes(ref).decode("utf-8", errors="replace").split("\n")
        idx = [i for i, ln in enumerate(lines) if significant(ln, options)]
        if not idx:
            return []
        mid, last = idx[len(idx) // 2], idx[-1]
        changed = list(lines)
        changed[mid] = alter_line(changed[mid])
        dropped = [ln for i, ln in enumerate(lines) if i != last]
        return [
            (f"alter a character on line {mid + 1}", write_mutation(workdir, ref, "alter", "\n".join(changed).encode())),
            (f"drop line {last + 1}", write_mutation(workdir, ref, "drop", "\n".join(dropped).encode())),
        ]
