"""evidence.json (schema bioparity.evidence/1)."""

from __future__ import annotations

import datetime as dt
import getpass
import json
import platform
from pathlib import Path

from . import __version__
from .comparators.base import exit_code
from .pairing import FileResult

SCHEMA = "bioparity.evidence/1"


def result_dict(r: FileResult) -> dict:
    return {
        "path": r.path, "candidate_path": r.candidate_path, "comparator": r.comparator,
        "verdict": r.result.verdict.value, "summary": r.result.summary, "examples": r.result.examples,
        "metrics": r.result.metrics, "note": r.note,
        "reference_sha256": r.ref_sha256, "candidate_sha256": r.cand_sha256,
    }


def case_dict(case_id: str, results: list[FileResult], runs: dict | None = None) -> dict:
    return {
        "id": case_id,
        "runs": runs or {},
        "results": [result_dict(r) for r in results],
        "exit_code": exit_code(r.result.verdict for r in results),
    }


def build(spec_name: str, reference: dict, candidate: dict, cases: list[dict]) -> dict:
    verdicts = [res["verdict"] for c in cases for res in c["results"]]
    return {
        "schema": SCHEMA,
        "bioparity_version": __version__,
        "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "host": {"platform": platform.platform(), "python": platform.python_version(), "user": getpass.getuser()},
        "spec": spec_name,
        "reference": reference,
        "candidate": candidate,
        "cases": cases,
        "summary": {v: verdicts.count(v) for v in sorted(set(verdicts))},
        "exit_code": exit_code(verdicts),
    }


def save(evidence: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n")
