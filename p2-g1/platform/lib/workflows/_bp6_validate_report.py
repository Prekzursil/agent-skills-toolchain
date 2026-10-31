#!/usr/bin/env python
"""Validate every blueprint this unit (blueprints/bp-6) delivered and print the validator's
EXACT per-file verdict.

Run from the repo root::

    python platform/lib/workflows/_bp6_validate_report.py

It is a thin driver over ``platform/lib/wfdsl/validate.py::validate_workflow`` - the SAME
function the CLI ``workflow`` subcommand calls - so this is not a second, laxer checker. Exit
0 only when every file is schema-valid with zero semantic VIOLATIONS (advisories are printed
but do not gate, matching the CLI's own gating rule).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_ROOT = REPO_ROOT / "platform" / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from wfdsl.validate import validate_workflow  # noqa: E402

#: The blueprints this unit owns, in card order. Explicit, not a glob: a glob would silently
#: absorb a sibling unit's file and report a count this unit did not author.
BP6_FILES: list[str] = [
    "security-review-scanner-fix-loop.json",
    "scanner-detector-integrity-probe.json",
    "secret-exposure-blast-radius-trace.json",
    "untrusted-checkout-config-quarantine.json",
    "supply-chain-alert-campaign-fail-closed.json",
    "license-and-rights-governance-register.json",
    "fetched-content-injection-egress-review.json",
    "live-estate-incident-triage.json",
    "dead-feed-recovery-unattended-proof.json",
    "orphaned-run-recovery-from-disk.json",
    "postmortem-failure-entry-distillation.json",
    "revert-gate-rollback-drill.json",
    "deterministic-differ-first-classification.json",
]

WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    names = argv or BP6_FILES
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in names:
        path = WORKFLOW_DIR / name
        if not path.is_file():
            missing.append(name)
            continue
        rows.append(validate_workflow(path))

    if not rows and not missing:
        print("FAILED:bp6-validate no inputs found")
        return 1

    bad: list[str] = list(missing)
    for r in rows:
        ok = r["schema_valid"] and r["semantic_violations"] == 0
        print(
            f"[{'PASS' if ok else 'FAIL'}] {Path(r['workflow']).name:<48} "
            f"schema_valid={r['schema_valid']} violations={r['semantic_violations']} "
            f"advisories={r['semantic_advisories']}"
        )
        for line in r["schema_errors"]:
            print(f"        schema: {line}")
        for rule in r["semantic_rules"]:
            if rule["violations"]:
                tag = "VIOLATION" if rule["severity"] == "violation" else "advisory"
                print(f"        {tag} {rule['rule']} x{rule['violations']}")
                for s in rule["sample"][:3]:
                    print(f"            {s['subject']}: {s['detail'][:180]}")
        if not ok:
            bad.append(Path(r["workflow"]).name)

    for name in missing:
        print(f"[FAIL] {name:<48} FILE NOT FOUND")

    print(f"files_checked={len(rows)} expected={len(names)} failing={len(bad)}")
    if bad:
        print("FAILED:bp6-validate " + ", ".join(sorted(bad)))
        return 1
    print("SUCCESS:bp6-validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
