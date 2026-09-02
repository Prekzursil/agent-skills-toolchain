#!/usr/bin/env python3
"""Named probe 1: git cat-file -p re-verifies every deployed file's blob sha.

Catalog signal (1): after a deploy into a throwaway HOME, every deployed
file's recorded source blob sha is re-verified by `git cat-file -p <sha>`
hashing to the same value as the live file. A record set can be complete
while the files are wrong; this probe is the bytes direction.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import deploy_provenance as dp  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0033.json"
SENTINEL = "SUCCESS:IMP-0033"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0033-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0033-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0033-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0033-p1-") as td:
        root = Path(td)
        src = root / "src"
        home = root / "home"
        home.mkdir()
        planted = dp.plant_throwaway_plugin(src)
        git_dir = Path(planted["git_dir"])
        deployed = dp.deploy_all_via_scripts(
            repo=src, home=home, git_dir=git_dir, worktree=REPO
        )
        ledger = json.loads((home / dp.LEDGER_REL).read_text(encoding="utf-8"))
        rows = []
        disagree = []
        for rec in ledger["records"]:
            live_path = home / rec["live_path"]
            live = live_path.read_bytes()
            blob = dp.git_cat_file_p(git_dir, rec["source_blob_sha"])
            live_sha = hashlib.sha256(live).hexdigest()
            cat_sha = hashlib.sha256(blob).hexdigest()
            blob_id = hashlib.sha1(f"blob {len(live)}\0".encode("ascii") + live).hexdigest()
            ok = blob == live and live_sha == cat_sha and blob_id == rec["source_blob_sha"]
            row = {
                "live_path": rec["live_path"],
                "source_path": rec["source_path"],
                "source_blob_sha": rec["source_blob_sha"],
                "catfile_sha256": cat_sha,
                "live_sha256": live_sha,
                "independent_blob_id": blob_id,
                "ok": ok,
            }
            rows.append(row)
            if not ok:
                disagree.append(row)
        if deployed["placed"] != planted["n_deployable"]:
            print(
                f"FAILED:IMP-0033-probe1 placed={deployed['placed']} "
                f"want={planted['n_deployable']}"
            )
            return 1
        if disagree:
            print(json.dumps({"disagree": disagree}, indent=2))
            print("FAILED:IMP-0033-probe1 cat-file hash mismatch")
            return 1
        if len(rows) < 6:
            print(f"FAILED:IMP-0033-probe1 too few records {len(rows)}")
            return 1

    out = {
        "probe": "probe1-blob-catfile",
        "unit_id": "IMP-0033",
        "pass": True,
        "n_records": len(rows),
        "n_catfile_ok": len(rows),
        "invoked_scripts": deployed["invoked_scripts"],
        "method": "git cat-file -p <source_blob_sha> sha256-equals live file",
        "two_independent_signals": True,
        "rows": rows,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0033-probe1 cat-file re-verifies every deployed blob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
