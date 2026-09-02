#!/usr/bin/env python3
"""Probe 1: live artifact satisfies the RES-0119 contract; captures re-hash.

Mechanically: load catalog output, evaluate(contract), re-hash capture files,
re-measure local Tor/opt-in and compare to the artifact's environment block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import sweep as S  # noqa: E402
from policy import OUTPUT_REL, SENTINEL, UNIT_ID  # noqa: E402

ART = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0119-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errors = C.evaluate(doc, REPO)
    if errors:
        print(json.dumps({"errors": errors}, indent=2))
        return fail("contract:" + ",".join(errors[:8]))

    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-not-in-bytes")
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        return fail("state-success-not-in-bytes")

    live_env = S.environment_probe(REPO)
    art_env = doc.get("environment") or {}
    if bool(live_env.get("tor_client_present")) != bool(
        art_env.get("tor_client_present")
    ):
        return fail("tor-client-drift")
    if bool(live_env.get("owner_optin_present")) != bool(
        art_env.get("owner_optin_present")
    ):
        return fail("owner-optin-drift")
    if live_env.get("tor_client_present"):
        return fail("live-tor-client-present")
    if live_env.get("owner_optin_present"):
        return fail("live-owner-optin-present")

    api_ok = False
    prose_ok = False
    for cap in doc.get("captures") or []:
        if cap.get("kind") == "structured-api" and cap.get("http_status") == 200:
            api_ok = True
        if cap.get("kind") == "prose" and cap.get("http_status") == 200:
            prose_ok = True
    if not api_ok or not prose_ok:
        return fail(f"rails api={api_ok} prose={prose_ok}")

    print(
        json.dumps(
            {
                "probe": "probe1-live-contract",
                "unit_id": UNIT_ID,
                "contract_errors": [],
                "captures": len(doc.get("captures") or []),
                "egress_rows": len(doc.get("egress_log") or []),
                "null_recorded": (doc.get("explicit_null_result") or {}).get(
                    "recorded"
                ),
                "onion_fetches_completed": doc.get("onion_fetches_completed"),
                "tor_client_present": live_env["tor_client_present"],
                "owner_optin_present": live_env["owner_optin_present"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0119-probe1 live contract + capture rehash + env remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
