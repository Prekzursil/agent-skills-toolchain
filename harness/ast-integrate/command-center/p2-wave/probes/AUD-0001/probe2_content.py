#!/usr/bin/env python3
"""Probe 2: PR-MERGED for head SHA, else two-dot tree equality (not ancestry)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

ART = REPO / C.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0001-probe2 {msg}")
    return 1


def main() -> int:
    bundle = C.live_bundle()
    if not bundle["control_ok"]:
        return fail(f"control {bundle['control_detail']}")
    fixture = bundle["fixture"]
    squash = C.by_name(fixture, C.SQUASH_BRANCH)
    unmerged = C.by_name(fixture, C.UNMERGED_BRANCH)
    on_main = C.by_name(fixture, C.ON_MAIN_BRANCH)
    if squash is None or unmerged is None or on_main is None:
        return fail("fixture branches missing")
    if squash["ancestry_ahead"] and squash["content_on_main"] is False:
        return fail("content detector missed squash-merged branch")
    if not squash["pr_merged"] and not squash["two_dot_empty"]:
        return fail("probe2 has neither PR-MERGED nor tree-equal for squash")
    if squash["class"] != "SQUASH-MERGED":
        return fail(f"expected SQUASH-MERGED got {squash['class']}")
    if unmerged["content_on_main"]:
        return fail("content detector is not discriminating (unmerged looks on-main)")
    if not on_main["content_on_main"]:
        return fail("already-on-main not CONTENT-ON-MAIN")
    if squash["two_dot_empty"] and squash["three_dot_empty"]:
        # Unusual but not fatal: still require ancestry/content disagreement.
        if not squash["ancestry_ahead"]:
            return fail("both diffs empty and ancestry not ahead; control collapsed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    blob = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(blob)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in blob:
        return fail("sentinel-absent")
    headline = doc.get("headline") or {}
    if int(headline.get("squash_merge_false_ahead") or 0) < 1:
        return fail("headline squash_merge_false_ahead missing")
    rec = None
    for row in (doc.get("fixture") or {}).get("branches") or []:
        if row.get("branch") == C.SQUASH_BRANCH:
            rec = row
            break
    if rec is None:
        return fail("artifact missing squash branch row")
    if rec.get("content_on_main") is not True:
        return fail("artifact squash row is not CONTENT-ON-MAIN")
    if rec.get("ancestry_ahead") is not True:
        return fail("artifact squash row lost ancestry-ahead")
    if rec.get("class") != "SQUASH-MERGED":
        return fail("artifact did not classify squash as SQUASH-MERGED")
    if rec.get("head_sha") != squash["head_sha"]:
        return fail("artifact squash head_sha drifted from live fixture")
    probes = doc.get("named_probes") or []
    if len(probes) < 2:
        return fail("named probes not recorded")
    joined = json.dumps(probes)
    if "PR-MERGED" not in joined and "TREE-EQUAL" not in joined:
        return fail("probe2 transcript missing from artifact")

    payload = {
        "pass": True,
        "probe": "probe2-content",
        "unit_id": "AUD-0001",
        "squash_content_on_main": squash["content_on_main"],
        "squash_reason": squash["content_reason"],
        "squash_pr_merged": squash["pr_merged"],
        "squash_two_dot_empty": squash["two_dot_empty"],
        "squash_three_dot_empty": squash["three_dot_empty"],
        "unmerged_content_on_main": unmerged["content_on_main"],
        "class": squash["class"],
        "falsified": "ancestry-ahead-as-unmerged",
        "head_sha": squash["head_sha"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"squash content_on_main={squash['content_on_main']} "
        f"reason={squash['content_reason']} "
        f"two_dot_empty={squash['two_dot_empty']} "
        f"unmerged_on_main={unmerged['content_on_main']}"
    )
    print("SUCCESS:AUD-0001-probe2 PR-MERGED/tree-equal reports squash CONTENT-ON-MAIN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
