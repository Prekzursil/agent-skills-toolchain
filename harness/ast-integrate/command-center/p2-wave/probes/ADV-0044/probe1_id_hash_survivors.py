#!/usr/bin/env python3
"""Probe 1: purge, then search every store by id and by content hash."""
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
    print(f"FAILED:ADV-0044-probe1 {msg}")
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
    for key in (
        "primary-store",
        "event-log-refs",
        "indexes",
        "body-token-derivatives",
        "caches",
        "embeddings",
        "backups",
        "mirrors",
    ):
        if rec_v.get(key) != live_v.get(key):
            return fail(
                f"verdict drift {key} artifact={rec_v.get(key)} live={live_v.get(key)}"
            )
    if live_v.get("primary-store") != "CONFIRMED":
        return fail("primary store was not cleared by unlink")
    if live_v.get("event-log-refs") != "REFUTED":
        return fail("event log unexpectedly empty of target id/hash")
    if live_v.get("indexes") != "REFUTED":
        return fail("index unexpectedly empty of target id/hash")
    if not live["post_control_id_hits"]:
        return fail("control artifact not findable by id after purge")
    if live["purge"].get("production_purge_api_absent") is not True:
        return fail("expected production purge API to be absent")
    print(P.render_probe1(live))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
