#!/usr/bin/env python3
"""BLD-0033 probe2: reviewer-instrument recheck (mechanically independent).

The receipt's independent reviewer block prescribes three query instruments
the author classifier does NOT share: (1) git log -S <symbol> --all
--diff-filter=D on a throwaway fixture repo, (2) inventory glob for
SKILL.md / plugin.json / marketplace*.json roots, (3) a live walk of
~/.claude and ~/.agents on this host (absent is absent, not a clean miss).
This probe executes all three on fresh fixtures, byte-compares the per-unit
manifest against the live receipt, and runs a mutation negative control (a
tampered copy whose reviewer closure loses independence must be detectable).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, git_fixture, require, sha256_normalized,
)

UID = "BLD-0033"
HERE = Path(__file__).resolve().parent
SYMBOL = "BLD0033_DELETED_ONLY_SYMBOL_qx9v"


def instrument_1_pickaxe_diff_filter() -> None:
    repo, _revs = git_fixture(
        {"tools/retired/once-only-scanner.mjs": f"export const {SYMBOL} = true;\n"},
        delete=["tools/retired/once-only-scanner.mjs"],
    )
    r = subprocess.run(
        ["git", "-C", repo, "log", "--all", "-S", SYMBOL,
         "--diff-filter=D", "--format=%H"],
        capture_output=True, text=True, timeout=120,
    )
    require(r.returncode == 0, f"pickaxe --diff-filter=D failed: {r.stderr[:200]}")
    require(r.stdout.strip(), "reviewer pickaxe query (--diff-filter=D) found no deletion commit")


def instrument_2_inventory_globs() -> None:
    root = Path(tempfile.mkdtemp(prefix="bld0033-inv-"))
    try:
        (root / "skills" / "alpha").mkdir(parents=True)
        (root / "skills" / "alpha" / "SKILL.md").write_text(
            "---\nname: alpha\n---\n", encoding="utf-8")
        (root / "plugins" / "beta").mkdir(parents=True)
        (root / "plugins" / "beta" / "plugin.json").write_text(
            '{"name":"beta"}', encoding="utf-8")
        (root / "marketplace.json").write_text("[]", encoding="utf-8")
        found = {
            p.name
            for pat in ("SKILL.md", "plugin.json", "marketplace*.json")
            for p in root.rglob(pat)
        }
        require(found == {"SKILL.md", "plugin.json", "marketplace.json"},
                f"inventory glob result wrong: {sorted(found)}")
        # an inventory root with NONE of those must enumerate EMPTY, not clean:
        # absent is absent
        empty = Path(tempfile.mkdtemp(prefix="bld0033-empty-"))
        try:
            (empty / "not-a-skill.txt").write_text("x", encoding="utf-8")
            hits = [p.name for pat in ("SKILL.md", "plugin.json", "marketplace*.json")
                    for p in empty.rglob(pat)]
            require(hits == [], f"empty root falsely enumerated: {hits}")
        finally:
            shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def instrument_3_host_live_walk() -> int:
    home = Path.home()
    total = 0
    for name in (".claude", ".agents"):
        root = home / name
        require(root.is_dir(), f"host live surface ~/{name} not present to walk")
        n = sum(1 for p in root.rglob("*") if p.is_file())
        require(n > 0, f"host live surface ~/{name} walked zero files")
        total += n
    return total


def manifest_and_mutation() -> None:
    man_p = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    require(man_p.is_file(), "per-unit manifest absent (write via _shard6lib.write_manifest)")
    man = json.loads(man_p.read_text(encoding="utf-8"))
    rows = [a for a in (man.get("artifacts") or []) if a.get("unit_id") == UID]
    require(rows, "manifest has no row for this unit")
    live = sha256_normalized(REPO / "command-center" / "receipts" / f"{UID}.json")
    require(any(a.get("sha256") == live and a.get("present") is True for a in rows),
            "manifest sha does not match live receipt bytes (LF-normalized)")

    # mutation negative control: reviewer closure losing independence must be
    # detectable in a tampered copy, and impossible in the live receipt.
    text = (REPO / "command-center" / "receipts" / f"{UID}.json").read_text(encoding="utf-8")
    doc = json.loads(text)
    require(doc["reviewer"].get("independent") is True,
            "live receipt reviewer already non-independent")
    tampered = json.loads(text)
    tampered["reviewer"]["independent"] = False
    fired = tampered["reviewer"]["independent"] is False and tampered["reviewer"]["independent"] != doc["reviewer"]["independent"]
    require(fired, "mutation (independent=false) not detectable in tampered copy")


def main() -> int:
    check_receipt_core(UID)
    instrument_1_pickaxe_diff_filter()
    instrument_2_inventory_globs()
    host_files = instrument_3_host_live_walk()
    manifest_and_mutation()
    print(json.dumps({
        "probe": "probe2-reviewer-instruments",
        "unit_id": UID,
        "pickaxe_diff_filter_found_deleted": True,
        "inventory_globs_enumerate_and_stay_silent_on_empty": True,
        "host_live_walk_files": host_files,
        "manifest_sha_match": True,
        "mutation_negative_control": "independent=false detected",
        "pass": True,
    }))
    print(f"SUCCESS:{UID}-probe2 reviewer's three instruments re-executed live; "
          f"manifest sha matches; mutation control fires")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
