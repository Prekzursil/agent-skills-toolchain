#!/usr/bin/env python3
"""Named probe 2: restore hash-set, EOL-unchanged, planted-file oracle.

Different field from probe 1 (dry-run vs applied identity / source-unique sha).
This probe reads raw tree hashes before apply vs after restore-from-backup,
EOL classification vs a naive byte-unequal conflict, and the take-target
lifecycle path that would destroy the planted owner file.
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
    EOL_ONLY,
    SKIP,
    apply_plan,
    classify_naive_no_eol,
    classify_pair,
    copy_capture,
    hash_set,
    inverse_control,
    isolation_negative_control,
    plan_conversion,
    planted_oracle,
    payloads_from_plan,
    restore_tree,
    snapshot_tree,
    walk_files,
)
from scenario import EOL_REL, PLUGIN_ONLY_RULE  # noqa: E402

ART = REPO / "command-center/receipts/REL-0017.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0017-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:REL-0017" not in ART.read_text(encoding="utf-8"):
        print("FAILED:REL-0017-probe2 sentinel absent")
        return 1

    iso_neg = isolation_negative_control()
    if not iso_neg.get("pass"):
        print("FAILED:REL-0017-probe2 isolation negative control")
        print(json.dumps(iso_neg, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="rel0017-p2-") as tmp:
        work = Path(tmp)
        hand, plugin = copy_capture(work)
        pre_hashes = hash_set(plugin)
        pre_files = walk_files(plugin)
        backup = work / "backup"
        snapshot_tree(plugin, backup)
        plan = plan_conversion(hand, plugin)
        payloads = payloads_from_plan(hand, plugin, plan)
        apply_plan(plugin, plan, payload_by_target=payloads)
        created_set = {m["target_rel"] for m in plan if m["op"] == "create"}
        oracle = planted_oracle(hand, plugin)
        inv = inverse_control(created_set)
        eol_src = (hand / EOL_REL).read_bytes()
        eol_dst = pre_files[EOL_REL]
        honest = classify_pair(eol_src, eol_dst)
        naive = classify_naive_no_eol(eol_src, eol_dst)
        eol_row = next(m for m in plan if m["target_rel"] == EOL_REL)
        restored = restore_tree(backup, plugin)
        plugin_only_restored = restored.get(PLUGIN_ONLY_RULE) == pre_hashes.get(
            PLUGIN_ONLY_RULE
        )

    if restored != pre_hashes or not pre_hashes:
        extra = sorted(set(restored) ^ set(pre_hashes))
        print("FAILED:REL-0017-probe2 restore hash-set mismatch")
        print(json.dumps({"extra_or_missing": extra[:20], "count_pre": len(pre_hashes), "count_restored": len(restored)}) )
        return 1
    if honest != EOL_ONLY or eol_row.get("op") != SKIP:
        print(
            f"FAILED:REL-0017-probe2 EOL not unchanged honest={honest} "
            f"op={eol_row.get('op')}"
        )
        return 1
    if naive != "CONFLICT":
        print(f"FAILED:REL-0017-probe2 naive classifier did not fire naive={naive}")
        return 1
    if not oracle.get("pass") or not oracle.get("take_target_refused"):
        print("FAILED:REL-0017-probe2 planted owner file oracle")
        print(json.dumps(oracle, indent=2, default=str)[:3000])
        return 1
    if not inv.get("pass"):
        print("FAILED:REL-0017-probe2 inverse deleted a pre-existing path")
        print(json.dumps(inv, indent=2))
        return 1
    if not plugin_only_restored:
        print("FAILED:REL-0017-probe2 plugin-only file lost across restore")
        return 1

    rec_restore = doc.get("restore") or {}
    if rec_restore.get("hash_set_match") is False:
        print("FAILED:REL-0017-probe2 receipt restore reported mismatch")
        return 1
    rec_eol = doc.get("eol_classification") or {}
    if rec_eol.get("classification") not in {EOL_ONLY, "EOL-ONLY"}:
        print("FAILED:REL-0017-probe2 receipt EOL class drift", rec_eol)
        return 1

    out = {
        "probe": "probe2-restore-eol-oracle",
        "unit_id": "REL-0017",
        "restore_hash_set_match": True,
        "restore_files": len(pre_hashes),
        "eol_classification": honest,
        "eol_op": eol_row.get("op"),
        "naive_conflict": naive,
        "planted_take_target_refused": True,
        "inverse_refused_preexisting_delete": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"restore files={len(pre_hashes)} eol={honest} naive={naive} "
        f"planted_caught=True inverse_caught=True"
    )
    print("SUCCESS:REL-0017-probe2 restore, EOL-unchanged, planted-file oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
