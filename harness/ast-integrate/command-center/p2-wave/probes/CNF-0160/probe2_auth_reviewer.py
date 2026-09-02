#!/usr/bin/env python3
"""Probe 2: read-only whoami, missing-rail NOT-CHECKED, reviewer of non-escalated."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from recruit import (  # noqa: E402
    apply_rule,
    independent_should_escalate,
    load_ledger,
    load_thirds,
)
from rule import DEFAULT_BUDGET_CAP, NOT_CHECKED  # noqa: E402
from whoami import diagnose, snapshot_env, snapshots_equal  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0160.json"
WHOAMI_SRC = HERE / "whoami.py"

FORBIDDEN_SNIPPETS = (
    "os.unsetenv(",
    "os.environ.pop(",
    "os.environ.setdefault(",
    "os.putenv(",
    "cursor-agent logout",
    "cursor-agent login",
    "--api-key",
)


def main() -> int:
    src = WHOAMI_SRC.read_text(encoding="utf-8")
    for snip in FORBIDDEN_SNIPPETS:
        if snip in src:
            print(f"FAILED:CNF-0160-probe2 whoami source contains {snip!r}")
            return 1

    before = snapshot_env()
    posture = diagnose()
    after = snapshot_env()
    if not snapshots_equal(before, after) or posture.get("credential_mutated"):
        print("FAILED:CNF-0160-probe2 credential env mutated")
        return 1
    if posture.get("credential_created") or posture.get("credential_rotated") or posture.get(
        "credential_unset"
    ):
        print("FAILED:CNF-0160-probe2 credential lifecycle touched")
        return 1
    who = posture.get("cursor_whoami") or {}
    if who.get("ran") and who.get("argv") != ["cursor-agent", "whoami", "--format", "json"]:
        print("FAILED:CNF-0160-probe2 unexpected whoami argv", who.get("argv"))
        return 1
    if who.get("credential_printed"):
        print("FAILED:CNF-0160-probe2 whoami printed a credential")
        return 1

    # Live third rails: this tree has none. Must not invent availability.
    if posture.get("third_rail_available") is True:
        print("FAILED:CNF-0160-probe2 unexpected live third rail")
        return 1
    if posture.get("missing_prerequisite") != "third-vendor-rail-unauthenticated":
        print(
            "FAILED:CNF-0160-probe2 missing_prerequisite",
            posture.get("missing_prerequisite"),
        )
        return 1

    ledger = load_ledger()
    thirds = load_thirds()
    missing = apply_rule(
        ledger, thirds, rail_available=False, cap=DEFAULT_BUDGET_CAP
    )
    if missing["two_way_fallback_anywhere"]:
        print("FAILED:CNF-0160-probe2 two-way fallback on missing rail")
        return 1
    qualified = [
        e
        for e in missing["evaluations"]
        if e["clauses"]["vendors_disagree"]
        and e["clauses"]["cnf0155_unsettled_irreducible"]
    ]
    if len(qualified) < 5:
        print("FAILED:CNF-0160-probe2 expected >=5 IRREDUCIBLE disagreements")
        return 1
    for ev in qualified:
        if ev.get("triangulation_outcome") != NOT_CHECKED:
            print("FAILED:CNF-0160-probe2 missing-rail not NOT-CHECKED", ev)
            return 1
        if ev.get("missing_prerequisite") != "third-vendor-rail-unauthenticated":
            print("FAILED:CNF-0160-probe2 unnamed prerequisite", ev)
            return 1
        if ev.get("recruited"):
            print("FAILED:CNF-0160-probe2 recruited without rail", ev["claim_id"])
            return 1
        if ev.get("two_way_fallback_used"):
            print("FAILED:CNF-0160-probe2 two-way on", ev["claim_id"])
            return 1
        # Must not collapse to either vendor as a verdict.
        if ev.get("triangulation_outcome") in {
            ev.get("anthropic_verdict"),
            ev.get("codex_verdict"),
        }:
            print("FAILED:CNF-0160-probe2 two-way collapse", ev["claim_id"])
            return 1

    # Reviewer: re-derive trigger for every non-escalated claim on the WITH-rail run.
    live = apply_rule(ledger, thirds, rail_available=True, cap=DEFAULT_BUDGET_CAP)
    missed = []
    for ev in live["evaluations"]:
        if ev["recruited"]:
            continue
        entry = {
            "claim_id": ev["claim_id"],
            "anthropic_verdict": ev["anthropic_verdict"],
            "codex_verdict": ev["codex_verdict"],
            "cnf0155_outcome": ev["cnf0155_outcome"],
            "tiebreak_test_id": ev.get("tiebreak_test_id"),
        }
        should = independent_should_escalate(
            entry, budget_remaining=int(ev["budget_remaining_before"])
        )
        if should and live["rail_available"] and not ev["recruited"]:
            missed.append(ev["claim_id"])
        if should != bool(ev["trigger_fired"]):
            missed.append(f"desync:{ev['claim_id']}")
    if missed:
        print("FAILED:CNF-0160-probe2 missed trigger", missed)
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0160-probe2 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0160" not in json.dumps(receipt):
        print("FAILED:CNF-0160-probe2 sentinel absent")
        return 1
    rec_auth = receipt.get("auth_posture") or {}
    if rec_auth.get("credential_mutated") is True:
        print("FAILED:CNF-0160-probe2 receipt claims mutation")
        return 1
    if rec_auth.get("third_rail_available") is True:
        print("FAILED:CNF-0160-probe2 receipt overclaims third rail")
        return 1
    live_missing = receipt.get("missing_rail_run") or {}
    if int(live_missing.get("not_checked_count") or 0) < 5:
        print("FAILED:CNF-0160-probe2 receipt missing-rail run thin")
        return 1

    src_fp = (receipt.get("source_probe") or {}).get("fingerprint")
    ver_fp = (receipt.get("verifier_probe") or {}).get("fingerprint")
    if not src_fp or not ver_fp or src_fp == ver_fp:
        print("FAILED:CNF-0160-probe2 probe fingerprints not distinct")
        return 1

    summary = {
        "probe": "probe2-auth-reviewer",
        "unit_id": "CNF-0160",
        "whoami_ran": bool(who.get("ran")),
        "whoami_authenticated": bool(who.get("authenticated")),
        "credential_mutated": False,
        "third_rail_available": False,
        "missing_rail_not_checked": len(qualified),
        "missed_triggers": [],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"whoami_ran={who.get('ran')} auth={who.get('authenticated')} "
        f"third_rail={posture.get('third_rail_available')} "
        f"not_checked={len(qualified)} missed=0"
    )
    print("SUCCESS:CNF-0160-probe2 auth whoami, missing-rail NOT-CHECKED, reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
