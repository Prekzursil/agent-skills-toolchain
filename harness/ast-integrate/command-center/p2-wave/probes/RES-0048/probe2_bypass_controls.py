#!/usr/bin/env python3
"""Named probe 2: bypass every listed mitigation; require two named attacks.

Both-states control:
  * naive signature-exists policy accepts the real signature even when the
    expected publisher is wrong (fires on bad policy)
  * identity-pinned policy accepts the real identity and rejects the wrong one
    (silent on the good pin)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from bypasses import (  # noqa: E402
    ATTACK_PARTIAL_TREE,
    ATTACK_SIGNED_MALWARE,
    ATTACK_UNPINNED_IDENTITY,
    construct_bypasses,
)

ART = REPO / "command-center/research/RES-0048.json"
REQUIRED_ATTACKS = (
    ATTACK_SIGNED_MALWARE,
    ATTACK_UNPINNED_IDENTITY,
    ATTACK_PARTIAL_TREE,
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:RES-0048-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    review = construct_bypasses()
    print(
        f"naive_accepts={review['naive_accepts_real_signature']} "
        f"pinned_real={review['pinned_accepts_real_identity']} "
        f"pinned_wrong={review['pinned_accepts_wrong_identity']}"
    )
    print(f"trees clean={review['trees']['clean'][:16]} swapped={review['trees']['swapped'][:16]}")

    fired_on_bad = (
        review["naive_accepts_real_signature"] and not review["pinned_accepts_wrong_identity"]
    )
    silent_on_good = review["pinned_accepts_real_identity"] is True
    if not fired_on_bad:
        return fail("identity-confusion control did not fire on unpinned policy", review)
    if not silent_on_good:
        return fail("pinned policy was not silent on the real identity", review)

    by_id = {m["id"]: m for m in review["mitigations"]}
    exists_only = by_id["MITIGATION-SIGNATURE-EXISTS-ONLY"]
    malware_scan = by_id["MITIGATION-SIGNATURE-AS-MALWARE-SCAN"]
    tree_pin = by_id["MITIGATION-IDENTITY-PINNED-TREE-DIGEST"]
    if exists_only.get("effective") or not exists_only.get("bypass_succeeded"):
        return fail("signature-exists-only must be bypassed and not effective")
    if malware_scan.get("effective") or not malware_scan.get("bypass_succeeded"):
        return fail("malware-scan mitigation must be bypassed and not effective")
    if not tree_pin.get("effective") or tree_pin.get("bypass_succeeded"):
        return fail("pinned tree-digest substitution bypass should fail; mitigation effective")

    if review["trees"]["plugin_json_only_clean"] != review["trees"]["plugin_json_only_swap"]:
        return fail("plugin.json-only digest should be identical across SKILL.md swap")
    if review["trees"]["clean"] == review["trees"]["swapped"]:
        return fail("full-tree digest should move when SKILL.md is swapped")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    named = {a.get("id") for a in (doc.get("does_not_prevent") or []) if isinstance(a, dict)}
    missing = [a for a in REQUIRED_ATTACKS if a not in named]
    if missing:
        return fail("artifact does not name required attacks", {"missing": missing, "named": sorted(named)})
    if len(doc.get("does_not_prevent") or []) < 2:
        return fail("need at least two named attacks")

    overclaim = False
    for m in doc.get("mitigations") or []:
        if m.get("id") == "MITIGATION-SIGNATURE-AS-MALWARE-SCAN" and m.get("effective"):
            overclaim = True
        if m.get("id") == "MITIGATION-SIGNATURE-EXISTS-ONLY" and m.get("effective"):
            overclaim = True
    if overclaim:
        return fail("artifact records a bypassed mitigation as effective")

    print(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"attacks_in_artifact={len(named)} required_present=True"
    )
    print("SUCCESS:RES-0048-probe2 bypass controls and named does-not-prevent list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
