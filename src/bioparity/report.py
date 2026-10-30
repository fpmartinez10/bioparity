"""Markdown report with a parity matrix (outputs x cases)."""

from __future__ import annotations

ICON = {"identical": "✅", "equivalent": "✅", "accepted": "🟡", "divergent": "❌",
        "missing": "⚠️", "extra": "⚠️", "error": "💥"}


def cell(verdict: str | None) -> str:
    return "—" if verdict is None else f"{ICON[verdict]} {verdict}"


def render(evidence: dict) -> str:
    cases = evidence["cases"]
    ref, cand = evidence.get("reference", {}), evidence.get("candidate", {})
    out = [f"# Parity report: {evidence['spec']}", ""]
    out.append(f"- **Reference:** {ref.get('label', 'n/a')} {ref.get('version', '')}".rstrip())
    out.append(f"- **Candidate:** {cand.get('label', 'n/a')} {cand.get('version', '')}".rstrip())
    out.append(f"- **Created:** {evidence['created']} (bioparity {evidence['bioparity_version']})")
    summary = ", ".join(f"{n} {v}" for v, n in evidence["summary"].items()) or "no outputs compared"
    status = "PASS" if evidence["exit_code"] == 0 else "FAIL"
    out += [f"- **Result:** {status} (exit code {evidence['exit_code']}): {summary}", ""]

    paths = sorted({r["path"] for c in cases for r in c["results"]})
    out += ["## Parity matrix", "", "| output | " + " | ".join(c["id"] for c in cases) + " |",
            "|---|" + "---|" * len(cases)]
    for p in paths:
        row = []
        for c in cases:
            match = next((r for r in c["results"] if r["path"] == p), None)
            row.append(cell(match["verdict"] if match else None))
        out.append(f"| `{p}` | " + " | ".join(row) + " |")

    problems = [(c["id"], r) for c in cases for r in c["results"] if r["verdict"] in ("divergent", "missing", "extra", "error", "accepted")]
    if problems:
        out += ["", "## Details", ""]
        for case_id, r in problems:
            out.append(f"### {cell(r['verdict'])} `{r['path']}` ({case_id}, comparator `{r['comparator']}`)")
            out.append(r["summary"] + (f". Accepted: {r['note']}" if r["note"] else ""))
            if r["examples"]:
                out += ["", "```"] + r["examples"] + ["```"]
            out.append("")
    runs = [(c["id"], c["runs"]) for c in cases if c.get("runs")]
    if runs:
        out += ["## Commands", ""]
        for case_id, r in runs:
            for side in ("reference", "candidate"):
                if side in r:
                    out.append(f"- `{case_id}` {side}: `{r[side]['command']}` (exit {r[side]['exit_code']}, {r[side]['seconds']}s)")
    return "\n".join(out) + "\n"
