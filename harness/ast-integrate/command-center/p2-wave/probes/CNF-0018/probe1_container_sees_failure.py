#!/usr/bin/env python3
"""Probe 1: the container must reproduce at least one known failure.

Re-runs the disposable isolation. A table that is all PASS is silently green
and fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import container as C  # noqa: E402
import fields as F  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0018-linux-container-repro.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0018-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0018":
        print("FAILED:CNF-0018-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0018-probe1 self-declared", doc.get("state"))
        return 1

    packed = C.run_container()
    measured = packed["measure"]
    xp = next(f for f in measured["failures"] if f["id"].startswith("F-XP-"))
    live_fail = [
        f["id"]
        for f in measured["failures"]
        if f["linux_container"]["outcome"] == "FAIL"
    ]
    print(
        json.dumps(
            {
                "probe": "probe1-container-sees-failure",
                "image_digest": packed["container"]["image_digest"],
                "kind": packed["container"]["kind"],
                "known_failure_reproduced": measured.get("known_failure_reproduced"),
                "linux_fail_ids": live_fail,
                "xp_outcome": xp["linux_container"]["outcome"],
                "artifact_digest_match": packed["container"]["image_digest"]
                == (doc.get("container") or {}).get("image_digest"),
            },
            sort_keys=True,
        )
    )
    if not measured.get("known_failure_reproduced"):
        print("FAILED:CNF-0018-probe1 known failure not reproduced")
        return 1
    if xp["linux_container"]["outcome"] != "FAIL":
        print("FAILED:CNF-0018-probe1 XP row did not FAIL in container")
        return 1
    if not live_fail:
        print("FAILED:CNF-0018-probe1 silently green: zero FAIL rows")
        return 1
    art_digest = F.container_of(doc).get("image_digest")
    if art_digest != packed["container"]["image_digest"]:
        print(
            "FAILED:CNF-0018-probe1 image_digest drift "
            f"artifact={art_digest} live={packed['container']['image_digest']}"
        )
        return 1
    print("SUCCESS:CNF-0018-probe1 container reproduced a known failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
