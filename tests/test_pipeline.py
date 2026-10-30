import json
from pathlib import Path

from typer.testing import CliRunner

from bioparity.cli import app

runner = CliRunner()

SPEC = """\
name: demo
outputs:
  - {pattern: "reads.fq", comparator: fastq}
  - {pattern: "metrics.txt", comparator: table, options: {key: [id], rtol: 0.01}}
  - {pattern: "report.txt", comparator: text, options: {ignore_lines: ["^version"]}}
accepted_divergences:
  - {pattern: "report.txt", reason: "wording changed in v2"}
"""


def make(root: Path, metric="100", report="ok", with_reads=True):
    root.mkdir(parents=True, exist_ok=True)
    if with_reads:
        (root / "reads.fq").write_text("@a\nACGT\n+\nIIII\n" * 20)
    (root / "metrics.txt").write_text(f"id\tn\nx\t{metric}\n")
    (root / "report.txt").write_text(f"version {metric}\n{report}\n")


def test_compare_pass_fail_missing_and_accept(tmp_path):
    spec = tmp_path / "parity.yaml"
    spec.write_text(SPEC)
    ref = tmp_path / "ref"; make(ref)
    ok = tmp_path / "ok"; make(ok, metric="100.5")
    res = runner.invoke(app, ["compare", str(ref), str(ok), "--spec", str(spec)])
    assert res.exit_code == 0, res.output

    bad = tmp_path / "bad"; make(bad, metric="150")
    res = runner.invoke(app, ["compare", str(ref), str(bad), "--spec", str(spec)])
    assert res.exit_code == 1 and "divergent" in res.output

    gone = tmp_path / "gone"; make(gone, with_reads=False)
    res = runner.invoke(app, ["compare", str(ref), str(gone), "--spec", str(spec)])
    assert res.exit_code == 2 and "missing" in res.output

    diff = tmp_path / "diff"; make(diff, report="changed")
    out = tmp_path / "ev.json"
    res = runner.invoke(app, ["compare", str(ref), str(diff), "--spec", str(spec), "--json", str(out)])
    assert res.exit_code == 0 and "accepted" in res.output   # divergent report.txt is a documented divergence
    ev = json.loads(out.read_text())
    assert ev["schema"] == "bioparity.evidence/1" and ev["summary"]["accepted"] == 1


def test_extra_output_is_flagged(tmp_path):
    spec = tmp_path / "parity.yaml"; spec.write_text(SPEC)
    ref = tmp_path / "ref"; make(ref, with_reads=False)
    cand = tmp_path / "cand"; make(cand)
    res = runner.invoke(app, ["compare", str(ref), str(cand), "--spec", str(spec)])
    assert res.exit_code == 2 and "extra" in res.output


def test_selftest_catches_all_mutations(tmp_path):
    spec = tmp_path / "parity.yaml"; spec.write_text(SPEC)
    ref = tmp_path / "ref"; make(ref)
    res = runner.invoke(app, ["selftest", str(ref), "--spec", str(spec)])
    assert res.exit_code == 0, res.output
    assert "MISS" not in res.output and "checks passed" in res.output


def test_selftest_flags_a_comparator_that_accepts_everything(tmp_path):
    from bioparity import comparators
    from bioparity.comparators.base import Comparator, Result, Verdict

    @comparators.register
    class Anything(Comparator):
        name = "anything"

        def compare(self, ref, cand, options):
            return Result(Verdict.EQUIVALENT, "always fine")

        def mutations(self, ref, options, workdir):
            bad = workdir / "bad.txt"
            bad.write_text("totally different")
            return [("replace content", bad)]

    spec = tmp_path / "lenient.yaml"
    spec.write_text('outputs:\n  - {pattern: "metrics.txt", comparator: anything}\n')
    ref = tmp_path / "ref"; make(ref)
    res = runner.invoke(app, ["selftest", str(ref), "--spec", str(spec)])
    assert res.exit_code == 1 and "MISS" in res.output


def test_run_with_local_commands(tmp_path):
    (tmp_path / "in.txt").write_text("5\n")
    spec = tmp_path / "parity.yaml"
    spec.write_text("""\
name: local-demo
reference: {label: "cat-ref", command: "cp {inputs.src} {outdir}/out.txt", version_command: "echo ref-1.0"}
candidate: {label: "cat-cand", command: "cp {inputs.src} {outdir}/out.txt", version_command: "echo cand-2.0"}
cases:
  - {id: c1, inputs: {src: in.txt}}
outputs:
  - {pattern: "out.txt", comparator: exact}
""")
    res = runner.invoke(app, ["run", str(spec), "--workdir", str(tmp_path / "runs")])
    assert res.exit_code == 0, res.output
    ev = json.loads((tmp_path / "runs" / "evidence.json").read_text())
    assert ev["reference"]["version"] == "ref-1.0" and ev["candidate"]["version"] == "cand-2.0"
    assert (tmp_path / "runs" / "report.md").exists()
    res = runner.invoke(app, ["run", str(spec), "--workdir", str(tmp_path / "runs2"), "--dry-run"])
    assert res.exit_code == 0 and "cp " in res.output


def test_run_reports_failed_tool(tmp_path):
    spec = tmp_path / "parity.yaml"
    spec.write_text("""\
reference: {label: r, command: "true"}
candidate: {label: c, command: "false"}
cases: [{id: c1}]
outputs: [{pattern: "x", comparator: exact}]
""")
    res = runner.invoke(app, ["run", str(spec), "--workdir", str(tmp_path / "runs")])
    assert res.exit_code == 3 and "error" in res.output


def test_unknown_comparator_and_preset(tmp_path):
    res = runner.invoke(app, ["compare", str(tmp_path), str(tmp_path), "--preset", "nope"])
    assert res.exit_code == 3 and "unknown preset" in res.output
