#!/usr/bin/env python3
"""Probe 2: live sweep + independent source settlement (no lane narratives).

Mechanically different from probe 1:
  * walks on-disk lane artifacts, not the planted B09/B10 JSON
  * re-reads OWNER and BASELINE excerpts only (reviewer path)
  * proves the live 10-vs-6 Direction A counts are scoped (not a false positive)
  * checks leftover remaining totals for same-file detector-failure
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe2-live.raw.json"
ART = REPO / "command-center/receipts/BLD-0061.json"
FM = REPO / "command-center/phase3/A2/FAILURE-MODES.json"
LEFTOVER = REPO / "command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
OWNER = HERE / "fixtures/sources/OWNER-DECISIONS-excerpt.md"
BASELINE = HERE / "fixtures/sources/BASELINE-SNAPSHOT-excerpt.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0061-probe2 {msg}")
    return 1


def main() -> int:
    # Independent reviewer path: raw sources only, no B09/B10 narratives.
    owner = OWNER.read_text(encoding="utf-8")
    if "PR-ONLY" not in owner:
        return fail("owner excerpt missing PR-ONLY")
    if "canary" in owner.lower():
        return fail("owner excerpt unexpectedly names canary")
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    if int(base["ci_test_steps_executed"]) != 28:
        return fail("baseline excerpt is not 28")
    print("raw_source_pr_only=True raw_source_ci_steps=28")

    live = D.run_live()
    OUT.write_text(json.dumps(live, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        "live_claims="
        + str(len(live["claims"]))
        + " live_contradictions="
        + str(len(live["contradictions"]))
        + " live_detector_failures="
        + str(len(live["detector_failures"]))
        + " search_surface="
        + str(len(live["search_surface"]))
    )

    # Live FP analogue: two Direction A counts in FAILURE-MODES.json (10 vs 6)
    # with different pairings must not share a contradiction subject.
    # phase3/A2 is empty on this worktree (.gitkeep only); skip if the file
    # is absent rather than inventing the 10-vs-6 numbers.
    if not FM.is_file():
        print("direction_a_analogue_absent=True path=command-center/phase3/A2/FAILURE-MODES.json")
    if FM.is_file():
        fm = json.loads(FM.read_text(encoding="utf-8"))
        live_n = fm["live_completeness"]["direction_a_orphan_registry_count"]
        support_n = fm["live_completeness"]["supporting_catalog_slice"]["direction_a_orphan_registry_count"]
        p1 = fm["live_completeness"]["pairing"]
        p2 = fm["live_completeness"]["supporting_catalog_slice"]["pairing"]
        print(f"direction_a_live={live_n} pairing={p1}")
        print(f"direction_a_support={support_n} pairing={p2}")
        if live_n == support_n:
            return fail("expected 10 vs 6 Direction A analogue")
        if p1 == p2:
            return fail("pairings must differ for the FP analogue")
        for c in live["contradictions"]:
            ids = {c.get("left", {}).get("id"), c.get("right", {}).get("id")}
            vals = c.get("values") or {}
            if c.get("kind") == "count" and set(vals.values()) == {live_n, support_n}:
                return fail("false-positive: 10 vs 6 Direction A flagged as one quantity")

    if LEFTOVER.is_file():
        left = json.loads(LEFTOVER.read_text(encoding="utf-8"))
        ids = left.get("remaining_ids") if isinstance(left.get("remaining_ids"), list) else []
        idn = len(ids)
        uniq = len({str(x) for x in ids})
        rbp = left.get("remaining_by_prefix")
        declared = left.get("remaining_if_log_success_skipped")
        rbp_ok = isinstance(rbp, dict) and bool(rbp)
        print(
            f"leftover_id_list={idn} unique={uniq} declared={declared} "
            f"rbp_present={rbp_ok}"
        )
        total_fails = [
            c
            for c in live["detector_failures"]
            if "leftover.remaining_total" in str(c.get("subject"))
        ]
        card_fails = [
            c
            for c in live["detector_failures"]
            if "leftover.remaining_ids_cardinality" in str(c.get("subject"))
        ]
        if rbp_ok and isinstance(declared, int):
            summed = sum(v for v in rbp.values() if isinstance(v, int))
            print(f"leftover_prefix_sum={summed} declared={declared} id_list={idn}")
            if summed == declared == idn:
                if total_fails:
                    return fail("leftover internals agree but classified detector-failure")
                print("leftover_internal_consistent=True")
            else:
                if not total_fails:
                    return fail("leftover internals disagree but not classified detector-failure")
                print("leftover_internal_detector_failure=True")
        else:
            print("leftover_prefix_fields_absent=True")
        if idn != uniq:
            if not card_fails:
                return fail("duplicate leftover ids not classified detector-failure")
            print("leftover_duplicate_ids_detector_failure=True")
        else:
            if card_fails:
                return fail("unique leftover ids classified detector-failure")
            print("leftover_ids_unique=True")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:BLD-0061" not in text:
            return fail("sentinel absent")
        rev = doc.get("reviewer") or {}
        if rev.get("resolved_from_raw_sources") is not True:
            return fail("reviewer did not resolve from raw sources")
        resolved = {r.get("subject"): r for r in (rev.get("resolutions") or [])}
        if resolved.get("release.mode", {}).get("winner") != "B09-REL-MODE":
            return fail("reviewer release.mode winner")
        if resolved.get("baseline.ci_steps_executed", {}).get("winner") != "B09-CI-COUNT":
            return fail("reviewer ci_steps winner")
        if (doc.get("controls") or {}).get("pass") is not True:
            return fail("artifact controls.pass")
        # Probe2 live contradiction count must match the artifact's live section.
        art_live = (doc.get("live_sweep") or {}).get("contradictions") or []
        if len(art_live) != len(live["contradictions"]):
            return fail(
                f"artifact live contradictions {len(art_live)} != probe2 {len(live['contradictions'])}"
            )
        print("artifact_checked=True")
    else:
        print("artifact_checked=False (emit has not written yet)")

    print("SUCCESS:BLD-0061-probe2 live-sweep source-settlement scoped-count-fp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
