#!/usr/bin/env python3
"""Probe 1: documented apply vs guide-parsed oracle, plus fixture provenance.

Signal (a): tree diff of the migrated fixture against the expected layout.
The candidate is the fenced command in docs/layout-migration.md. The oracle
relocates the same captured bytes using the mapping table parsed from that
guide — it does not import tools/layout/migrate.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import capture as C  # noqa: E402
import harness as H  # noqa: E402

UID = "TST-0256"


def main() -> int:
    if not (H.REPO / H.PROVENANCE_REL).is_file():
        rc = C.main()
        if rc != 0:
            return rc
    prov = C.verify()
    if not prov["ok"]:
        print(json.dumps({"probe": "probe1", "pass": False, "provenance": prov}, sort_keys=True))
        print("FAILED:TST-0256-probe1 fixture provenance")
        return 1

    guide = H.GUIDE.read_text(encoding="utf-8")
    mapping = H.parse_mapping(guide)
    apply_cmd = H.documented_apply_command(guide)
    if apply_cmd != H.APPLY_CMD:
        print(json.dumps({"probe": "probe1", "pass": False, "apply_cmd": apply_cmd}, sort_keys=True))
        print("FAILED:TST-0256-probe1 documented apply command drifted")
        return 1

    with H.work_copy() as tmp:
        tmp_path = Path(tmp)
        candidate = tmp_path / "candidate"
        expected = tmp_path / "expected"
        H.copy_tree(H.CAPTURED, candidate)
        crc, cout = H.run_documented(
            'python3 tools/layout/migrate.py classify --tree "$TREE"', candidate
        )
        if crc != 0:
            print(
                json.dumps(
                    {
                        "probe": "probe1",
                        "pass": False,
                        "classify_rc": crc,
                        "out": cout[-1500:],
                    },
                    sort_keys=True,
                )
            )
            print("FAILED:TST-0256-probe1 classify exited non-zero")
            return 1
        before_layout = H.last_json_object(cout)
        rc, out = H.run_documented(apply_cmd, candidate)
        if rc != 0:
            print(json.dumps({"probe": "probe1", "pass": False, "apply_rc": rc, "out": out[-1500:]}, sort_keys=True))
            print("FAILED:TST-0256-probe1 documented apply exited non-zero")
            return 1
        applied = H.last_json_object(out)
        cand_rows = H.census(candidate)
        oracle_rows = H.oracle_apply(H.CAPTURED, expected, mapping)
        diffs = H.tree_diff(cand_rows, oracle_rows)

    payload = {
        "probe": "probe1-convert-and-diff",
        "unit_id": UID,
        "pass": applied.get("action") == "migrated"
        and applied.get("layout_after") == "new"
        and before_layout.get("layout") == "old"
        and not diffs
        and prov["ok"]
        and len(cand_rows) >= 8,
        "documented_command": apply_cmd,
        "mapping": [{"from": a, "to": b} for a, b in mapping],
        "layout_before": before_layout.get("layout"),
        "apply_action": applied.get("action"),
        "layout_after": applied.get("layout_after"),
        "files_written": applied.get("files_written"),
        "candidate_tree_hash": H.tree_hash_from_census(cand_rows),
        "oracle_tree_hash": H.tree_hash_from_census(oracle_rows),
        "tree_diff_count": len(diffs),
        "tree_diff": diffs[:12],
        "candidate_paths": [r["path"] for r in cand_rows],
        "provenance": {
            "ok": prov["ok"],
            "file_count": prov["file_count"],
            "source_root": prov["source_root"],
            "synthesized_from_migration_script": prov["synthesized_from_migration_script"],
        },
        "oracle_imports_migrate": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0256-probe1 conversion or provenance")
        return 1
    print(
        "SUCCESS:TST-0256-probe1 migrated tree matches guide-oracle "
        f"hash={payload['candidate_tree_hash'][:12]} diffs=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
