from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Optional

import typer

from . import comparators, evidence, pairing, report, runner, selftest as selftest_mod, spec as spec_mod
from .comparators.base import exit_code

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Evidence that a rewrite of a bioinformatics tool matches the original.")

TEMPLATE = """\
name: my-rewrite-vs-original
# extends: rustqc-rna          # optionally start from a shared preset (see `bioparity presets`)
reference: {label: "original 1.0", container: "quay.io/biocontainers/TOOL:TAG",
            command: "tool {params} -o {outdir} {inputs.reads}", version_command: "tool --version"}
candidate: {label: "rewrite 2.0",  container: "quay.io/biocontainers/TOOL2:TAG",
            command: "tool {params} -o {outdir} {inputs.reads}", version_command: "tool --version"}
cases:
  - {id: default, inputs: {reads: data/sample.fq.gz}, params: ""}
outputs:
  - {pattern: "*.fq.gz", comparator: fastq}
  - {pattern: "*_report.txt", comparator: text, options: {ignore_lines: ["^Command line", "version"]}}
accepted_divergences: []
"""


def _fail_on_error(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(3)
    return wrapper


def _finish(ev: dict, json_path: Optional[Path], report_path: Optional[Path]) -> None:
    if json_path:
        evidence.save(ev, json_path)
    md = report.render(ev)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md)
    typer.echo(md)
    raise typer.Exit(ev["exit_code"])


@app.command()
def init(path: Path = typer.Option(Path("parity.yaml"), help="Where to write the template")):
    """Write a template parity.yaml."""
    if path.exists():
        typer.echo(f"error: {path} already exists", err=True)
        raise typer.Exit(3)
    path.write_text(TEMPLATE)
    typer.echo(f"wrote {path}")


@app.command()
def presets():
    """List shared rule presets and comparators."""
    typer.echo("presets:     " + ", ".join(spec_mod.preset_names()))
    typer.echo("comparators: " + ", ".join(comparators.names()))


@app.command()
@_fail_on_error
def run(spec: Path = typer.Argument(..., exists=True, help="parity.yaml"),
        workdir: Path = typer.Option(Path("runs"), help="Where tool outputs and logs go"),
        case: Optional[str] = typer.Option(None, help="Run a single case id"),
        dry_run: bool = typer.Option(False, help="Print the commands without running them"),
        json_path: Path = typer.Option(None, "--json", help="evidence.json path (default: WORKDIR/evidence.json)"),
        report_path: Path = typer.Option(None, "--report", help="report.md path (default: WORKDIR/report.md)")):
    """Run reference and candidate on every case, compare, write evidence."""
    s = spec_mod.load_spec(spec)
    ev = runner.run_spec(s, spec.resolve().parent, workdir, case, dry_run, typer.echo)
    if ev is None:
        raise typer.Exit(0)
    _finish(ev, json_path or workdir / "evidence.json", report_path or workdir / "report.md")


@app.command()
@_fail_on_error
def compare(reference: Path = typer.Argument(..., exists=True, file_okay=False, help="Reference output directory"),
            candidate: Path = typer.Argument(..., exists=True, file_okay=False, help="Candidate output directory"),
            spec: Optional[Path] = typer.Option(None, exists=True, help="parity.yaml with `outputs` rules"),
            preset: Optional[str] = typer.Option(None, help="Shared rule preset (see `bioparity presets`)"),
            label: str = typer.Option("", help="Label for the report title"),
            json_path: Optional[Path] = typer.Option(None, "--json"),
            report_path: Optional[Path] = typer.Option(None, "--report")):
    """Compare two existing output directories (no tools are run)."""
    if not spec and not preset:
        raise ValueError("give --spec and/or --preset so there are rules to apply")
    s = spec_mod.load_spec(spec, preset)
    results = pairing.compare_dirs(reference, candidate, s)
    ev = evidence.build(label or s.name, {"label": str(reference)}, {"label": str(candidate)},
                        [evidence.case_dict("compare", results)])
    _finish(ev, json_path, report_path)


@app.command()
@_fail_on_error
def selftest(reference: Path = typer.Argument(..., exists=True, file_okay=False, help="A reference output directory"),
             spec: Optional[Path] = typer.Option(None, exists=True),
             preset: Optional[str] = typer.Option(None)):
    """Alter reference outputs on purpose; every alteration must be flagged divergent."""
    if not spec and not preset:
        raise ValueError("give --spec and/or --preset so there are rules to test")
    s = spec_mod.load_spec(spec, preset)
    outcomes = selftest_mod.run_selftest(reference, s)
    missed = [o for o in outcomes if not o.caught]
    for o in outcomes:
        typer.echo(f"{'ok  ' if o.caught else 'MISS'} {o.path} [{o.comparator}] {o.mutation}")
    typer.echo(f"\n{len(outcomes) - len(missed)}/{len(outcomes)} checks passed")
    raise typer.Exit(1 if missed or not outcomes else 0)


@app.command(name="report")
@_fail_on_error
def report_cmd(evidence_path: Path = typer.Argument(..., exists=True, dir_okay=False),
               output: Optional[Path] = typer.Option(None, "-o")):
    """Re-render the Markdown report from an evidence.json."""
    md = report.render(json.loads(evidence_path.read_text()))
    if output:
        output.write_text(md)
    typer.echo(md)


if __name__ == "__main__":
    app()
