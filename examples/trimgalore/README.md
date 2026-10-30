# Trim Galore 2.x vs 0.6.11

```bash
python make_data.py reads.fq.gz
bioparity run parity.yaml --workdir runs/ --dry-run   # print the docker commands
bioparity run parity.yaml --workdir runs/             # needs a running Docker daemon
```

Container tags were checked against quay.io/biocontainers/trim-galore. The `trimgalore` preset ignores version and
command-line lines in the trimming report; add `accepted_divergences` for any wording changes that are intentional.
