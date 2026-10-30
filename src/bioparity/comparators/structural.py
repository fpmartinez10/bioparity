from __future__ import annotations

import re
from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, write_mutation
from .table import parse_rows, split_line, table_lines, to_float


@register
class Structural(Comparator):
    """For stochastic or implementation-dependent outputs: same shape, not same values.

    Checks the label set of a key column, row count (within `rows_rtol`), the set of row
    widths, which columns are numeric, and that selected lines (`exact_lines` regexes)
    are identical.
    """

    name = "structural"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        opts = {"header": False, **options}
        h1, r1 = parse_rows(ref, opts)
        h2, r2 = parse_rows(cand, opts)
        problems: list[str] = []
        tol = opts.get("rows_rtol", 0.0)
        if abs(len(r1) - len(r2)) > tol * max(len(r1), len(r2)):
            problems.append(f"row count: reference {len(r1)} vs candidate {len(r2)}")
        if opts["header"] and h1 != h2:
            problems.append(f"header differs: {h1} vs {h2}")
        if sorted({len(r) for r in r1}) != sorted({len(r) for r in r2}):
            problems.append(f"row widths differ: {sorted({len(r) for r in r1})} vs {sorted({len(r) for r in r2})}")
        key = opts.get("key")
        if key is not None:
            labels1 = sorted(r[key] for r in r1 if len(r) > key)
            labels2 = sorted(r[key] for r in r2 if len(r) > key)
            if labels1 != labels2:
                only1, only2 = set(labels1) - set(labels2), set(labels2) - set(labels1)
                problems.append(f"labels in column {key} differ: only reference {sorted(only1)[:5]}, only candidate {sorted(only2)[:5]}")
        if opts.get("check_numeric", True) and r1 and r2:
            for c in range(min(len(r1[0]), len(r2[0]))):
                n1 = all(to_float(r[c]) is not None for r in r1 if len(r) > c)
                n2 = all(to_float(r[c]) is not None for r in r2 if len(r) > c)
                if n1 != n2:
                    problems.append(f"column {c} numeric in {'reference' if n1 else 'candidate'} only")
        for rx in opts.get("exact_lines", []):
            m1 = sorted(ln.strip() for _, ln in table_lines(ref, opts)[1] if re.search(rx, ln))
            m2 = sorted(ln.strip() for _, ln in table_lines(cand, opts)[1] if re.search(rx, ln))
            if m1 != m2:
                problems.append(f"lines matching /{rx}/ differ: {m1[:2]} vs {m2[:2]}")
        if problems:
            return Result(Verdict.DIVERGENT, f"{len(problems)} structural differences", problems[: opts.get("max_examples", 10)])
        return Result(Verdict.EQUIVALENT, f"same structure ({len(r1)} rows)")

    def mutations(self, ref: Path, options: dict, workdir: Path):
        opts = {"header": False, **options}
        raw, kept = table_lines(ref, opts)
        if len(kept) < 2:
            return []
        out = []
        last_i = kept[-1][0]
        if opts.get("rows_rtol", 0.0) < 0.5 / max(len(kept), 1):
            out.append(("drop last row", write_mutation(workdir, ref, "drop", "\n".join(
                ln for i, ln in enumerate(raw) if i != last_i).encode())))
        delimiter = opts.get("delimiter", "\t")
        mid_i, mid_text = kept[len(kept) // 2]
        cells = split_line(mid_text, delimiter)
        lines = list(raw)
        lines[mid_i] = (" " if delimiter == "whitespace" else delimiter).join(cells + ["extra"])
        out.append(("add a column to one row", write_mutation(workdir, ref, "widen", "\n".join(lines).encode())))
        return out
