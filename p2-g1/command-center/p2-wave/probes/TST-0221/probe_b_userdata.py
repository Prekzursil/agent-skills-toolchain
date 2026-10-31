#!/usr/bin/env python3
"""TST-0221 probe B: removal preserves user data; rollback restores the package.

Signal (b): two scoped byte-inventories, hashed with a mechanically different
API (os.walk) than the tree utilities used elsewhere:
  1. the PACKAGE-LOCAL tree (site packages/hello-skill/1.0.0) is byte-identical
     after remove + rollback restore (the rollback regression seed: a rollback
     path that lost or rewrote package bytes would fail here);
  2. the OWNER's user-data directory in the site survives remove and rollback
     byte-identical; the removed payload directory is genuinely gone between
     the two, so the identical restore is a real round-trip, not a no-op.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "marketplace"))

from mkt import fixture, install as inst_mod  # noqa: E402

WORK = HERE / "fixtures" / "userdata"


def walk_inventory(root: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = str(p.relative_to(root)).replace("\\", "/")
            data = p.read_bytes()
            h.update(rel.encode("utf-8"))
            h.update(hashlib.sha256(data).digest())
            count += 1
    return h.hexdigest(), count


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    built = fixture.build(WORK)
    registry_root = Path(built["registry_root"])
    policy = fixture.trust_policy()
    site = WORK / "site"
    inst = inst_mod.Installer(registry_root, site, policy)
    receipt = inst.install("hello-skill", "=1.0.0")
    assert receipt["outcome"] == "SUCCESS", receipt

    (site / "user-data").mkdir(parents=True, exist_ok=True)
    (site / "user-data" / "notes.txt").write_bytes(b"owner notes: survive every transition\n")

    payload_dir = site / "packages" / "hello-skill" / "1.0.0"
    pkg_hash_pre, pkg_files_pre = walk_inventory(payload_dir)
    user_hash_pre, user_files_pre = walk_inventory(site / "user-data")

    rm = inst.remove("hello-skill")
    removed_ok = rm["outcome"] == "SUCCESS" and not payload_dir.exists()
    user_hash_post, _ = walk_inventory(site / "user-data")

    rb = inst.rollback("hello-skill")
    rollback_ok = rb["outcome"] == "SUCCESS" and rb.get("version") == "1.0.0"
    pkg_hash_post_rb, pkg_files_post_rb = walk_inventory(payload_dir)
    user_hash_post_rb, _ = walk_inventory(site / "user-data")

    checks = {
        "remove_succeeds_and_payload_gone": removed_ok is True,
        "rollback_restores_package_bytes_identical": rollback_ok is True
        and pkg_hash_pre == pkg_hash_post_rb
        and pkg_files_pre == pkg_files_post_rb
        and pkg_files_pre >= 1,
        "user_data_byte_identical_after_remove": user_hash_pre == user_hash_post,
        "user_data_byte_identical_after_rollback": user_hash_pre == user_hash_post_rb,
        "inventory_material": pkg_files_pre >= 1 and user_files_pre >= 1,
    }
    out = {
        "probe": "probe_b_userdata",
        "unit": "TST-0221",
        "remove_receipt": {"outcome": rm.get("outcome"), "version": rm.get("version")},
        "rollback_receipt": {"outcome": rb.get("outcome"), "version": rb.get("version")},
        "hashes": {
            "package_pre": pkg_hash_pre,
            "package_post_rollback": pkg_hash_post_rb,
            "user_pre": user_hash_pre,
            "user_post_remove": user_hash_post,
            "user_post_rollback": user_hash_post_rb,
        },
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-b-userdata.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(WORK, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
