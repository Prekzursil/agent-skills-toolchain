#!/usr/bin/env python3
"""Probe 2: named permission/lock errors, both-states, overclaim guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / "command-center/receipts/BLD-0009.json"


def main() -> int:
    matrix = H.run_matrix()
    by_id = {c["id"]: c for c in matrix["cells"]}

    lock = by_id.get("open_file_held")
    print(f"open_file_held verdict={lock and lock['verdict']} error={lock and lock.get('named_error')}")
    if not lock or lock["verdict"] != "EXERCISED" or lock.get("named_error") != "FileLocked":
        print("FAILED:BLD-0009-probe2 lock cell")
        return 1

    perm = by_id.get("acl_or_readonly_dir")
    print(f"acl_or_readonly_dir verdict={perm and perm['verdict']} error={perm and perm.get('named_error')}")
    if not perm or perm["verdict"] not in {"EXERCISED", "NEVER-TESTED"}:
        print("FAILED:BLD-0009-probe2 permission cell missing")
        return 1
    if perm["verdict"] == "EXERCISED" and perm.get("named_error") != "PermissionDenied":
        print("FAILED:BLD-0009-probe2 permission not named")
        return 1

    if not H.fixture_negative_fails():
        print("FAILED:BLD-0009-probe2 empty-tree fixture control did not fail")
        return 1

    linux_only_never = ("mapped_network_drive", "ntfs_junction_escape")
    for cell_id in linux_only_never:
        cell = by_id[cell_id]
        print(f"{cell_id} verdict={cell['verdict']}")
        if cell["verdict"] == "EXERCISED":
            print(f"FAILED:BLD-0009-probe2 overclaim {cell_id} EXERCISED on Linux")
            return 1

    adv = matrix["adv_0117"]
    print(f"adv_0117 consumed={adv['consumed']} present={adv['present']}")
    if not adv["consumed"]:
        for owned in H.ADV_OWNED:
            if by_id[owned]["verdict"] == "COVERED-BY-ADV-0117":
                print(f"FAILED:BLD-0009-probe2 overclaim {owned} COVERED-BY-ADV-0117 without receipt")
                return 1

    if not ART.is_file():
        print("FAILED:BLD-0009-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0009-probe2 self-declared {doc.get('state')}")
        return 1
    live_ids = {c["id"] for c in matrix["cells"]}
    art_cells = doc.get("cells")
    if not isinstance(art_cells, list):
        report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
        art_cells = report.get("cells") if isinstance(report, dict) else []
    art_ids = {c["id"] for c in art_cells if isinstance(c, dict) and "id" in c}
    if live_ids != art_ids:
        print(f"FAILED:BLD-0009-probe2 cell-id drift live={sorted(live_ids)} art={sorted(art_ids)}")
        return 1
    if "SUCCESS:BLD-0009" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0009-probe2 sentinel absent")
        return 1
    print("SUCCESS:BLD-0009-probe2 permission-lock both-states overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
