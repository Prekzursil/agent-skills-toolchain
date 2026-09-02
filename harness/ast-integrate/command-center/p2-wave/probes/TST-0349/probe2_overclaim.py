#!/usr/bin/env python3
"""Probe 2: overclaim control — raw mock count is not the finding.

A test with three neighbour patches must stay unflagged. A mutant that
flags any patch_call_count>0 would call that test a finding. The receipt
must record subject+overlapping target pairs, live TEST-REGISTRY absence,
and conversion-not-deletion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / S.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0349-probe2 {msg}")
    return 1


def main() -> int:
    census = S.run_unit_census()
    planted = census["planted"]
    triple = C.record_by_name(planted, "test_three_neighbour_mocks")
    if triple is None:
        return fail("missing three-neighbour control")
    if triple["patch_call_count"] < 3:
        return fail(f"expected >=3 patch calls, got {triple['patch_call_count']}")
    if triple["flagged"]:
        return fail("three neighbour mocks flagged; overlap rule is broken")
    mutant_would_flag = [r["name"] for r in planted if r["patch_call_count"] > 0]
    overlap_flags = [r["name"] for r in planted if r["flagged"]]
    if "test_three_neighbour_mocks" not in mutant_would_flag:
        return fail("count-mutant would not see the neighbour-heavy test")
    if "test_three_neighbour_mocks" in overlap_flags:
        return fail("overlap detector matched the count mutant")
    if "test_http_client_patches_own_subject" not in overlap_flags:
        return fail("self-patch missing from overlap flags")
    extra = set(mutant_would_flag) - set(overlap_flags)
    if "test_three_neighbour_mocks" not in extra:
        return fail(f"count mutant extras={sorted(extra)}")
    print(
        json.dumps(
            {
                "triple_patch_call_count": triple["patch_call_count"],
                "triple_flagged": False,
                "count_mutant_would_flag": sorted(mutant_would_flag),
                "overlap_flags": sorted(overlap_flags),
                "count_mutant_false_positives": sorted(extra),
            },
            sort_keys=True,
        )
    )

    mention = C.record_by_name(planted, "test_mention_only_does_not_patch")
    src = (REPO / mention["path"]).read_text(encoding="utf-8")
    if 'patch("subject_pkg.http_client.HttpClient")' not in src:
        return fail("mention fixture lost the patch(...) string")
    if mention["patch_call_count"] != 0:
        return fail("text mention counted as a patch Call")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    payload = S.receipt_payload(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0349" not in text:
        return fail("sentinel absent")
    if payload.get("raw_mock_count_is_not_the_finding") is not True:
        return fail("artifact does not record that raw mock count is not the finding")
    if payload.get("deletion_forbidden") is not True:
        return fail("artifact does not forbid deletion")
    evidence = payload.get("overlap_evidence") or []
    if not evidence:
        return fail("no overlap_evidence (subject + patched target)")
    for row in evidence:
        if not row.get("subject") or not row.get("overlapping_patched_target"):
            return fail(f"evidence missing subject/target pair {row}")
    declared = (payload.get("declared_inputs") or {}).get("TEST-REGISTRY.json") or {}
    live_present = S.live_registry_path().is_file()
    if bool(declared.get("present")) is not bool(live_present):
        return fail(
            f"TEST-REGISTRY present={declared.get('present')} disk={live_present}"
        )
    live = payload.get("live_corpus") or {}
    if "UNDECLARED" not in str(live.get("honesty") or ""):
        return fail("live corpus honesty must say UNDECLARED, not silently clean")
    if "CLEAN" in str(live.get("honesty") or "").upper() and "UNDECLARED" not in str(
        live.get("honesty") or ""
    ):
        return fail("live corpus honesty claims CLEAN")
    if live.get("flagged") not in (0, census["counts"]["live_flagged"]):
        return fail("live flagged count mismatch")
    conv = payload.get("prioritized_for_conversion") or []
    if any(row.get("recommended_action") == "delete" for row in conv):
        return fail("conversion list recommends delete")
    if any("delete" in str(row.get("recommended_action") or "") for row in conv):
        return fail("conversion action mentions delete")

    print("SUCCESS:TST-0349-probe2 overclaim: count mutant vs overlap, mention, honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
