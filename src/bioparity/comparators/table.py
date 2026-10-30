from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, read_bytes, read_lines, write_mutation


class Tol:
    __slots__ = ("rtol", "atol")

    def __init__(self, rtol: float = 0.0, atol: float = 0.0):
        self.rtol, self.atol = float(rtol), float(atol)


def split_line(line: str, delimiter: str) -> list[str]:
    if delimiter == "whitespace":
        return line.split()
    return [cell.strip() for cell in line.split(delimiter)]


def join_line(cells: list[str], delimiter: str) -> str:
    return " ".join(cells) if delimiter == "whitespace" else delimiter.join(cells)


def to_float(text: str):
    try:
        return float(text)
    except ValueError:
        return None


def cell_equal(a: str, b: str, tol: Tol, precision) -> tuple[bool, bool]:
    """(equal, used_tolerance)."""
    if a == b:
        return True, False
    fa, fb = to_float(a), to_float(b)
    if fa is None or fb is None:
        return False, False
    if math.isnan(fa) or math.isnan(fb):
        return (math.isnan(fa) and math.isnan(fb)), False
    if math.isinf(fa) or math.isinf(fb):
        return fa == fb, False
    if precision is not None:
        fa, fb = round(fa, precision), round(fb, precision)
    if fa == fb:
        return True, True
    diff = abs(fa - fb)
    # either bound is enough (the lenient semantics used by RustQC-benchmarks)
    return (diff <= tol.atol or diff <= tol.rtol * max(abs(fa), abs(fb))), True


def table_lines(path: Path, opts: dict) -> tuple[list[str], list[tuple[int, str]]]:
    """(all raw lines, [(raw line index, text)] of lines taking part in the comparison)."""
    raw = read_bytes(path).decode("utf-8", errors="replace").split("\n")
    prefixes = opts.get("skip_prefixes", [])
    kept = [(i, ln) for i, ln in enumerate(raw) if ln.strip() and not any(ln.startswith(p) for p in prefixes)]
    return raw, kept


def resolve(col, header: list[str] | None) -> int:
    if isinstance(col, int):
        return col
    if header is not None and col in header:
        return header.index(col)
    if isinstance(col, str) and col.isdigit():
        return int(col)
    raise ValueError(f"column '{col}' not found in header {header}")


def col_label(idx: int, header: list[str] | None) -> str:
    return header[idx] if header and idx < len(header) else str(idx)


def compared_columns(width: int, header, opts: dict) -> list[int]:
    cols = [resolve(c, header) for c in opts["columns"]] if opts.get("columns") else list(range(width))
    ignored = {resolve(c, header) for c in opts.get("ignore_columns", [])}
    return [c for c in cols if c not in ignored]


def tolerance_for(idx: int, header, opts: dict) -> Tol:
    base = Tol(opts.get("rtol", 0.0), opts.get("atol", 0.0))
    for col, spec in (opts.get("tolerances") or {}).items():
        try:
            if resolve(col, header) == idx:
                return Tol(spec.get("rtol", base.rtol), spec.get("atol", base.atol))
        except ValueError:
            continue
    return base


def parse_rows(path: Path, opts: dict):
    _, kept = table_lines(path, opts)
    delimiter = opts.get("delimiter", "\t")
    rows = [split_line(text, delimiter) for _, text in kept]
    header = None
    if opts.get("header", True) and rows:
        header, rows = rows[0], rows[1:]
    return header, rows


def keyed(rows: list[list[str]], key_idx: list[int]) -> dict:
    seen: Counter = Counter()
    out = {}
    for row in rows:
        key = tuple(row[i] if i < len(row) else "" for i in key_idx)
        seen[key] += 1
        out[key + ((f"#{seen[key]}",) if seen[key] > 1 else ())] = row
    return out


