#!/usr/bin/env python3
"""TST-0194 probe2 -- negative control: deferring the check to INSTALL time must
fail the unit's requirement - on case-insensitive NTFS the colliding pair
installs to FEWER files than manifest entries (silent last-write-wins loss),
which is exactly what the BUILD-time gate prevents. Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packer as PK  # noqa: E402

UNIT = "TST-0194"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)

    colliding = {
        "Lib/Hooks.py": b"# hooks A (build-gated pair)\n",
        "lib/hooks.py": b"# hooks B (case-variant, would overwrite)\n",
    }
    staging = RUN / "naive-staging"
    staging.mkdir(parents=True)
    for rel, data in colliding.items():  # a packer WITHOUT the build gate
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    staged_files = sum(1 for f in staging.rglob("*") if f.is_file())

    target = RUN / "install-target"
    installed_files = PK.install(staging, target)
    survivor = (target / "Lib" / "Hooks.py")
    survived_content = survivor.read_bytes() if survivor.exists() else None
    lost_variant = b"# hooks A (build-gated pair)" not in (survived_content or b"") or installed_files < staged_files
    data_loss_demonstrated = installed_files < len(colliding)

    payload = {
        "probe": "probe2-install-deferral",
        "unit_id": UNIT,
        "pass": data_loss_demonstrated and lost_variant,
        "negative_control": {
            "deferred_check": "naive packer skips the build gate; collision surfaces at install",
            "manifest_entries": len(colliding),
            "staged_files": staged_files,
            "installed_files_after_ntfs_merge": installed_files,
            "silent_data_loss": data_loss_demonstrated,
            "survivor_content": (survived_content or b"").decode(errors="replace").strip(),
        },
        "casefold_set_comparison": {
            "raw_distinct": len(set(colliding)),
            "casefold_distinct": len(set(p.casefold() for p in colliding)),
            "delta_is_hidden_collision": len(set(colliding)) - len(set(p.casefold() for p in colliding)),
        },
        "conclusion": "deferring to install time fails the requirement; the build-time gate (probe1) is required",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 installed=%d<%d silent-loss-demonstrated=True"
              % (UNIT, installed_files, len(colliding)))
        return 0
    print("FAILED:%s-probe2 installed=%d staged=%d loss=%s"
          % (UNIT, installed_files, staged_files, data_loss_demonstrated))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
