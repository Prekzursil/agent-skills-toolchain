#!/usr/bin/env python3
"""Probe 2: never-forward env canary + fail-open detector control.

Two leak signals must agree. Overclaim check requires DESIGN and SENTENCE
loci. Mutating a REFUTED row to drop defect_locus must fail the checker.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import never_forward as NF  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/phase3/A6/SECURITY.json"


def main() -> int:
    live = NF.run_never_forward()
    printable = {k: live[k] for k in sorted(live)}
    print(json.dumps(printable, sort_keys=True))
    if not live.get("pass"):
        print("FAILED:ARC-0041-probe2 never-forward did not pass")
        return 1
    if live["walk_closed_leaks"] or live["dump_closed_leaks"]:
        print("FAILED:ARC-0041-probe2 canary leaked on fail-closed path")
        return 1
    if not live["signals_agree_closed"] or not live["signals_agree_open"]:
        print("FAILED:ARC-0041-probe2 leak signals disagree (BLOCKED, not picked)")
        return 1
    if not live["fail_open_mutant_leaks_canary"]:
        print("FAILED:ARC-0041-probe2 fail-open mutant did not leak canary")
        return 1
    if live["forbidden_payload_keys"]:
        print(f"FAILED:ARC-0041-probe2 forbidden keys {live['forbidden_payload_keys']}")
        return 1
    if live["argv_forwarded"] or live["env_copied"]:
        print("FAILED:ARC-0041-probe2 argv or env copied to outbound")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0041-probe2 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0041-probe2 self-declared {doc.get('state')}")
        return 1
    rec = doc.get("never_forward") or {}
    checks = (
        ("fail_closed_clean", True),
        ("fail_open_mutant_leaks_canary", True),
        ("signals_agree_closed", True),
        ("walk_closed_leaks", False),
        ("dump_closed_leaks", False),
        ("argv_forwarded", False),
        ("env_copied", False),
    )
    for key, want in checks:
        if rec.get(key) is not want or live.get(key) is not want:
            print(f"FAILED:ARC-0041-probe2 {key} rec={rec.get(key)} live={live.get(key)}")
            return 1

    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0041-probe2 overclaim check failed on artifact")
        return 1
    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0041-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0041-probe2 mutant without defect_locus was accepted")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live_ev = 0
    for row in evidence:
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok_a, why_a = A.resolve_anchor(REPO, rel, line, snippet)
        if not ok_a:
            print(f"FAILED:ARC-0041-probe2 anchor {why_a}")
            return 1
        if row.get("kind") == "dossier":
            dossier += 1
        elif row.get("kind") == "live-tree":
            live_ev += 1
    if dossier < 3 or live_ev < 1:
        print(f"FAILED:ARC-0041-probe2 evidence dossier={dossier} live={live_ev}")
        return 1
    if "SUCCESS:ARC-0041" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0041-probe2 sentinel absent")
        return 1
    if doc.get("adv_rebuild_circle") is True:
        print("FAILED:ARC-0041-probe2 ADV rebuild circle")
        return 1
    print(
        f"canary_absent={not live['walk_closed_leaks']} "
        f"fail_open_leaks={live['fail_open_mutant_leaks_canary']} "
        f"stripped={live['never_forward_stripped']}"
    )
    print("SUCCESS:ARC-0041-probe2 never-forward env canary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