@register
class Table(Comparator):
    """Delimited tables with key-based or positional rows, per-column numeric tolerances."""

    name = "table"
    defaults: dict = {}

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        opts = {**self.defaults, **options}
        if ref.read_bytes() == cand.read_bytes():
            return Result(Verdict.IDENTICAL, "byte-identical")
        h1, r1 = parse_rows(ref, opts)
        h2, r2 = parse_rows(cand, opts)
        width = max([len(h1 or [])] + [len(r) for r in r1] + [0])
        cols = compared_columns(width, h1, opts)
        precision = opts.get("precision")
        limit = opts.get("max_examples", 10)
        problems: list[str] = []
        stats = {"rows": 0, "cells": 0, "tolerated": 0, "max_abs_dev": 0.0, "max_rel_dev": 0.0}

        if h1 is not None and h2 is not None and opts.get("header_check", True):
            for c in cols:
                a = h1[c] if c < len(h1) else None
                b = h2[c] if c < len(h2) else None
                if a != b:
                    problems.append(f"header column {c}: reference='{a}' candidate='{b}'")

        key_idx = [resolve(k, h1) for k in opts["key"]] if opts.get("key") else None
        if key_idx is not None:
            d1, d2 = keyed(r1, key_idx), keyed(r2, key_idx)
            for k in d1.keys() - d2.keys():
                problems.append(f"key {k} only in reference")
            for k in d2.keys() - d1.keys():
                problems.append(f"key {k} only in candidate")
            pairs = [(k, d1[k], d2[k]) for k in d1 if k in d2]
        else:
            if opts.get("ignore_order"):
                r1, r2 = sorted(r1), sorted(r2)
            if len(r1) != len(r2):
                problems.append(f"row count differs: reference {len(r1)} vs candidate {len(r2)}")
            pairs = [(i + 1, a, b) for i, (a, b) in enumerate(zip(r1, r2))]

        for key, a, b in pairs:
            stats["rows"] += 1
            for c in cols:
                x = a[c] if c < len(a) else None
                y = b[c] if c < len(b) else None
                if x is None or y is None:
                    problems.append(f"row {key}: column {col_label(c, h1)} missing on one side")
                    continue
                ok, used = cell_equal(x, y, tolerance_for(c, h1, opts), precision)
                stats["cells"] += 1
                if used and ok:
                    stats["tolerated"] += 1
                fx, fy = to_float(x), to_float(y)
                if fx is not None and fy is not None and math.isfinite(fx) and math.isfinite(fy) and fx != fy:
                    dev = abs(fx - fy)
                    stats["max_abs_dev"] = max(stats["max_abs_dev"], dev)
                    stats["max_rel_dev"] = max(stats["max_rel_dev"], dev / max(abs(fx), abs(fy)))
                if not ok:
                    problems.append(f"row {key} col {col_label(c, h1)}: reference={x} candidate={y}")

        if problems:
            return Result(Verdict.DIVERGENT, f"{len(problems)} differences in {stats['rows']} compared rows",
                          problems[:limit], stats)
        note = f", {stats['tolerated']} cells within tolerance" if stats["tolerated"] else ""
        return Result(Verdict.EQUIVALENT, f"{stats['rows']} rows, {stats['cells']} cells compared{note}", [], stats)

    # ---- mutation self-test -------------------------------------------------
    def mutations(self, ref: Path, options: dict, workdir: Path):
        opts = {**self.defaults, **options}
        raw, kept = table_lines(ref, opts)
        delimiter = opts.get("delimiter", "\t")
        parsed = [(i, split_line(text, delimiter)) for i, text in kept]
        header = None
        if opts.get("header", True) and parsed:
            header, parsed = parsed[0][1], parsed[1:]
        if not parsed:
            return []
        width = max(len(r) for _, r in parsed)
        key_idx = {resolve(k, header) for k in opts.get("key", [])}
        cols = [c for c in compared_columns(width, header, opts) if c not in key_idx]
        mid = parsed[len(parsed) // 2]

        def emit(tag: str, lines: list[str]):
            return write_mutation(workdir, ref, tag, "\n".join(lines).encode())

        out = []
        # numeric perturbation beyond the configured tolerance
        for c in cols:
            row_i, cells = mid
            value = to_float(cells[c]) if c < len(cells) else None
            if value is None or not math.isfinite(value):
                continue
            tol = tolerance_for(c, header, opts)
            precision = opts.get("precision")
            delta = max(10 * tol.atol, 10 * tol.rtol * abs(value),
                        10 ** (1 - precision) if precision is not None else 0.0)
            if delta == 0.0:
                delta = max(abs(value) * 1e-3, 1e-3)
            changed = list(cells)
            changed[c] = f"{value + delta:.12g}"
            lines = list(raw)
            lines[row_i] = join_line(changed, delimiter)
            out.append((f"perturb {col_label(c, header)} beyond tolerance (row at line {row_i + 1})",
                        emit("perturb", lines)))
            break
        # string cell alteration
        for c in cols:
            row_i, cells = mid
            if c < len(cells) and to_float(cells[c]) is None:
                changed = list(cells)
                changed[c] = cells[c] + "X"
                lines = list(raw)
                lines[row_i] = join_line(changed, delimiter)
                out.append((f"alter text in {col_label(c, header)}", emit("alter", lines)))
                break
        # drop and duplicate a row
        row_i, cells = parsed[-1]
        out.append(("drop last row", emit("droprow", [ln for i, ln in enumerate(raw) if i != row_i])))
        lines = list(raw)
        lines.insert(row_i + 1, raw[row_i])
        out.append(("duplicate last row", emit("duprow", lines)))
        return out


__all__ = ["Table", "Tol", "cell_equal"]
