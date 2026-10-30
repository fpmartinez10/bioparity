from __future__ import annotations

import re
from pathlib import Path

from . import register
from .base import Comparator, Result, Verdict, read_bytes, write_mutation


def extract(text_lines: list[str], spec: dict):
    rx = re.compile(spec["regex"])
    for line in text_lines:
        m = rx.search(line)
        if m:
            value = m.group(1) if m.groups() else m.group(0)
            if spec.get("split"):
                parts = [p.strip() for p in value.split(spec["split"])]
                pick = spec.get("pick", "all")
                return parts if pick == "all" else parts[-1] if pick == "last" else parts[0]
            return value.strip()
    return None


@register
class Fields(Comparator):
    """Compare values pulled out of lines by regex (e.g. the 100% point of an R plot script)."""

    name = "fields"

    def compare(self, ref: Path, cand: Path, options: dict) -> Result:
        a = read_bytes(ref).decode("utf-8", errors="replace").splitlines()
        b = read_bytes(cand).decode("utf-8", errors="replace").splitlines()
        problems = []
        specs = options.get("fields", [])
        for spec in specs:
            va, vb = extract(a, spec), extract(b, spec)
            if va != vb and spec.get("rtol") is not None and va is not None and vb is not None:
                try:
                    fa, fb = float(va), float(vb)
                    if abs(fa - fb) <= spec["rtol"] * max(abs(fa), abs(fb)):
                        continue
                except (TypeError, ValueError):
                    pass
            if va != vb:
                problems.append(f"{spec.get('name', spec['regex'])}: reference={va} candidate={vb}")
        if not specs:
            return Result(Verdict.ERROR, "no `fields` configured")
        if problems:
            return Result(Verdict.DIVERGENT, f"{len(problems)} of {len(specs)} fields differ", problems)
        return Result(Verdict.EQUIVALENT, f"{len(specs)} extracted fields equal")

    def mutations(self, ref: Path, options: dict, workdir: Path):
        lines = read_bytes(ref).decode("utf-8", errors="replace").split("\n")
        out = []
        for n, spec in enumerate(options.get("fields", [])):
            rx = re.compile(spec["regex"])
            for i, line in enumerate(lines):
                if rx.search(line):
                    changed = list(lines)
                    tokens = list(re.finditer(r"-?\d+(?:\.\d+)?", line))
                    if tokens:
                        t = tokens[-1]
                        old = float(t.group(0))
                        new = old * (1 + 10 * spec["rtol"]) + 1 if spec.get("rtol") else old + 1
                        changed[i] = line[:t.start()] + (f"{new:.12g}" if "." in t.group(0) or spec.get("rtol") else str(int(new))) + line[t.end():]
                    else:
                        changed[i] = line + "9"
                    out.append((f"alter value of '{spec.get('name', n)}'", write_mutation(workdir, ref, f"field{n}", "\n".join(changed).encode())))
                    break
        return out
