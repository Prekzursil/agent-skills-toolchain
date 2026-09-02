#!/usr/bin/env python3
"""Probe 1: known-present PR-ONLY + DELETE-ALL, and planted laundering.

Re-runs the classifier. Does not trust the artifact's stored control block
as the only signal: classifications are computed from the fixtures, then
checked against the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0138-authority-provenance.json"
SENTINEL_NEEDLE = "SUCCESS:ADV-0138 emitted only when"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0138-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if SENTINEL_NEEDLE not in text:
        print("FAILED:ADV-0138-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:ADV-0138-probe1 self-declared", doc.get("state"))
        return 1

    kp = C.known_present_bundle()
    planted = C.planted_bundle(C.load_catalog_utterances())
    if not kp["pass"]:
        print("FAILED:ADV-0138-probe1 known-present")
        print(json.dumps(kp, default=str)[:2000])
        return 1
    if kp["pr_only"]["classification"] != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe1 PR-ONLY not OWNER-STATED")
        return 1
    if kp["delete_all"]["classification"] != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe1 DELETE-ALL not OWNER-STATED")
        return 1
    ok_pr, why_pr = C.resolve_anchor(
        kp["pr_only"]["anchor"], kp["pr_only"]["owner_quote"]
    )
    ok_del, why_del = C.resolve_anchor(
        kp["delete_all"]["anchor"], kp["delete_all"]["owner_quote"]
    )
    if not ok_pr or not ok_del:
        print("FAILED:ADV-0138-probe1 known-present anchors", why_pr, why_del)
        return 1
    if not planted["pass"] or planted["row"]["classification"] != C.PROGRAM:
        print("FAILED:ADV-0138-probe1 planted not PROGRAM-AUTHORED")
        print(json.dumps(planted, default=str)[:2000])
        return 1

    stored = doc.get("controls") or {}
    if not (stored.get("known_present") or {}).get("pass"):
        print("FAILED:ADV-0138-probe1 artifact known_present.pass false")
        return 1
    if (stored.get("known_present") or {}).get(
        "pr_only_classification"
    ) != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe1 artifact PR-ONLY drift")
        return 1
    if (stored.get("known_present") or {}).get(
        "delete_all_classification"
    ) != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe1 artifact DELETE-ALL drift")
        return 1
    if (stored.get("planted_laundering") or {}).get("classification") != C.PROGRAM:
        print("FAILED:ADV-0138-probe1 artifact planted drift")
        return 1

    live = doc.get("binding_decisions") or []
    missing_cls = [r.get("id") for r in live if not r.get("classification")]
    if missing_cls:
        print("FAILED:ADV-0138-probe1 live row missing classification", missing_cls)
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-known-present-and-laundering",
        "unit_id": "ADV-0138",
        "pr_only": {
            "classification": kp["pr_only"]["classification"],
            "anchor": kp["pr_only"]["anchor"],
            "anchor_ok": why_pr,
        },
        "delete_all": {
            "classification": kp["delete_all"]["classification"],
            "anchor": kp["delete_all"]["anchor"],
            "anchor_ok": why_del,
        },
        "planted_classification": planted["row"]["classification"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "known_present PR-ONLY=OWNER-STATED DELETE-ALL=OWNER-STATED "
        "planted=PROGRAM-AUTHORED"
    )
    print("SUCCESS:ADV-0138-probe1 known-present and planted laundering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
