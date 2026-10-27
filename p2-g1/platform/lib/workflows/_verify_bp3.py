"""Compact per-file verdict for the bp-3 blueprint range, plus a both-states detector control.

Run from the repo root::

    python platform/lib/workflows/_verify_bp3.py

Prints one line per document (schema verdict, semantic violation count, advisories) and then
runs the KNOWN-BROKEN control: a copy of the first blueprint is mutated in four different
ways, and the checker must reject all four. A verdict of "all green" printed by a checker that
was never shown to fire is worth nothing.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "platform" / "lib"))

from wfdsl import schemas, semantics  # noqa: E402

WORKFLOWS = REPO_ROOT / "platform" / "workflows"


def check(doc: dict[str, Any]) -> tuple[bool, int, int, list[str]]:
    errs = sorted(
        schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    sem = semantics.check_workflow(doc)
    violations = sum(len(r.violations) for r in sem if r.severity == "violation")
    advisories = sum(len(r.violations) for r in sem if r.severity == "advisory")
    detail = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message[:110]}"
        for e in errs[:4]
    ]
    detail += [
        f"{r.rule}: {v[0]} {v[1][:100]}"
        for r in sem
        if r.severity == "violation"
        for v in r.violations[:2]
    ]
    return (not errs), violations, advisories, detail


#: (label, mutate) - each must be REJECTED, proving the checker is not vacuous.
MUTATIONS: list[tuple[str, Any]] = [
    ("unknown-root-key", lambda d: d.__setitem__("totally_unknown_key", 1)),
    ("role-ref-dangles", lambda d: d["stages"][0].__setitem__("role", "no-such-role")),
    (
        "tool-outside-allowlist",
        lambda d: d["stages"][0].__setitem__("tool_permissions", ["Bash:curl"]),
    ),
    (
        "unparseable-expression",
        lambda d: d["stopping_rules"][0].__setitem__("expression", "=== &&& AND"),
    ),
    ("stages-emptied", lambda d: d.__setitem__("stages", [])),
]


def main() -> int:
    paths = sorted(WORKFLOWS.glob("*.workflow.json")) + sorted(
        (WORKFLOWS / "_shared").glob("*.subworkflow.json")
    )
    if not paths:
        print(
            "FAILED:verify-bp3 no documents found - empty walk is a failure, not a pass"
        )
        return 1

    bad: list[str] = []
    print(f"{'document':<62} schema  viol  adv")
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        ok, viol, adv, detail = check(doc)
        print(f"{p.name:<62} {'VALID' if ok else 'INVALID':<7} {viol:<5} {adv}")
        for d in detail:
            print(f"    - {d}")
        if not ok or viol:
            bad.append(p.name)

    # ---- both-states control: the checker MUST fire on a known-broken document
    base = json.loads(paths[0].read_text(encoding="utf-8"))
    control_rows = []
    for label, mutate in MUTATIONS:
        mutant = copy.deepcopy(base)
        mutate(mutant)
        ok, viol, _adv, _d = check(mutant)
        rejected = (not ok) or viol > 0
        control_rows.append((label, rejected))
        print(f"control {label:<26} rejected={rejected}")
    silent = [lbl for lbl, rej in control_rows if not rej]

    if bad:
        print(f"FAILED:verify-bp3 invalid_documents={bad}")
        return 1
    if silent:
        print(f"FAILED:verify-bp3 detector silent on known-broken state: {silent}")
        return 1
    print(
        f"SUCCESS:verify-bp3 documents={len(paths)} all_valid=True "
        f"controls_fired={len(control_rows)}/{len(MUTATIONS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
