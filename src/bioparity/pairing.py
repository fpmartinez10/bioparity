"""Pair reference outputs with candidate outputs and compare them."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import comparators
from .comparators.base import Result, Verdict
from .spec import Spec


@dataclass
class FileResult:
    path: str                    # relative path in the reference dir
    candidate_path: str | None
    comparator: str
    result: Result
    ref_sha256: str | None = None
    cand_sha256: str | None = None
    note: str = ""


def sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def candidate_name(rel: str, rename) -> str:
    return re.sub(rename[0], rename[1], rel) if rename else rel


def compare_dirs(ref_dir: Path, cand_dir: Path, spec: Spec) -> list[FileResult]:
    results: list[FileResult] = []
    claimed_cand: set[str] = set()
    ref_files = [f for f in rel_files(ref_dir) if not any(fnmatch.fnmatch(f, g) for g in spec.ignore)]
    done: set[str] = set()
    for rule in spec.outputs:
        matches = [f for f in ref_files if f not in done and fnmatch.fnmatch(f, rule.pattern)]
        for rel in matches:
            done.add(rel)
            cand_rel = candidate_name(rel, rule.rename)
            claimed_cand.add(cand_rel)
            results.append(compare_one(ref_dir, cand_dir, rel, cand_rel, rule, spec))
        if not matches and rule.required and not any(c in rule.pattern for c in "*?["):
            # a literal required path that does not exist in the reference output
            results.append(FileResult(rule.pattern, None, rule.comparator,
                                      Result(Verdict.MISSING, "no reference file matches this pattern (absent or ignored)")))
    # candidate files that match a rule's pattern but have no reference counterpart
    for cand_rel in rel_files(cand_dir):
        if cand_rel in claimed_cand or any(fnmatch.fnmatch(cand_rel, g) for g in spec.ignore):
            continue
        for rule in spec.outputs:
            if rule.rename is None and fnmatch.fnmatch(cand_rel, rule.pattern):
                results.append(FileResult(cand_rel, cand_rel, rule.comparator,
                                          Result(Verdict.EXTRA, "produced by candidate only"),
                                          cand_sha256=sha256(cand_dir / cand_rel)))
                break
    return results


def compare_one(ref_dir, cand_dir, rel, cand_rel, rule, spec) -> FileResult:
    ref, cand = ref_dir / rel, cand_dir / cand_rel
    if not cand.is_file():
        return FileResult(rel, cand_rel, rule.comparator, Result(Verdict.MISSING, "candidate did not produce this output"),
                          ref_sha256=sha256(ref))
    try:
        result = comparators.get(rule.comparator).compare(ref, cand, rule.options)
    except Exception as exc:  # a comparator bug must not hide other results
        result = Result(Verdict.ERROR, f"{type(exc).__name__}: {exc}")
    note = ""
    if result.verdict == Verdict.DIVERGENT:
        for acc in spec.accepted_divergences:
            if fnmatch.fnmatch(rel, acc.pattern):
                result.verdict, note = Verdict.ACCEPTED, acc.reason
                break
    return FileResult(rel, cand_rel, rule.comparator, result, sha256(ref), sha256(cand), note)
