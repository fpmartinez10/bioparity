# bioparity

**Evidence that a rewrite of a bioinformatics tool matches the original.**

AI makes rewriting a tool in a new language cheap (RustQC, Trim Galore v2, fgumi, turbo-picard and more).
The hard part is proving the rewrite gives the same results. Today every rewrite project builds its own
one-off comparison scripts. `bioparity` is a shared, tool-agnostic harness: it runs the original and the rewrite on
the same inputs (or compares outputs you already have), applies format-aware comparison rules with explicit
tolerances, and ends with **a report that lists every check that was made**.

> Status: early (v0.1 MVP). The core runs and is tested; several features below are planned and tracked as
> [issues](https://github.com/fpmartinez10/bioparity/issues).

## What a PASS means, and what it does not

A PASS says: *on the inputs you tested, and under the rules in your spec, the rewrite's outputs matched the
original's.* It is evidence, not a proof. It cannot catch behaviour you did not test, and a tolerance that is too
loose will hide a real difference. That is why every comparison is reported with the level it was checked at,
the tolerance used, and the largest deviation seen, and why `bioparity selftest` alters your reference outputs on
purpose to check that your rules would notice.

Following [rewrites.bio](https://rewrites.bio): name the exact upstream version you validated against, re-validate
when upstream releases, and keep outputs compatible.

## Who it is for

- Authors of rewrites or ports who want to show users and maintainers that outputs match.
- Pipeline maintainers deciding whether a rewritten tool is safe to swap in.
- Anyone checking that a tool upgrade or a migration did not change results.

## Comparison levels

Every compared file gets a check at each level that applies. The report will show which levels were checked and
which were not (a level matrix; issue #3).

| # | Level | What it checks | Status |
|---|---|---|---|
| 1 | Byte identity | SHA-256 of both files | Implemented (`exact`); BLAKE3 later |
| 2 | Normalised identity | Decompress, drop volatile lines (versions, timestamps, command lines), canonical line endings, optional sort | Partly (`text`, `table`, `fastq`); shared block planned (#4) |
| 3 | Structural equivalence | Same files, samples, columns, record counts, output categories | Partly (`structural`, missing/extra files); manifest checks planned (#5) |
| 4 | Semantic equivalence | Format-aware record comparison | FASTQ and regex-extracted fields today; SAM/BAM/CRAM, VCF, MultiQC data planned (#15, #16, #17) |
| 5 | Numerical equivalence | Absolute and relative tolerances, maximum deviation | Tolerances implemented; deviation summary in the report planned (#6) |
| 6 | Statistical equivalence | Correlations, distributions, set concordance where exact equality is not expected | Planned (#18) |
| 7 | Operational comparison | Runtime, peak memory, output size (reported separately; never affects pass/fail) | Wall time per run today; schema and report section planned (#7), Nextflow trace and Slurm imports (#29) |

## Verdicts and exit codes

| Verdict | Meaning | Exit |
|---|---|---|
| identical | byte-for-byte the same | 0 |
| equivalent | same after normalisation or within tolerance | 0 |
| accepted | differs, but listed under `accepted_divergences` with a reason | 0 |
| divergent | differs beyond tolerance | 1 |
| missing / extra | an output exists on one side only | 2 |
| error | a run or a comparison failed | 3 |

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q

bioparity presets                                   # shared rule presets and comparators
bioparity init                                      # write a template parity.yaml
bioparity run parity.yaml --workdir runs/           # run both tools (Docker), compare, write the report
bioparity compare REF_DIR CAND_DIR --preset NAME    # compare outputs you already have
bioparity selftest REF_DIR --preset NAME            # prove the rules catch deliberate alterations
```

`bioparity run` writes `evidence.json` (versions, commands, hashes, per-file verdicts) and `report.md` (a parity
matrix plus details of every non-passing file).

## Tests and datasets

- **Unit tests** (`pytest`, under a second): comparators, pairing, verdicts, CLI.
- **Pilot 0** (`examples/rustqc/run_pilot0.sh`, needs network): applies the `rustqc-rna` preset to the snapshots
  committed in RustQC-benchmarks. Last result: 21 outputs pass (13 identical, 8 within tolerance); `selftest`
  catches 73 of 73 deliberate alterations.
- **Tiny end-to-end test** (planned, #2): a few-KB synthetic dataset and a toy original/rewrite pair with known
  differences, run through the whole flow with the report checked against a golden file. No Docker needed.
- **Real end-to-end tests** (planned, #14 and #24): RustQC against the original RNA-seq QC tools, first on a small
  human chr6 dataset on a laptop, then a full-size run on a cluster, each ending in a full report.

## Roadmap

- **v0.2 foundation:** CI, tiny datasets and golden report, per-level checks and the level matrix, shared
  normalisation, manifest checks, deviation summaries, operational section, friendlier errors, docs.
- **v0.3 formats and pilots:** multi-step references (several upstream tools replaced by one rewrite), SAM/BAM/CRAM,
  VCF, MultiQC data, statistical comparator, Apptainer backend, reference-version matrix and upstream watcher, the
  RustQC small end-to-end run and non-human validation.
- **v1.0 release:** full-size cluster run with a published report, HTML report and badge, PyPI and Bioconda.

## Contributing

Work is tracked in issues, sized to fit one focused session each. `AGENTS.md` describes the workflow (branch per
issue, tests with every change, draft pull requests). A new comparator needs `compare`, `mutations` (so `selftest`
covers it) and tests.

## Prior art

| Tool | What it is | How `bioparity` differs |
|---|---|---|
| [difftest](https://github.com/nalediym/difftest) | Run two programs on the same input, compare stdout and exit code | `bioparity` compares output files and directories with tolerances and formats |
| Bosun "Parity" | Generic legacy-vs-replacement behaviour checks | Not bioinformatics file formats, no tolerance concept |
| RustQC-benchmarks, FastQC-Rust, turbo-picard, fgumi `compare` | Per-project parity harnesses | Project-specific; `bioparity` turns their rules into shareable presets |
| nf-test, Tonkaz, fieldcompare | Snapshot tests, workflow reproducibility levels, generic directory diff | Different scope; see [docs/design.md](docs/design.md) |

Rules in `src/bioparity/presets/` are ported with attribution (see `NOTICE`).

## License

MIT
