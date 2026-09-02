#!/usr/bin/env python3
"""Probe 1: planted self-patch DETECTED, neighbour and mention not flagged.

Both-states: the same detector fires on the self-patch control and is silent
on the neighbour control. A detector silent in both states measures nothing.
Prioritisation: P0-contract self-patch ranks above P2-unit self-patch.
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
SELF_NAMES = (
    "test_http_client_patches_own_subject",
    "test_http_client_patches_own_subject_low",
    "test_patch_object_own_subject",
    "test_mocker_patches_own_subject",
    "test_context_manager_patches_own_subject",
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0349-probe1 {msg}")
    return 1


def main() -> int:
    census = S.run_unit_census()
    planted = census["planted"]
    detected = []
    for name in SELF_NAMES:
        row = C.record_by_name(planted, name)
        if row is None:
            return fail(f"missing planted test {name}")
        if not row["flagged"] or not row["overlaps"]:
            return fail(f"{name} not DETECTED overlaps={row.get('overlaps')}")
        if row["subject"] not in row["overlaps"] and not any(
            t.startswith(row["subject"] + ".") for t in row["overlaps"]
        ):
            return fail(f"{name} overlaps do not include subject {row['subject']}")
        detected.append(name)
        print(f"DETECTED {name} subject={row['subject']} overlaps={row['overlaps']}")

    neighbour = C.record_by_name(planted, "test_http_client_patches_neighbour")
    if neighbour is None:
        return fail("missing neighbour control")
    if neighbour["flagged"]:
        return fail("neighbour control flagged")
    if neighbour["patch_call_count"] < 1:
        return fail("neighbour control has no patch calls (control is inert)")
    print(
        f"neighbour_not_flagged patch_call_count={neighbour['patch_call_count']} "
        f"patched={neighbour['patched']}"
    )

    mention = C.record_by_name(planted, "test_mention_only_does_not_patch")
    if mention is None:
        return fail("missing mention control")
    if mention["flagged"] or mention["patch_call_count"] != 0:
        return fail(
            f"mention treated as use flagged={mention['flagged']} "
            f"patch_call_count={mention['patch_call_count']}"
        )
    print("mention_not_use patch_call_count=0")

    high = C.record_by_name(planted, "test_http_client_patches_own_subject")
    low = C.record_by_name(planted, "test_http_client_patches_own_subject_low")
    if high["score"] <= low["score"]:
        return fail(f"priority scores high={high['score']} low={low['score']}")
    ranked = [r["name"] for r in census["prioritized"]]
    if ranked.index("test_http_client_patches_own_subject") > ranked.index(
        "test_http_client_patches_own_subject_low"
    ):
        return fail(f"rank order {ranked}")
    print(
        f"prioritisation P0-contract={high['score']} P2-unit={low['score']} "
        f"order={ranked}"
    )

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    payload = S.receipt_payload(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0349" not in text:
        return fail("sentinel absent")
    if payload.get("deletion_forbidden") is not True:
        return fail("artifact must forbid deletion")
    required = {
        t["id"]: t for t in payload.get("tests_required") or [] if isinstance(t, dict)
    }
    for tid in ("planted-self-patch", "neighbour-not-flagged", "prioritisation"):
        if required.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact tests_required {tid} not PASS")
    conv = payload.get("prioritized_for_conversion") or []
    if len(conv) < len(SELF_NAMES):
        return fail(f"conversion list short {len(conv)}")
    if any(row.get("forbidden_action") != "delete" for row in conv):
        return fail("conversion list missing forbidden delete")

    print(
        json.dumps(
            {
                "detected": detected,
                "neighbour_flagged": False,
                "mention_patch_calls": 0,
                "p0_score": high["score"],
                "p2_score": low["score"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0349-probe1 planted controls both-states and prioritisation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
