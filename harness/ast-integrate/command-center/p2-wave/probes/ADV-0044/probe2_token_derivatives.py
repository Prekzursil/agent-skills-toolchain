#!/usr/bin/env python3
"""Probe 2: search by a distinctive TOKEN from the artifact body (not by id)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0044-artifact-erasure-completeness.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0044-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0044":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:ADV-0044" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = P.run_campaign(REPO)
    if not live["controls_ok"]:
        return fail("live controls failed " + json.dumps(live["tests"]))
    live_v = P.qualitative(live)
    rec_v = {row["id"]: row["verdict"] for row in P.targets_from_artifact(doc)}
    if rec_v.get("body-token-derivatives") != live_v.get("body-token-derivatives"):
        return fail(
            "derivative verdict drift "
            f"artifact={rec_v.get('body-token-derivatives')} "
            f"live={live_v.get('body-token-derivatives')}"
        )
    if live_v.get("body-token-derivatives") != "REFUTED":
        return fail("TOKEN derivatives unexpectedly gone after id-based unlink")
    token_stores = live["counts"]["post_target_token_stores"]
    if "derivatives" not in token_stores:
        return fail(f"TOKEN not found in derivatives stores={token_stores}")
    if not live["post_control_token_hits"]:
        return fail("control TOKEN not findable after purge")
    deriv_only = [
        h for h in live["post_target_token_hits"] if h["store"] == "derivatives"
    ]
    if not deriv_only:
        return fail("no TOKEN hits classified as derivatives")
    print(P.render_probe2(live))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
