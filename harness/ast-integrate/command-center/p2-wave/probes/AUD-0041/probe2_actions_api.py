#!/usr/bin/env python3
"""Probe 2: Actions API job list + string-named workflow registry.

Mechanically different from probe 1: observes matrix expansion and skipped
steps the static YAML does not show, and follows string-named registries.
The planted registry-only ghost must be LIVE. Stripping string edges must
return it to DEAD.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    GHOST,
    assert_control,
    build,
    probe2_payload,
)

ART = REPO / "command-center/audit/AUD-0041-ci-step-inventory.json"
SENTINEL = "SUCCESS:AUD-0041"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0041-probe2 {msg}")
    return 1


def main() -> int:
    cen = build()
    payload = probe2_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    ctl = cen["planted_control"]
    if payload["ghost"] != "LIVE":
        return fail("ghost not LIVE via registry")
    if payload["truly_absent"] != "DEAD":
        return fail("truly_absent must stay DEAD")
    if payload["mention_only"] != "DEAD":
        return fail("comment mention counted as a use")
    if ctl["probe2_without_string_edges"] != "DEAD":
        return fail("string-edge strawman did not fire")
    if payload.get("string_edge_count", 0) < 1:
        return fail("no string registry edges")
    if payload["api_matrix_job_count"] != 6:
        return fail("known-run API job count != 6 matrix legs")
    if payload["api_plain_job_count"] != 1:
        return fail("plain known-run API job count != 1")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    art_ctl = doc.get("planted_control") or {}
    if art_ctl.get("probe2_verdict") != "LIVE":
        return fail("artifact probe2_verdict not LIVE")
    if art_ctl.get("independent") is not True:
        return fail("artifact control not independent")
    by_id = {i["id"]: i for i in doc.get("items") or [] if i.get("kind") == "module"}
    row = by_id.get(GHOST)
    if not row or row.get("probe2_verdict") != "LIVE":
        return fail("artifact ghost item probe2 not LIVE")
    if row.get("probe1_verdict") == row.get("probe2_verdict"):
        return fail("probes agree on registry-only ghost")
    never = [
        i
        for i in doc.get("items") or []
        if i.get("kind") == "function"
        and i.get("step_name") == "never"
        and i.get("universe") == "fixture"
    ]
    if not never or never[0].get("probe2_verdict") != "DEAD":
        return fail("artifact skipped-step never not DEAD on API")
    if never[0].get("probe1_verdict") != "LIVE":
        return fail("artifact skipped-step never not LIVE on YAML")
    if (doc.get("sampled_agree") or "") != payload["sampled_agree"]:
        return fail("artifact sampled_agree drifted from live API reconcile")
    print(
        f"actions_api ghost=LIVE matrix_api_jobs=6 "
        f"sampled_agree={payload['sampled_agree']} "
        f"yaml_skipped={payload['origin_yaml_live_api_skipped']}"
    )
    print("SUCCESS:AUD-0041-probe2 registry-only LIVE; API skipped steps DEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
