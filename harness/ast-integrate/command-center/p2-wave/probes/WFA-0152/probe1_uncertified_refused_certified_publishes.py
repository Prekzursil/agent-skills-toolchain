#!/usr/bin/env python3
"""Probe 1: uncertified pack refused; same pack certified publishes (both-states)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import COMPLETION_SENTINEL, OUTPUT_REL, UNIT_ID  # noqa: E402
from scenario import both_states_publish  # noqa: E402


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        print("FAILED:WFA-0152-probe1 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:WFA-0152-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:WFA-0152-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0152-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0152-p1-") as tmp_s:
        live = both_states_publish(Path(tmp_s))

    if not live.get("pass"):
        print("FAILED:WFA-0152-probe1 live both-states did not pass")
        print(json.dumps(live, sort_keys=True, default=str)[:4000])
        return 1

    uncert = live["uncertified"]
    if not uncert.get("refused"):
        print("FAILED:WFA-0152-probe1 uncertified was not refused")
        return 1
    err = uncert.get("error") or {}
    if err.get("code") != "uncertified-workflow" or err.get("workflow_id") != "wf-alpha":
        print("FAILED:WFA-0152-probe1 refuse did not name wf-alpha", err)
        return 1
    if not live["certified_v1"].get("artifact_digest"):
        print("FAILED:WFA-0152-probe1 certified publish missing digest")
        return 1
    if live["required_bump_v1_to_v11"] != "minor":
        print("FAILED:WFA-0152-probe1 required bump", live["required_bump_v1_to_v11"])
        return 1
    if not (live["insufficient_bump"] or {}).get("refused"):
        print("FAILED:WFA-0152-probe1 insufficient patch bump was accepted")
        return 1
    if not (live["privilege_widen"] or {}).get("refused"):
        print("FAILED:WFA-0152-probe1 privilege-widening preset was accepted")
        return 1

    pub = doc.get("publication") or {}
    both = pub.get("both_states") or doc.get("both_states") or {}
    if both.get("uncertified_refused") is False:
        print("FAILED:WFA-0152-probe1 artifact overclaims uncertified_refused")
        return 1
    answers = doc.get("answers") or {}
    if not answers.get("what_pack_contains"):
        print("FAILED:WFA-0152-probe1 artifact missing pack-contents answer")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-uncertified-refused-certified-publishes",
                "unit_id": UNIT_ID,
                "uncertified_code": err.get("code"),
                "uncertified_workflow_id": err.get("workflow_id"),
                "certified_digest_v1": live["certified_v1"]["artifact_digest"],
                "certified_digest_v11": live["certified_v11"]["artifact_digest"],
                "required_bump": live["required_bump_v1_to_v11"],
                "insufficient_bump_refused": True,
                "privilege_widen_refused": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0152-probe1 uncertified refused; certified published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
