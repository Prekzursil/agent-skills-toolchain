#!/usr/bin/env python3
"""Probe 1: blocked vs unblocked both completed; destinations attached; network is the variable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402
import schema_local as SCH  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0106-probe1 {msg}")
    return 1


def main() -> int:
    m = H.measure()
    bw, uw = m["blocked_warm"], m["unblocked_warm"]
    bc, uc = m["blocked_cold"], m["unblocked_cold"]
    print(f"blocked_warm_completed={bw['completed']} unblocked_warm_completed={uw['completed']}")
    print(f"blocked_cold_completed={bc['completed']} unblocked_cold_completed={uc['completed']}")
    if not (bw["completed"] and uw["completed"] and bc["completed"] and uc["completed"]):
        return fail("a run did not complete")

    herm_b = H.step(bw, "test_genuinely_hermetic")
    herm_u = H.step(uw, "test_genuinely_hermetic")
    lie_b = H.step(bw, "test_claims_offline_but_fetches")
    lie_u = H.step(uw, "test_claims_offline_but_fetches")
    cache_bw = H.step(bw, "test_cache_reverify")
    cache_bc = H.step(bc, "test_cache_reverify")
    cache_uc = H.step(uc, "test_cache_reverify")
    inst_bw = H.step(bw, "install")
    inst_bc = H.step(bc, "install")
    inst_uc = H.step(uc, "install")

    print(f"hermetic blocked={herm_b['ok']} unblocked={herm_u['ok']}")
    print(f"lying blocked={lie_b['ok']} unblocked={lie_u['ok']} dests_b={lie_b['attempted_destinations']}")
    print(f"cache warm_blocked={cache_bw['ok']} cold_blocked={cache_bc['ok']} cold_unblocked={cache_uc['ok']}")
    print(f"install warm_blocked={inst_bw['ok']} cold_blocked={inst_bc['ok']} cold_unblocked={inst_uc['ok']}")

    if not herm_b["ok"] or not herm_u["ok"]:
        return fail("hermetic test is not stable across both states")
    if lie_b["ok"]:
        return fail("known-broken offline-claim test passed under block")
    if not lie_u["ok"]:
        return fail("unblocked control did not pass the network-using test")
    if not lie_b["attempted_destinations"]:
        return fail("blocked lying test recorded no destination")
    if not cache_bw["ok"]:
        return fail("warm cache + blocked should pass reverify")
    if cache_bc["ok"] or not cache_bc["attempted_destinations"]:
        return fail("cold cache + blocked did not fail-and-log destination")
    if not cache_uc["ok"]:
        return fail("cold cache + unblocked should pass (network is the variable)")
    if not inst_bw["ok"]:
        return fail("warm install should not need the network")
    if inst_bc["ok"]:
        return fail("cold install should fail under block")
    if not inst_uc["ok"]:
        return fail("cold install should pass when unblocked")
    if not m["block_control"]["failed_as_required"]:
        return fail("deliberate fetch did not fail under wrap")
    if not m["os_netns_control"]["failed_as_required"]:
        return fail("unshare -n control did not fail")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if not rep.get("blocked_run_completed") or not rep.get("unblocked_run_completed"):
        return fail("artifact missing completed-run flags")
    dests = rep.get("attempted_destinations") or []
    if len(dests) < 1:
        return fail("attempted_destinations empty")
    verrs = SCH.errors(doc)
    if verrs:
        return fail("schema-invalid " + verrs[0])

    art_lie = None
    for st in (rep.get("runs") or {}).get("blocked", {}).get("steps") or []:
        if st.get("id") == "test_claims_offline_but_fetches":
            art_lie = st
    if not art_lie or art_lie.get("ok") is not False:
        return fail("artifact did not record lying test fail under block")

    print("SUCCESS:CNF-0106-probe1 blocked-vs-unblocked destinations attached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
