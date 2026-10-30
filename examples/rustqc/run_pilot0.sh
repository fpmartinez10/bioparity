#!/usr/bin/env bash
# Pilot 0: reproduce the RustQC-benchmarks verdicts from their committed snapshots (no containers).
# Usage: run_pilot0.sh [scratch_dir]    (defaults to a fresh temp dir; the clone is never committed here)
set -euo pipefail
scratch="${1:-$(mktemp -d)}"
git clone --depth 1 https://github.com/seqeralabs/RustQC-benchmarks.git "$scratch/RustQC-benchmarks"
snap="$scratch/RustQC-benchmarks/snapshots/rna/small"
bioparity compare "$snap" "$snap/rustqc" --preset rustqc-rna \
  --json "$scratch/evidence.json" --report "$scratch/report.md"
bioparity selftest "$snap" --preset rustqc-rna
echo "evidence: $scratch/evidence.json  report: $scratch/report.md"
