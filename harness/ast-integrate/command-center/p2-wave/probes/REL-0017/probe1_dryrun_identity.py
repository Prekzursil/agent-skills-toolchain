#!/usr/bin/env python3
"""Named probe 1: dry-run plan versus independently measured applied tree delta.

Also: a source-only file survives conversion with its raw sha256 intact.
Different field from probe 2 (restore hash-set / EOL class / planted-file oracle).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from migrate import (  # noqa: E402
    CREATE,
    apply_plan,
    assert_copy,
    copy_capture,
    isolation_negative_control,
    plan_conversion,
    plan_vs_applied,
    payloads_from_plan,
    source_unique_report,
    verify_source_unique_hashes,
    walk_files,
)
from scenario import PLANTED_LINE, PLANTED_TARGET  # noqa: E402

ART = REPO / "command-center/receipts/REL-0017.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0017-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "REL-0017":
        print("FAILED:REL-0017-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:REL-0017" not in text:
        print("FAILED:REL-0017-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:REL-0017-probe1 self-declared", doc.get("state"))
        return 1
    iso = doc.get("isolation") or {}
    if iso.get("ran_against_copy") is not True:
        print("FAILED:REL-0017-probe1 receipt did not run against a copy")
        return 1
    if not iso.get("copy_path"):
        print("FAILED:REL-0017-probe1 copy_path missing")
        return 1

    iso_neg = isolation_negative_control()
    if not iso_neg.get("pass"):
        print("FAILED:REL-0017-probe1 isolation negative control")
        print(json.dumps(iso_neg, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="rel0017-p1-") as tmp:
        work = Path(tmp)
        hand, plugin = copy_capture(work)
        try:
            assert_copy(plugin, mutating=True)
        except Exception as exc:
            print("FAILED:REL-0017-probe1 copy isolation", exc)
            return 1
        if plugin.resolve() == (HERE / "fixtures/captured/plugin").resolve():
            print("FAILED:REL-0017-probe1 mutating captured original")
            return 1
        plan = plan_conversion(hand, plugin)
        pre = walk_files(plugin)
        payloads = payloads_from_plan(hand, plugin, plan)
        apply_plan(plugin, plan, payload_by_target=payloads)
        post = walk_files(plugin)
        diffs = plan_vs_applied(plan, pre, post)
        unique = source_unique_report(plan)
        hash_fail = verify_source_unique_hashes(hand, plugin, plan)
        planted = plugin / PLANTED_TARGET
        planted_ok = (
            planted.is_file()
            and PLANTED_LINE.encode("utf-8") in planted.read_bytes()
            and not hash_fail
        )

    if diffs:
        print("FAILED:REL-0017-probe1 dry-run vs applied diff not empty")
        print(json.dumps(diffs, indent=2)[:3000])
        return 1
    if unique["preserved"] < 1:
        print("FAILED:REL-0017-probe1 no source-unique files preserved")
        return 1
    if unique["refused"] < 1:
        print("FAILED:REL-0017-probe1 no both-unique refuse (oracle would be silent)")
        return 1
    if hash_fail:
        print(f"FAILED:REL-0017-probe1 source-unique hash broken {hash_fail}")
        return 1
    if not planted_ok:
        print("FAILED:REL-0017-probe1 planted owner skill hash not intact")
        return 1

    recorded_diff = doc.get("plan_vs_applied_diff")
    if recorded_diff not in ([], None) and recorded_diff:
        print("FAILED:REL-0017-probe1 receipt plan_vs_applied_diff not empty")
        return 1
    rec_unique = (doc.get("source_unique") or {})
    if rec_unique.get("preserved") != unique["preserved"]:
        print(
            "FAILED:REL-0017-probe1 preserved count drift "
            f"receipt={rec_unique.get('preserved')} live={unique['preserved']}"
        )
        return 1

    creates = [m for m in plan if m["op"] == CREATE]
    out = {
        "probe": "probe1-dryrun-identity",
        "unit_id": "REL-0017",
        "copy_path": str(work),
        "plan_applied_identical": True,
        "measured_write_count": len([m for m in plan if m["op"] in {CREATE, "overwrite"}]),
        "creates": len(creates),
        "source_unique_preserved": unique["preserved"],
        "source_unique_refused": unique["refused"],
        "source_unique_hashes_intact": True,
        "isolation_negative_control": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"dry-run vs applied diff empty; preserved={unique['preserved']} "
        f"refused={unique['refused']} copy={iso.get('copy_path')}"
    )
    print("SUCCESS:REL-0017-probe1 dry-run identity and source-unique hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
