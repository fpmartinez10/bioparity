import gzip
from pathlib import Path

import pytest

from bioparity import comparators
from bioparity.comparators.base import Verdict, exit_code


def w(path: Path, text: str, gz: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode()
    path.write_bytes(gzip.compress(data, mtime=1) if gz else data)
    return path


def cmp(name, a, b, **opts):
    return comparators.get(name).compare(a, b, opts)


def test_exact_identical_and_gzip_equivalent(tmp_path):
    a = w(tmp_path / "a.gz", "hello\n", gz=True)
    b = tmp_path / "b.gz"
    b.write_bytes(gzip.compress(b"hello\n", mtime=99))  # different header bytes, same content
    assert cmp("exact", a, a).verdict == Verdict.IDENTICAL
    assert cmp("exact", a, b).verdict == Verdict.EQUIVALENT
    w(b, "hellO\n", gz=True)
    assert cmp("exact", a, b).verdict == Verdict.DIVERGENT


def test_text_ignores_lines_and_sorts(tmp_path):
    a = w(tmp_path / "a", "version 1\nb\na\n")
    b = w(tmp_path / "b", "version 2\na\nb\n")
    assert cmp("text", a, b, ignore_lines=["^version"], sort=True).verdict == Verdict.EQUIVALENT
    assert cmp("text", a, b, ignore_lines=["^version"]).verdict == Verdict.DIVERGENT


def test_table_tolerance_either_bound(tmp_path):
    a = w(tmp_path / "a", "id\tv\nx\t100\ny\t0\n")
    b = w(tmp_path / "b", "id\tv\nx\t101\ny\t0.4\n")
    assert cmp("table", a, b, key=["id"], rtol=0.02, atol=0.5).verdict == Verdict.EQUIVALENT
    r = cmp("table", a, b, key=["id"], rtol=0.001)
    assert r.verdict == Verdict.DIVERGENT and "col v" in r.examples[0]


def test_table_key_missing_and_ignore_columns(tmp_path):
    a = w(tmp_path / "a", "id\tv\tnoise\nx\t1\t5\ny\t2\t6\n")
    b = w(tmp_path / "b", "id\tv\tnoise\nx\t1\t9\n")
    r = cmp("table", a, b, key=["id"], ignore_columns=["noise"])
    assert r.verdict == Verdict.DIVERGENT and any("only in reference" in e for e in r.examples)
    c = w(tmp_path / "c", "id\tv\tnoise\ny\t2\t0\nx\t1\t9\n")
    assert cmp("table", a, c, key=["id"], ignore_columns=["noise"]).verdict == Verdict.EQUIVALENT


def test_table_ignore_order_and_nan(tmp_path):
    a = w(tmp_path / "a", "h\nb\tNaN\na\t1\n")
    b = w(tmp_path / "b", "h\na\t1\nb\tNaN\n")
    assert cmp("table", a, b, ignore_order=True).verdict == Verdict.EQUIVALENT
    assert cmp("table", a, b).verdict == Verdict.DIVERGENT


def test_metrics_skips_comment_blocks(tmp_path):
    a = w(tmp_path / "a", "## header\n# started 1\nX\tY\n1\t0.123456\n")
    b = w(tmp_path / "b", "## header\n# started 2\nX\tY\n1\t0.123457\n")
    assert cmp("metrics", a, b, atol=1e-5).verdict == Verdict.EQUIVALENT
    assert cmp("metrics", a, b, atol=1e-8).verdict == Verdict.DIVERGENT


def test_structural_labels_and_rows(tmp_path):
    a = w(tmp_path / "a", "g1\t1\ng2\t2\n")
    b = w(tmp_path / "b", "g2\t9\ng1\t8\n")
    assert cmp("structural", a, b, key=0).verdict == Verdict.EQUIVALENT
    c = w(tmp_path / "c", "g1\t1\ng3\t2\n")
    assert cmp("structural", a, c, key=0).verdict == Verdict.DIVERGENT


def test_fastq_ordered_and_multiset(tmp_path):
    r1, r2 = "@a\nACGT\n+\nIIII\n", "@b\nTTTT\n+\nIIII\n"
    a = w(tmp_path / "a.fq.gz", r1 + r2, gz=True)
    b = w(tmp_path / "b.fq", r2 + r1)
    assert cmp("fastq", a, b).verdict == Verdict.DIVERGENT
    assert cmp("fastq", a, b, ordered=False).verdict == Verdict.EQUIVALENT


def test_fields_with_rtol(tmp_path):
    a = w(tmp_path / "a", "slope: 1.00\ny=c(1,2,3)\n")
    b = w(tmp_path / "b", "slope: 1.05\ny=c(9,9,3)\n")
    fields = [{"name": "slope", "regex": r"slope: (\S+)", "rtol": 0.1},
              {"name": "y100", "regex": r"^y=c\((.*)\)$", "split": ",", "pick": "last"}]
    assert cmp("fields", a, b, fields=fields).verdict == Verdict.EQUIVALENT
    fields[0]["rtol"] = 0.01
    assert cmp("fields", a, b, fields=fields).verdict == Verdict.DIVERGENT


def test_exit_codes():
    assert exit_code(["identical", "equivalent", "accepted"]) == 0
    assert exit_code(["identical", "divergent"]) == 1
    assert exit_code(["divergent", "missing"]) == 2
    assert exit_code(["missing", "error"]) == 3
