"""Mutation self-test: every deliberate alteration of a reference output must be flagged."""

from __future__ import annotations

import fnmatch
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import comparators
from .comparators.base import Verdict
from .pairing import rel_files
from .spec import Spec


@dataclass
class MutationOutcome:
    path: str
    comparator: str
    mutation: str
    caught: bool
    detail: str


def run_selftest(ref_dir: Path, spec: Spec) -> list[MutationOutcome]:
    outcomes: list[MutationOutcome] = []
    done: set[str] = set()
    files = [f for f in rel_files(ref_dir) if not any(fnmatch.fnmatch(f, g) for g in spec.ignore)]
    with tempfile.TemporaryDirectory(prefix="bioparity-selftest-") as tmp:
        tmp_path = Path(tmp)
        for rule in spec.outputs:
            comp = comparators.get(rule.comparator)
            for rel in [f for f in files if f not in done and fnmatch.fnmatch(f, rule.pattern)]:
                done.add(rel)
                ref = ref_dir / rel
                scratch = tmp_path / rel.replace("/", "__")
                scratch.mkdir(parents=True, exist_ok=True)
                # control: an untouched copy must not be flagged
                control = scratch / "control" / ref.name
                control.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ref, control)
                res = comp.compare(ref, control, rule.options)
                outcomes.append(MutationOutcome(rel, rule.comparator, "control (unchanged copy)",
                                                res.verdict in (Verdict.IDENTICAL, Verdict.EQUIVALENT), res.summary))
                try:
                    mutated = comp.mutations(ref, rule.options, scratch)
                except Exception as exc:
                    outcomes.append(MutationOutcome(rel, rule.comparator, "mutation generation", False, f"{type(exc).__name__}: {exc}"))
                    continue
                for description, path in mutated:
                    res = comp.compare(ref, path, rule.options)
                    outcomes.append(MutationOutcome(rel, rule.comparator, description,
                                                    res.verdict == Verdict.DIVERGENT, res.summary))
    return outcomes
