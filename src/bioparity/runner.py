"""Run reference and candidate tools for each case, then compare."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from . import evidence, pairing
from .spec import Case, Spec, Tool


def render_command(tool: Tool, case: Case, outdir: Path, base: Path) -> tuple[str, list[Path]]:
    inputs = {k: (base / v).resolve() if not Path(v).is_absolute() else Path(v) for k, v in case.inputs.items()}
    command = tool.command.format(params=case.params, outdir=outdir, inputs=SimpleNamespace(**{k: str(v) for k, v in inputs.items()}))
    return command, [v.parent for v in inputs.values()]


def wrap(tool: Tool, command: str, outdir: Path, input_dirs: list[Path]) -> list[str] | str:
    if not tool.container:
        return command
    argv = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-w", str(outdir),
            "-v", f"{outdir}:{outdir}"]
    for d in sorted(set(input_dirs)):
        argv += ["-v", f"{d}:{d}:ro"]
    return argv + [tool.container, "sh", "-c", command]


def execute(tool: Tool, command: str, outdir: Path, input_dirs: list[Path], log: Path) -> dict:
    wrapped = wrap(tool, command, outdir, input_dirs)
    start = time.monotonic()
    with log.open("w") as handle:
        proc = subprocess.run(wrapped, shell=isinstance(wrapped, str), cwd=outdir, stdout=handle, stderr=subprocess.STDOUT)
    info = {"command": command, "exit_code": proc.returncode, "seconds": round(time.monotonic() - start, 2), "log": str(log)}
    if tool.version_command:
        v = subprocess.run(wrap(tool, tool.version_command, outdir, input_dirs), shell=not tool.container,
                           cwd=outdir, capture_output=True, text=True)
        info["version"] = (v.stdout.strip() or v.stderr.strip()).splitlines()[0] if (v.stdout.strip() or v.stderr.strip()) else ""
    return info


def run_spec(spec: Spec, spec_dir: Path, workdir: Path, only: str | None = None, dry_run: bool = False, echo=print) -> dict | None:
    if not (spec.reference and spec.candidate and spec.cases):
        raise ValueError("`run` needs reference, candidate and cases in the spec (use `compare` for existing outputs)")
    cases = [c for c in spec.cases if only in (None, c.id)]
    if not cases:
        raise ValueError(f"no case named '{only}'")
    case_records = []
    versions: dict[str, str] = {}
    for case in cases:
        runs: dict[str, dict] = {}
        dirs: dict[str, Path] = {}
        for side, tool in (("reference", spec.reference), ("candidate", spec.candidate)):
            outdir = (workdir / case.id / side).resolve()
            dirs[side] = outdir
            command, input_dirs = render_command(tool, case, outdir, spec_dir)
            if dry_run:
                echo(f"[{case.id}/{side}] {wrap(tool, command, outdir, input_dirs)}")
                continue
            outdir.mkdir(parents=True, exist_ok=True)
            echo(f"[{case.id}/{side}] running {tool.label}")
            runs[side] = execute(tool, command, outdir, input_dirs, workdir / case.id / f"{side}.log")
            versions[side] = runs[side].get("version", "")
        if dry_run:
            continue
        if any(r["exit_code"] != 0 for r in runs.values()):
            failed = [s for s, r in runs.items() if r["exit_code"] != 0]
            from .comparators.base import Result, Verdict
            res = [pairing.FileResult(f"<{s} run>", None, "run", Result(Verdict.ERROR, f"{s} exited with {runs[s]['exit_code']} (see {runs[s]['log']})")) for s in failed]
        else:
            res = pairing.compare_dirs(dirs["reference"], dirs["candidate"], spec)
        case_records.append(evidence.case_dict(case.id, res, runs))
    if dry_run:
        return None
    ref = {"label": spec.reference.label, "version": versions.get("reference", "")}
    cand = {"label": spec.candidate.label, "version": versions.get("candidate", "")}
    return evidence.build(spec.name, ref, cand, case_records)
