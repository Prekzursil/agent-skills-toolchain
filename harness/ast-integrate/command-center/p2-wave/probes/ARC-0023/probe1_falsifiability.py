#!/usr/bin/env python3
"""Probe 1: falsifiability without publishing, against the A3 claim extract.

Working vs missing-blob fixture markets must disagree. Public publish stays
BLOCKED. Stopping condition 13 is UNSATISFIABLE-AS-WRITTEN. Observable
counts in REFUTATION.json must match the live run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A3/REFUTATION.json"
CLAIM = REPO / "command-center/phase3/A3/CLAIM-UNDER-TEST.json"


def main() -> int:
    run = S.run_scenario()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:ARC-0023-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0023-probe1 REFUTATION.json missing")
        return 1
    if not CLAIM.is_file():
        print("FAILED:ARC-0023-probe1 CLAIM-UNDER-TEST.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0023-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("falsifiable_without_publish") is True
        and rec.get("distinguishes_working_from_broken_without_publish") is True
        and rec.get("publish_public_blocked") is True
        and rec.get("condition_13_unsatisfiable_as_written") is True
    )
    if not rec_ok:
        print("FAILED:ARC-0023-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0023-probe1 procedure too short")
        return 1
    silent = str((doc.get("scenario") or {}).get("silent_loss_file") or "")
    if not silent.startswith("command-center/phase3/A3/CLAIM-UNDER-TEST.json:"):
        print(f"FAILED:ARC-0023-probe1 silent_loss_file not CLAIM: {silent}")
        return 1
    try:
        line = int(silent.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        print(f"FAILED:ARC-0023-probe1 silent_loss_file not file:line {silent}")
        return 1
    clines = CLAIM.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(clines):
        print("FAILED:ARC-0023-probe1 CLAIM line oob")
        return 1
    hit = clines[line - 1]
    if "silent" not in hit.lower() and "never observed" not in hit.lower() and "unobserv" not in hit.lower():
        print("FAILED:ARC-0023-probe1 CLAIM line does not name unobservability")
        return 1
    art_obs = doc.get("observables") or {}
    live_n = int(run["observable_count"])
    live_ids = list(run["observable_ids"])
    if int(art_obs.get("count") or 0) != live_n:
        print("FAILED:ARC-0023-probe1 artifact observable count != live")
        return 1
    if list(art_obs.get("ids") or []) != live_ids:
        print("FAILED:ARC-0023-probe1 artifact observable ids != live")
        return 1
    if live_n < 1:
        print("FAILED:ARC-0023-probe1 no observables")
        return 1
    if doc.get("falsifiability_verdict") != "FALSIFIABLE-WITHOUT-PUBLISH":
        print("FAILED:ARC-0023-probe1 expected FALSIFIABLE-WITHOUT-PUBLISH")
        return 1
    if str((doc.get("stopping_condition_13") or {}).get("verdict")) != "UNSATISFIABLE-AS-WRITTEN":
        print("FAILED:ARC-0023-probe1 condition 13 not UNSATISFIABLE-AS-WRITTEN")
        return 1
    if "never a public marketplace release" not in str(doc.get("pr_only_quote") or ""):
        print("FAILED:ARC-0023-probe1 PR-ONLY quote missing")
        return 1
    if "SUCCESS:ARC-0023" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0023-probe1 sentinel absent")
        return 1
    print(
        "falsifiable="
        f"{bool(run.get('falsifiable_without_publish'))} "
        f"distinguish={bool(run.get('distinguishes_working_from_broken_without_publish'))} "
        f"observables={live_n}"
    )
    print("SUCCESS:ARC-0023-probe1 falsifiability-without-publish reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
