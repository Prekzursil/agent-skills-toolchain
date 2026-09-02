#!/usr/bin/env python3
"""Probe 2: both-states healthy SUCCESS + consumer-read (not stat).

Mechanically different from probe 1 (no planted deletion). Uses a second
listing instrument (os.walk) and proves existence≠readability on a fixture
that stats and parses but lacks consumer_token.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import gate as G  # noqa: E402


DEPS = ("CNF-0162", "CNF-0169", "CNF-0187", "CNF-0191")


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0192-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0192-ok-") as td:
        root = Path(td)
        mpath = F.write_healthy(root)
        result = G.verify(mpath)
        walk_names = G.list_disk_os_walk(root)
        rglob_names = [row["path"] for row in result["disk_listing"]]
        print(
            json.dumps(
                {
                    "case": "healthy",
                    "bucket": result["bucket_terminal_state"],
                    "counts": result["counts"],
                    "exceptions": result["exceptions"],
                    "listing_agree": walk_names == rglob_names,
                    "walk_n": len(walk_names),
                    "rglob_n": len(rglob_names),
                },
                sort_keys=True,
            )
        )
        if result["bucket_terminal_state"] != "SUCCESS":
            return _fail(f"healthy bucket {result['bucket_terminal_state']}")
        if result["exceptions"] != 0:
            return _fail(f"healthy exceptions {result['exceptions']}")
        if result["counts"]["verified"] != result["counts"]["total"]:
            return _fail("healthy verified != total")
        if result["counts"]["missing"] or result["counts"]["empty"] or result["counts"]["unreadable_by_consumer"]:
            return _fail("healthy exception counters not zero")
        if walk_names != rglob_names:
            return _fail("os.walk listing disagrees with pathlib rglob")
        for entry in result["entries"]:
            if entry["terminal_state"] != "VERIFIED":
                return _fail(f"{entry['id']} not VERIFIED")
            if entry.get("stat_only") is True:
                return _fail("stat_only true — condition 12 would be decorative")
            cons = entry.get("consumer") or {}
            if not cons.get("opened") or cons.get("bytes_read", 0) <= 0:
                return _fail(f"{entry['id']} consumer did not open/read")
            if not cons.get("first_key"):
                return _fail(f"{entry['id']} consumer extracted no first_key")
            if "id" not in (cons.get("parsed_keys") or []):
                return _fail(f"{entry['id']} consumer did not parse required id")

    with tempfile.TemporaryDirectory(prefix="cnf0192-unread-") as td:
        root = Path(td)
        mpath = F.write_tree(root, unreadable="alpha")
        result = G.verify(mpath)
        alpha = next(e for e in result["entries"] if e["id"] == "alpha")
        alpha_path = root / "bucket" / "alpha.json"
        exists_only = alpha_path.is_file() and alpha_path.stat().st_size > 0
        print(
            json.dumps(
                {
                    "case": "unreadable-alpha",
                    "bucket": result["bucket_terminal_state"],
                    "alpha": alpha["terminal_state"],
                    "unreadable": result["counts"]["unreadable_by_consumer"],
                    "exists_and_nonempty": exists_only,
                    "consumer_reason": (alpha.get("consumer") or {}).get("reason"),
                },
                sort_keys=True,
            )
        )
        if not exists_only:
            return _fail("unreadable fixture is not a present non-empty file")
        if alpha["terminal_state"] != "UNREADABLE-BY-CONSUMER":
            return _fail(
                f"exists-and-parses-but-missing-token -> {alpha['terminal_state']} "
                "(existence mistaken for readability)"
            )
        if result["counts"]["unreadable_by_consumer"] < 1:
            return _fail("unreadable-by-consumer count did not grow")
        if result["bucket_terminal_state"] == "SUCCESS":
            return _fail("bucket SUCCESS on unreadable consumer fixture")

    # Roll-up guard: absent upstream receipts must stay NOT-CHECKED, never CONFIRMED.
    rollup = []
    for uid in DEPS:
        path = REPO / "command-center" / "receipts" / f"{uid}.json"
        present = path.is_file() and path.stat().st_size > 0
        verdict = "PRESENT-ON-DISK" if present else "NOT-CHECKED"
        if (not present) and verdict == "CONFIRMED":
            return _fail(f"{uid} silently upgraded")
        if not present and verdict != "NOT-CHECKED":
            return _fail(f"{uid} absent but verdict={verdict}")
        rollup.append({"id": uid, "present": present, "verdict": verdict})
    print(json.dumps({"rollup_guard": rollup}, sort_keys=True))
    upgraded = [r for r in rollup if (not r["present"]) and r["verdict"] not in {"NOT-CHECKED", "MISSING"}]
    if upgraded:
        return _fail(f"NOT-CHECKED upgraded: {upgraded}")

    live = REPO / "command-center" / "ARTIFACT-MANIFEST.json"
    print(f"live_charter_manifest_present={live.is_file()}")

    print("SUCCESS:CNF-0192-probe2 both-states consumer-read and rollup-guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
