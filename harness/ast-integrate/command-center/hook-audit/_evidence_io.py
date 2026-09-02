"""One place that decides whether a probe run may replace a committed evidence file.

THE DEFECT THIS CLOSES (verifier item V3, CONFIRMED, and two siblings found by scanning
for the same shape). Three probes in this directory wrote their partial output over their
committed evidence file on a FAILURE path and then returned non-zero:

    _r4_githygiene_range.py:123   -> R4-GITHYGIENE-RANGE.json
    _r4_budget_ceiling.py:112,142 -> R4-BUDGET-CEILING.json
    _r4_wire_exit.py:160          -> R4-WIRE-EXIT.json

Executed, not inferred (`_b13_destruction_repro.py`): forcing the first one down its
INCONCLUSIVE branch with `GIT_HYGIENE=off` removed SIX top-level keys from the committed
file and took `check_citations.py` from 0 unbacked to 18 unbacked. The evidence was
restored byte-exact afterwards, and the gate returned to its prior state on both axes.

Why it matters more than the key count: re-running a probe is how anyone CHECKS a published
claim. A probe that overwrites its own evidence when it cannot measure punishes verification
and, worse, leaves a file that still LOOKS like a measurement -- `verdict: INCONCLUSIVE` sits
in the same shape as a real result. The next reader cannot tell a failed run from a fixed
one without reading the code.

THE RULE. A committed evidence file may be replaced only by a run that actually measured
something. A failed or inconclusive run writes a sibling `<name>.INCONCLUSIVE.json` and
leaves the committed file untouched. `ok` is the caller's own verdict -- this module
deliberately does not guess it.

The sibling is left UNTRACKED, matching this directory's existing scratch convention. An
earlier draft of this docstring called it "gitignored"; `git check-ignore` exits 1 on it, so
that was wrong. Untracked and ignored are different states and the difference matters here:
the sibling DOES show up in `git status`, which is a feature -- a failed run should be
visible -- but nothing stops someone committing one, so do not treat it as evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

INCONCLUSIVE_SUFFIX = ".INCONCLUSIVE.json"


def inconclusive_path(target: Path) -> Path:
    """Sibling path a non-measuring run writes instead of `target`."""
    return target.with_name(target.name[: -len(".json")] + INCONCLUSIVE_SUFFIX)


def write_evidence(target: Path, payload: dict, *, ok: bool) -> Path:
    """Write `payload` as JSON and return the path actually written.

    ok=True  -> replaces `target` (a real measurement supersedes the previous one).
    ok=False -> writes `inconclusive_path(target)` and does NOT touch `target`.

    The return value is the path written, so a caller can name it in its FAILED: line
    rather than leaving the reader to guess where the partial output went.
    """
    dest = target if ok else inconclusive_path(target)
    dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return dest
