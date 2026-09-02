#!/usr/bin/env python3
"""Named probe 2 (IMP-0081): ASSERTED vs VERIFIED surfaces, mismatch, local './'.

Independent of probe 1's planted repo:
  * unreachable upstream is ASSERTED, never VERIFIED
  * ASSERTED and VERIFIED render differently on every surface
  * mismatched commit is not recorded as VERIFIED (negative control)
  * local './' does not crash and is first-party-local, not federated-verified
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.federated_identity import (  # noqa: E402
    BADGE_ASSERTED,
    BADGE_VERIFIED,
    STATUS_ASSERTED,
    STATUS_FIRST_PARTY_LOCAL,
    STATUS_MISMATCH,
    STATUS_VERIFIED,
    ScriptedResolver,
    UnreachableUpstream,
    map_identity,
    map_index,
    record_in_index,
    surfaces_distinguish,
)

ART = REPO / "command-center" / "receipts" / "IMP-0081.json"
FIX = HERE / "fixtures" / "marketplace.json"
PLANTED = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
GIT_SRC = "https://github.com/acme/federated-pkg.git#v1.2.3"


def _require_receipt() -> str:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0081-probe2 receipt missing")
        raise SystemExit(1)
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0081-probe2 receipt unparseable {exc}")
        raise SystemExit(1)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0081-probe2 self-declared {doc.get('state')}")
        raise SystemExit(1)
    if "SUCCESS:IMP-0081" not in text:
        print("FAILED:IMP-0081-probe2 sentinel absent")
        raise SystemExit(1)
    return text


def _no_sleep(_s: float) -> None:
    return None


def main() -> int:
    _require_receipt()

    verified = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([PLANTED]),
        sleeper=_no_sleep,
    )
    asserted = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([UnreachableUpstream("probe2-unreachable")]),
        sleeper=_no_sleep,
    )
    if verified.status != STATUS_VERIFIED or asserted.status != STATUS_ASSERTED:
        print(
            f"FAILED:IMP-0081-probe2 statuses verified={verified.status} "
            f"asserted={asserted.status}"
        )
        return 1
    if asserted.badge == verified.badge or asserted.badge == BADGE_VERIFIED:
        print("FAILED:IMP-0081-probe2 ASSERTED badge collides with VERIFIED")
        return 1
    if asserted.badge != BADGE_ASSERTED:
        print(f"FAILED:IMP-0081-probe2 asserted badge {asserted.badge}")
        return 1
    diff = surfaces_distinguish(verified, asserted)
    if not diff.get("distinguished") or diff.get("identical_surfaces"):
        print(f"FAILED:IMP-0081-probe2 surfaces not distinguished {diff}")
        return 1

    mismatch = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([OTHER]),
        sleeper=_no_sleep,
    )
    attached = record_in_index({"name": "federated-pkg"}, mismatch)
    if mismatch.status != STATUS_MISMATCH:
        print(f"FAILED:IMP-0081-probe2 mismatch status={mismatch.status}")
        return 1
    if attached["federated_identity"]["status"] == STATUS_VERIFIED:
        print("FAILED:IMP-0081-probe2 mismatch recorded as VERIFIED")
        return 1

    local = map_identity("ast-integrate", "./")
    if local.status != STATUS_FIRST_PARTY_LOCAL or local.first_party is not True:
        print(f"FAILED:IMP-0081-probe2 local './' {local.to_dict()}")
        return 1
    if local.verified:
        print("FAILED:IMP-0081-probe2 local './' marked VERIFIED")
        return 1

    fixture = json.loads(FIX.read_text(encoding="utf-8"))
    mapped = map_index(
        fixture,
        resolver=ScriptedResolver([PLANTED]),
        sleeper=_no_sleep,
    )
    local_block = mapped["plugins"][0]["federated_identity"]
    git_block = mapped["plugins"][1]["federated_identity"]
    if local_block["status"] != STATUS_FIRST_PARTY_LOCAL:
        print(f"FAILED:IMP-0081-probe2 fixture local {local_block}")
        return 1
    if git_block["status"] != STATUS_VERIFIED:
        print(f"FAILED:IMP-0081-probe2 fixture git {git_block}")
        return 1
    if local_block == git_block:
        print("FAILED:IMP-0081-probe2 fixture blocks identical")
        return 1

    payload = {
        "asserted_status": asserted.status,
        "distinguished": True,
        "fixture_local": local_block["status"],
        "fixture_git": git_block["status"],
        "local_dot_slash": local.status,
        "mismatch_index_status": attached["federated_identity"]["status"],
        "mismatch_not_verified": True,
        "pass": True,
        "probe": "probe2-asserted-mismatch-local",
        "unit_id": "IMP-0081",
        "verified_status": verified.status,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "asserted_distinct=True mismatch_not_verified=True "
        "local_dot_slash_ok=True"
    )
    print("SUCCESS:IMP-0081-probe2 ASSERTED distinguishable; mismatch refused; ./ handled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
