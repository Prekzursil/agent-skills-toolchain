#!/usr/bin/env python3
"""Probe 2: credential-free control + reviewer bypass of every mitigation.

Independent of hop derivation (does not import hops). Both-states: live
artifact must be clean; a planted-JWT mutant of the same object must fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scan as S  # noqa: E402

UNIT = "RES-0044"
ART = REPO / "command-center/research/RES-0044.json"
SENTINEL = (
    "SUCCESS:RES-0044 in the receipt AND a hop-by-hop token-location trace "
    "plus a scan result showing the artifact is credential-free"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    raw = ART.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    live = S.scan_obj(doc)
    if not live["credential_free"]:
        return fail(f"live artifact not credential-free {live['hits']}")

    planted = S.scan_obj(S.plant_jwt(doc, "_planted_control"))
    if planted["credential_free"] or planted["hit_count"] < 1:
        return fail("planted JWT mutant did not fire (control inert)")

    review = doc.get("reviewer_bypass_attempts") or {}
    attempts = {a.get("id"): a for a in (review.get("attempts") or []) if isinstance(a, dict)}
    for bid in ("B1-nested-jwt", "B2-bearer-header-transcript", "B3-access-token-key", "B5-token-in-query-url"):
        row = attempts.get(bid)
        if not row:
            return fail(f"missing bypass {bid}")
        if not row.get("effective") or row.get("bypass_succeeded"):
            return fail(f"bypass {bid} did not establish mitigation")
    hex_row = attempts.get("B4-hex-encoded-jwt")
    if not hex_row:
        return fail("missing residual bypass B4")
    if hex_row.get("residual") is not True:
        return fail("B4 must be marked residual")
    if hex_row.get("bypass_succeeded") is not True:
        return fail("B4 residual encoding bypass did not succeed; residual is dishonest")

    scan_block = doc.get("credential_scan") or {}
    if scan_block.get("result") != "CREDENTIAL-FREE":
        return fail("credential_scan.result not CREDENTIAL-FREE")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("T2-credential-free-artifact", {}).get("result") != "PASS":
        return fail("T2 not PASS")
    if (doc.get("reviewer") or {}).get("verdict") != "PASS":
        return fail("reviewer verdict not PASS")

    print(
        json.dumps(
            {
                "probe": "probe2-credential-scan",
                "live_credential_free": True,
                "planted_jwt_fires": True,
                "reviewer_id": review.get("reviewer_id"),
                "bypasses_effective": [
                    "B1-nested-jwt",
                    "B2-bearer-header-transcript",
                    "B3-access-token-key",
                    "B5-token-in-query-url",
                ],
                "residual_encoding_bypass": "B4-hex-encoded-jwt",
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 artifact credential-free; planted JWT fires; mitigations reviewed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
