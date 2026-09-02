#!/usr/bin/env python3
"""Named probe 1: planted user-data survives executed rollback (both-states).

Safe rollback restores a packaged artifact and keeps the planted file+hash.
Naive wipe-the-profile rollback loses it. Exit 0 only when both sides fire.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from packages import write_benign_package  # noqa: E402
from rollback import naive_rollback, plant_user_data, rehearse, sha256_bytes  # noqa: E402

PLANTED_REL = "notes/owner.txt"
PLANTED_PAYLOAD = b"IMP-0241 planted user-data; must survive packaged rollback\n"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0241-p1-") as tmp:
        root = Path(tmp)
        v1 = write_benign_package(root / "pkg" / "plugin-1.0.0.zip", "1.0.0")
        v2 = write_benign_package(root / "pkg" / "plugin-2.0.0.zip", "2.0.0")
        safe_profile = root / "safe-profile"
        result = rehearse(v1, v2, safe_profile, PLANTED_REL, PLANTED_PAYLOAD)
        naive_profile = root / "naive-profile"
        naive_profile.mkdir()
        from rollback import install_package  # local import after path setup

        install_package(v1, naive_profile)
        planted = plant_user_data(naive_profile, PLANTED_REL, PLANTED_PAYLOAD)
        planted_hash = sha256_bytes(PLANTED_PAYLOAD)
        naive = naive_rollback(v1, naive_profile)
        naive_lost = PLANTED_REL in naive.get("lost", [])
        naive_missing = not planted.is_file()

        out = {
            "probe": "probe1-userdata-rollback",
            "unit_id": "IMP-0241",
            "safe": {
                "executed": True,
                "mode": result.get("mode"),
                "pass": result.get("pass"),
                "exists_after": result.get("exists_after"),
                "hash_match": result.get("hash_match"),
                "planted_hash": result.get("planted_hash"),
                "live_hash": result.get("live_hash"),
                "lost": result.get("lost"),
                "rolled_back_to": result.get("rolled_back_to"),
                "upgraded_to": result.get("upgraded_to"),
                "package": Path(result["package"]).name if result.get("package") else None,
            },
            "naive": {
                "executed": True,
                "mode": naive.get("mode"),
                "lost_planted": naive_lost,
                "file_missing": naive_missing,
                "lost": naive.get("lost"),
            },
            "both_states": bool(
                result.get("pass") and naive_lost and naive_missing
            ),
        }
        print(json.dumps(out, sort_keys=True))
        if not result.get("pass"):
            print("FAILED:IMP-0241-probe1 safe rollback did not preserve planted user-data")
            return 1
        if result.get("planted_hash") != hashlib.sha256(PLANTED_PAYLOAD).hexdigest():
            print("FAILED:IMP-0241-probe1 planted hash drift")
            return 1
        if result.get("rolled_back_to") != "1.0.0":
            print("FAILED:IMP-0241-probe1 did not restore packaged v1")
            return 1
        if result.get("upgraded_to") != "2.0.0":
            print("FAILED:IMP-0241-probe1 upgrade to v2 did not execute")
            return 1
        if not naive_lost or not naive_missing:
            print("FAILED:IMP-0241-probe1 naive rollback did not lose planted user-data")
            return 1
        print(
            "safe_preserved=True naive_lost=True "
            f"hash={result.get('live_hash')} version={result.get('rolled_back_to')}"
        )
        print("SUCCESS:IMP-0241-probe1 planted user-data survives rehearsed rollback")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
