"""Write a small synthetic FASTQ with 3' adapters and low-quality tails (reads.fq.gz)."""
import gzip
import random
import sys

random.seed(7)
ADAPTER = "AGATCGGAAGAGC"
out = sys.argv[1] if len(sys.argv) > 1 else "reads.fq.gz"
with gzip.open(out, "wt", compresslevel=6) as fq:
    for i in range(2000):
        insert = "".join(random.choice("ACGT") for _ in range(random.randint(25, 70)))
        seq = (insert + ADAPTER + "".join(random.choice("ACGT") for _ in range(100)))[:100]
        qual = "".join(chr(33 + (36 if j < 80 else random.randint(2, 20))) for j in range(100))
        fq.write(f"@read{i}\n{seq}\n+\n{qual}\n")
print(f"wrote {out}")
