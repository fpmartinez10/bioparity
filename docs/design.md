# bioparity: design and prior art

**Pitch:** `bioparity` is CI for rewrites of bioinformatics tools. It runs the original and the rewrite on the same inputs, compares their outputs with rules that understand each file format, and produces a shareable evidence report that the rewrite matches.

**Why now:**
- AI rewrites are multiplying: RustQC (Apr 2026), Trim Galore v2, fgumi, turbo-picard, SSHash/piscem, salmon in Rust.
- rewrites.bio requires: identical outputs, continuous comparison against upstream, naming the exact upstream version, re-validating on every upstream release, and documented benchmarks.
- There is no shared tooling, so each project rebuilds it.

**Prior art and the gap:**

| Existing | What it does | Why it isn't this |
|---|---|---|
| turbo-picard parity framework | Per-command comparison methods, mutation tests, evidence bundles, 2 reference versions | Picard-only; internal scripts. **Best design reference.** |
| RustQC-benchmarks (MIT) | Nextflow + nf-test suite with per-tool tolerance rules in Groovy (their README marks qualimap/preseq "TBD", but the tests already compare them) | Groovy-in-nf-test; RustQC-specific. **Rules are portable as presets.** |
| fgumi `compare` (MIT) | Feature-gated Rust subcommand (BAM record-key pairing, molecule-join, metrics outer-join) plus a migration guide of known divergences | fgbio-only |
| Trim Galore v2 CI (GPL-3) | md5 of decompressed output vs pinned Perl 0.6.11 | Project-specific shell in CI |
| nf-test (+ nft-* plugins) | Snapshot tests within one implementation | No reference-vs-candidate model, no evidence bundle |
| [nalediym/difftest](https://github.com/nalediym/difftest) (Rust, MIT) | Run two programs on the same args or stdin, compare stdout and exit code with a line diff | No output files or directories, no tolerances, no formats, no containers, no evidence file |
| Bosun "Parity" (development preview) | Generic legacy-vs-replacement behaviour checker (COBOL to Rust example) | Service-behaviour oriented, no tolerance concept, needs a privileged Linux runner |
| FastQC-Rust `tests/equivalence/compare.py` | Own harness: stored Java outputs, text and chart comparison, HTML report, `UPSTREAM.toml` pin plus a nightly job that opens an issue on a new upstream release | Project-specific. Ideas adopted: upstream pin and watcher, plot comparison |
| Tonkaz | Reproducibility levels between workflow runs | Needs Sapporo RO-Crates; workflows, not tool rewrites |
| fieldcompare / dir-content-diff | Generic directory diff with numeric tolerance | Not bioinformatics-aware; no runner or evidence |
| Differential-testing literature (e.g., arXiv 2608.14527, GAMESS) | Protocols | Not packaged tools |

**Originality: MEDIUM.**
- The generic "run two programs and diff the output" idea is not novel (difftest, Bosun Parity, differential-testing literature).
- What was not found is a bioinformatics **output-file** parity tool with format-aware tolerances, shared presets and an evidence report. Today every rewrite project (RustQC-benchmarks, FastQC-Rust, turbo-picard, fgumi, Trim Galore v2) has its own harness.
- The comparison engine is a thin layer. The value is in the shared presets and in adoption, so the plan is to ask maintainers early (see the roadmap) and to stay workflow-agnostic.
- Seqera wrote both RustQC and rewrites.bio and could generalise its validation pipeline; offer the tool to the rewrites.bio effort rather than compete with it.

**Roadmap after the MVP:**
1. BAM/CRAM and VCF comparators (pysam): record multisets, tag subsets, ignoring @PG, as in turbo-picard's normalisation.
2. A MultiQC-compatibility comparator: run MultiQC on both outputs and diff the parsed data.
3. Operational comparison (time, memory, output size), kept separate from correctness.
4. Apptainer backend; a Nextflow backend for HPC-scale case matrices.
5. Testing against several reference versions; a GitHub Action, plus a scheduled job that re-validates when upstream releases.
6. An HTML report and a badge.
7. A public registry of evidence bundles (links to rewrites.bio).

**Pilots:**
0. **Reproduce RustQC-benchmarks' verdicts** from their committed snapshots with the `rustqc-rna` preset (no containers), using the tolerances actually coded in `tests/rna/rustqc/*.nf.test` (not the README table, which is partly stale).
1. Trim Galore 2.x vs 0.6.x (small and fast; the secondary demo).
2. **RustQC vs upstream on non-human data** (mouse, yeast, Arabidopsis; stranded and unstranded; single- and paired-end). This is real validation the RustQC author asked for. File the discrepancies as issues.
3. Offer to port turbo-picard or fgumi evidence into bioparity specs.

**Adoption experiment:**
- Publish the RustQC non-human evidence report.
- Post it in rewrites.bio issue #8, nf-core Slack and the Nextflow forum.
- **Success:** at least one rewrite project adopts a `parity.yaml`, or a maintainer links the evidence.
- **Kill or pivot:** if nobody adopts it, pivot the engine to comparing pipeline outputs across upgrades.

**Risks:**
- **Comparators that are too lenient:** mitigated by mutation self-tests.
- **Scope creep into a general diff framework:** stay focused on reference-vs-candidate evidence.
- **Container and runner complexity:** keep the runner thin; bring-your-own-runs `compare` mode always works.

**Design-doc sources:**
- rewrites.bio: https://rewrites.bio · https://github.com/seqeralabs/rewrites.bio/issues
- RustQC: https://github.com/seqeralabs/RustQC
- turbo-picard parity: https://turbo-picard.readthedocs.io/en/stable/_sources/parity.rst.txt
- fgumi: https://docs.rs/crate/fgumi/0.7.0
- Differential fault injection: https://arxiv.org/html/2608.14527v1

## Existing one-off checks reviewed (reuse findings)

| Project (license) | What the check is | Reusable? | What `bioparity` takes from it |
|---|---|---|---|
| **seqeralabs/RustQC-benchmarks** (MIT) | Separate repo. Nextflow + nf-test suite. Upstream tools run as nf-core modules and snapshotted in `snapshots/rna/small/`. A Groovy `CompareUtils` (`tsvMatch`, `textMatch`) plus per-test inline rules. Actual rules from the tests: dupRadar count columns abs 10 / rel 0.02 (rate and RPKM columns skipped), slope and intercept within 10%; featureCounts gene counts abs 2 / rel 0.01 (coordinate columns skipped), biotype counts rel 0.20 or abs 5; bam_stat and infer_experiment exact text minus headers; read_duplication md5-exact; read_distribution labels and totals exact, fractions loose; inner_distance rel 0.15; junction_annotation exact after row sorting; junction_saturation structural (stochastic); qualimap coverage rel 0.05 / abs 0.5; preseq rel 0.05 / abs 1.0; TIN rel 0.05 / abs 1.0 (file-name column skipped); samtools flagstat and idxstats exact text, stats exact minus `#` lines. | **Rules yes, code no** (Groovy inside nf-test). The committed reference snapshots are directly usable as input. | A `rustqc-rna` preset encoding these rules. The `tsvMatch` options map straight onto my table comparator: abs and rel tolerance where *either* passing is accepted, skip prefixes, skip columns, delimiter, max errors. A **structural** comparator for stochastic outputs. **Value-add over their suite:** same rules, but tool-agnostic YAML with a runner, an evidence report and mutation self-tests. |
| **fulcrumgenomics/fgumi** `compare` (MIT, Rust, feature-gated) | `compare bams` (record-by-record, paired by a record key so a reorder is reported rather than masked; a molecule-join mode where IDs differ legitimately) and `compare metrics` (outer join on key columns, round to precision, then rel/abs tolerance). Per-stage presets (`--command dedup`, etc.). Known divergences are documented in a migration guide. | Ideas yes, code no (Rust, BAM-specific) | Outer-join metrics comparison, order-sound pairing, the *preset-per-command* idea, and `accepted_divergences` (their migration-guide list as data). |
| **dnncha/turbo-picard** `tools/parity_compare.py` (MIT, **Python**) | Metrics: skip `#` comment lines, 1e-5 numeric tolerance. WGS metrics: exact fields vs per-field tolerances. SAM/CRAM via `samtools view`, optionally ignoring MD/NM tags. Evidence bundles (commands, exit codes, both versions, input sha256, JSON+Markdown). Mutation tests prove comparators fail on alterations. | **Closest to reusable** (Python, MIT). Still tied to Picard vocabulary. | Per-field tolerance tables, `samtools view`-based SAM comparison (no pysam dependency at first), the evidence schema, and mutation testing (my `selftest`). Ship a `picard-metrics` preset. Credit in NOTICE. |
| **FelixKrueger/TrimGalore** CI (GPL-3) | CI job installs Perl Trim Galore pinned to the immutable `0.6.11` tag (conda, `cutadapt=5.2` pinned to a build) and compares md5 of the *decompressed* output against Rust. Checked-in `test_files/` plus `*_REFERENCE` outputs. | Idea only (GPL-3, shell in CI) | Gzip-aware identity, pinned-upstream convention. **Do not copy code.** Reimplement the idea. |

**Implications for the design:**
- **Compatibility is the pitch.** `bioparity` can *consume* RustQC-benchmarks' committed upstream snapshots as the reference directory, so it can reproduce their verdicts without running anything.
- **Pilot 0 (no Docker, no HPC):** run `bioparity compare` on their `snapshots/rna/small/` upstream vs RustQC directories with a `rustqc-rna` preset. Success means it reproduces their pass/fail results, and it adds an evidence report, a self-test and a tool-agnostic spec.
- **Then extend:** non-human datasets via `bioparity run`, which is the validation the RustQC author asked for.
- **Presets are the shared asset:** a `presets/` directory of YAML rule sets (rustqc-rna, picard-metrics, trimgalore, fgumi-metrics) that rewrite projects can contribute to, keeping their own tolerances as data rather than code.
- **Licensing:** ported rules come from MIT projects with attribution in NOTICE. Nothing is copied from GPL-3 sources. Contact the authors before publishing presets derived from their tolerances.
- **Outreach:** propose to the RustQC-benchmarks, fgumi and turbo-picard maintainers that their specs live in `bioparity` format; it reduces their maintenance.
