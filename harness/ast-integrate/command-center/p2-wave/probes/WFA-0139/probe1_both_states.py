#!/usr/bin/env python3
"""Probe 1: both-states copyleft+permissive and unknown-fail-closed.

Feed a copyleft+permissive pair and assert the copyleft result; feed an
unknown-license source and assert BLOCKED rather than a silent permissive
default. Detector-control: known copyleft pair is classified BEFORE the
unknown absence claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lattice as L  # noqa: E402
import loader as LD  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0139-license-and-credit-propagation-lattice-through-fusio.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0139-probe1 {msg}")
    return 1


def main() -> int:
    corpus = LD.load_corpus(REPO)
    register = corpus["register_by_id"]
    # Detector-control first: known copyleft+permissive pair.
    print("detector_control_first=True")
    print("both-states copyleft+permissive")
    copyleft = L.fuse(
        [register["LR-01"], register["LR-16"]],
        register,
        fusion_id="probe1-copyleft-permissive",
    )
    print(
        f"copyleft_status={copyleft['status']} "
        f"result_class={copyleft['result_class']} "
        f"rules={copyleft['rules_applied']}"
    )
    if copyleft["status"] != "ALLOWED":
        return fail("copyleft+permissive was not ALLOWED")
    if copyleft["result_class"] != "STRONG_COPYLEFT":
        return fail("copyleft+permissive did not yield STRONG_COPYLEFT")
    if 6 not in copyleft["rules_applied"]:
        return fail("copyleft+permissive missing rule index 6")
    print("detector_control_found_copyleft_result=True")

    print("both-states unknown-license")
    unknown = L.fuse(
        [register["LR-01"], register["LR-41"]],
        register,
        fusion_id="probe1-unknown",
    )
    print(
        f"unknown_status={unknown['status']} "
        f"result_class={unknown['result_class']} "
        f"rules={unknown['rules_applied']}"
    )
    if unknown["status"] != "BLOCKED":
        return fail("unknown-license was not BLOCKED")
    if unknown["result_class"] is not None:
        return fail("unknown-license assigned an outbound class")
    if unknown["result_class"] == "PERMISSIVE":
        return fail("silent permissive default")
    if 2 not in unknown["rules_applied"]:
        return fail("unknown-license missing rule index 2")

    # MU-03 and MU-09 on the seeded corpus (same pairs).
    mu3 = L.fuse_merge_unit(corpus["merge_units"][2], register)
    mu9 = L.fuse_merge_unit(corpus["merge_units"][8], register)
    print(f"MU-03 status={mu3['status']} class={mu3['result_class']}")
    print(f"MU-09 status={mu9['status']} class={mu9['result_class']}")
    if mu3["result_class"] != "STRONG_COPYLEFT" or mu3["status"] != "ALLOWED":
        return fail("MU-03 copyleft+permissive mismatch")
    if mu9["status"] != "BLOCKED":
        return fail("MU-09 unknown was not BLOCKED")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0139" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    bs = doc.get("both_states") or {}
    cp = bs.get("copyleft_plus_permissive") or {}
    uk = bs.get("unknown_license") or {}
    if cp.get("result_class") != "STRONG_COPYLEFT":
        return fail("artifact copyleft both-states mismatch")
    if uk.get("status") != "BLOCKED" or uk.get("silent_permissive_default") is not False:
        return fail("artifact unknown both-states mismatch")
    if doc.get("lattice", {}).get("unknown_never_permissive") is not True:
        return fail("artifact missing unknown_never_permissive")
    print("SUCCESS:WFA-0139-probe1 copyleft+permissive and unknown fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
