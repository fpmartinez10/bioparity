# AGENTS.md: working on bioparity

`bioparity` checks that a rewrite of a bioinformatics tool matches the original. README.md says what and why;
this file says how to change it.

## Setup and checks

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
```

Python 3.10+. Dependencies: typer, pydantic, pyyaml. No network is needed for the tests.

## Repo map

- `src/bioparity/cli.py`: commands `init`, `presets`, `run`, `compare`, `selftest`, `report`.
- `spec.py`: `parity.yaml` models and preset loading. `pairing.py`: pair reference and candidate files, apply rules.
- `runner.py`: run both tools (local or Docker). `evidence.py`, `report.py`: evidence.json and the Markdown report.
- `selftest.py`: mutation self-test. `comparators/`: one module per comparator, registered with `@register`.
- `presets/*.yaml`: shared rule sets, ported with attribution (see `NOTICE`). `examples/`: runnable demos. `tests/`.

## Contract

- One issue, one session, one branch named `issue-N-short-slug`, branched off `main`.
- Never commit to or push to `main`. Open a **draft** pull request with `Closes #N`; the maintainer merges.
- Run `git status` first and leave changes you did not make out of your commits.
- Atomic commits in the style `type(scope): what changed` (`feat`, `fix`, `test`, `docs`, `chore`), ending with the
  `Co-Authored-By` trailer given by the session's attribution reminder.
- Every change comes with tests, and `pytest -q` passes before you push.
- Out-of-scope findings are not fixed in passing: open a new issue labelled `parked`.

## Rules for comparators

A comparator needs `compare` (returns a verdict with a one-line summary and examples), `mutations` (deliberate
alterations that must be flagged `divergent`, so `bioparity selftest` covers it) and unit tests. Say which comparison
levels it evaluates (see the README table). Never make a comparator more lenient without a test that shows the
difference it would hide.

## Spending the session well

- Search with Grep or Glob first, then Read with offset and limit. Do not re-read a file you just edited.
- Plan before touching more than two files. Small edits go straight in.
- Answers lead with the result, in labelled parts (Result, Files, Verified, Decide), without recaps or pasted output.
- When the pull request is open, say "done, `/clear` before the next issue".
