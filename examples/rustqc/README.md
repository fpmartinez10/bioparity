# Pilot 0: RustQC vs upstream, from committed snapshots

`run_pilot0.sh` clones `seqeralabs/RustQC-benchmarks` and applies the `rustqc-rna` preset (their nf-test tolerances,
expressed as data) to their upstream and RustQC snapshots. No Nextflow, nf-test or containers needed.

Result on the snapshots at the time of writing (2026-10-29): **PASS, 21 outputs (13 identical, 8 equivalent)**, and
`bioparity selftest` catches **73/73** deliberate alterations of those outputs.

To validate on new data (the real contribution), produce upstream and RustQC outputs for another organism or library
type, lay them out like the snapshots (or write a spec with `rename` rules) and run `bioparity compare`.
