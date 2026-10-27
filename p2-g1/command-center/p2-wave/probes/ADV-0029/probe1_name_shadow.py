#!/usr/bin/env python3
"""Probe 1: resolve a private name with a higher-version public shadow, by hash."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0029-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0029-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0029-probe1 self-declared {st}")
        return 1

    live = H.run_campaign()
    pred = live["predicates"]
    if not pred["control_private_only_selects_private"]:
        print("FAILED:ADV-0029-probe1 control did not select the private payload")
        return 1
    if not pred["origin_pin_mutant_selects_private"]:
        print("FAILED:ADV-0029-probe1 origin-pin mutant did not select private")
        return 1
    if not pred["hashes_distinct"]:
        print("FAILED:ADV-0029-probe1 fixture hashes are not distinct")
        return 1
    if not pred["detector_live"]:
        print("FAILED:ADV-0029-probe1 detector is not live")
        return 1

    t1 = live["targets"][0]
    if t1["verdict"] not in H.LEGAL:
        print("FAILED:ADV-0029-probe1 illegal verdict", t1)
        return 1
    art_targets = {
        t["id"]: t["verdict"] for t in doc.get("enumerated_targets") or []
    }
    live_targets = {t["id"]: t["verdict"] for t in live["targets"]}
    if art_targets != live_targets:
        print("FAILED:ADV-0029-probe1 target verdict mismatch", art_targets, live_targets)
        return 1
    if t1["fetched_sha256"] != live["payloads"]["public_sha256"]:
        if t1["verdict"] == "CONFIRMED":
            print("FAILED:ADV-0029-probe1 CONFIRMED but fetched hash is not public")
            return 1
    if t1["fetched_sha256"] == live["payloads"]["private_sha256"]:
        if t1["verdict"] == "CONFIRMED":
            print("FAILED:ADV-0029-probe1 private hash fetched; cannot CONFIRM confusion")
            return 1

    summary = {
        "probe": "probe1-name-shadow",
        "unit_id": H.UNIT,
        "pass": True,
        "control_ok": True,
        "origin_pin_mutant_ok": True,
        "chosen_origin": t1.get("chosen_origin"),
        "chosen_version": t1.get("chosen_version"),
        "fetched_sha256": t1.get("fetched_sha256"),
        "private_sha256": live["payloads"]["private_sha256"],
        "public_sha256": live["payloads"]["public_sha256"],
        "t1_dependency_confusion": t1["verdict"],
        "selector": (live.get("shadow") or {}).get("selector"),
        "installer": H.INSTALLER_REL + ":attempt_install",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "origin={0} ver={1} fetched={2} public={3} t1={4}".format(
            t1.get("chosen_origin"),
            t1.get("chosen_version"),
            t1.get("fetched_sha256"),
            live["payloads"]["public_sha256"],
            t1["verdict"],
        )
    )
    print("SUCCESS:ADV-0029-probe1 resolved private name with public shadow by hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
