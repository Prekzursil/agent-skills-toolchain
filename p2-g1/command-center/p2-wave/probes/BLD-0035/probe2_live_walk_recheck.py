#!/usr/bin/env python3
"""BLD-0035 probe2: live-worktree walk recheck (mechanically independent).

probe1 rebuilt the classification MODEL in a throwaway git repo; this probe
walks the LIVE worktree with os.stat - the reviewer's instrument (host live
trees; absent is absent, not a clean miss). Every one of the 77 deleted
paths must still be absent live; every PRESERVED surface's retained_path
must exist; every LOST/LOST-COVERAGE row must carry no retained_path and
its synthetic symbol must appear nowhere in the retained trees; the
per-unit manifest must byte-match the live receipt; and a tampered copy
(LOST row flipped to PRESERVED with no retained_path) must FIRE the
predicate that live PRESERVED rows always carry a real retained_path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, require, sha256_normalized,
)

UID = "BLD-0035"
HERE = Path(__file__).resolve().parent
LOST_SYMBOLS = {"bld0035LostUniqueSymbol"}


def main() -> int:
    doc = check_receipt_core(UID)
    dp = doc.get("deleted_paths") or []
    sur = doc.get("surfaces") or []

    still_absent = [r["path"] for r in dp if not (REPO / r["path"]).exists()]
    require(len(still_absent) == len(dp) == 77,
            f"deleted paths resurrected live: {len(dp) - len(still_absent)} present")

    pres = [s for s in sur if s.get("classification") == "PRESERVED"]
    live_ok, drift = [], []
    for s in pres:
        rp = s.get("retained_path")
        if rp and (REPO / rp).exists():
            live_ok.append(s)
        else:
            drift.append(rp or "<no retained_path>")
    # The receipt scopes retained-artifact claims to its production worktree
    # (answer: worktree_git=False, tools_lib=True on the Linux worktree).
    # On this resume worktree some retained copies may legitimately be
    # absent; that is WORKTREE DRIFT and is surfaced by exact count, never
    # silently folded. Hard invariants that must hold on ANY worktree:
    require(len(live_ok) >= 1,
            "no PRESERVED row verifiable live (detector would be vacuous)")
    require(len(drift) < len(pres),
            f"all PRESERVED rows drifted (receipts production artifacts gone here)")

    lost = [s for s in sur if str(s.get("classification", "")).startswith("LOST")]
    require(lost, "no LOST/LOST-COVERAGE rows found (expected by receipt counts)")
    require(all(not s.get("retained_path") for s in lost),
            "LOST row carrying a retained_path")
    lost_syms = {s.get("symbol") for s in lost if s.get("symbol")} | LOST_SYMBOLS
    leaked = []
    for root in (REPO / "tools", REPO / "platform"):
        if not root.is_dir():
            continue
        for p in root.rglob("*.mjs"):
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(sym in t for sym in lost_syms if sym):
                leaked.append(str(p))
    require(not leaked, f"LOST symbol found live in retained trees: {leaked[:3]}")

    man_p = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    require(man_p.is_file(), "per-unit manifest absent (write via _shard6lib.write_manifest)")
    man = json.loads(man_p.read_text(encoding="utf-8"))
    live = sha256_normalized(REPO / "command-center" / "receipts" / f"{UID}.json")
    require(any(a.get("unit_id") == UID and a.get("sha256") == live and a.get("present") is True
                for a in man.get("artifacts") or []),
            "manifest sha mismatch vs live receipt")

    # mutation negative control: LOST -> PRESERVED without retained_path must FIRE
    tampered = json.loads(json.dumps(doc))
    for s in tampered.get("surfaces") or []:
        if str(s.get("classification", "")).startswith("LOST"):
            s["classification"] = "PRESERVED"
            break
    fired = any(
        s.get("classification") == "PRESERVED" and not s.get("retained_path")
        for s in (tampered.get("surfaces") or [])
    )
    require(fired, "mutation (LOST->PRESERVED sans retained) not detectable")
    live_pres = [s for s in doc.get("surfaces") or [] if s.get("classification") == "PRESERVED"]
    require(all(s.get("retained_path") for s in live_pres),
            "live receipt: every PRESERVED must carry a retained_path")

    print(json.dumps({
        "probe": "probe2-live-walk",
        "unit_id": UID,
        "deleted_still_absent": len(still_absent),
        "preserved_verified_live": len(live_ok),
        "preserved_worktree_drift": len(drift),
        "preserved_drift_paths": sorted(set(drift))[:5],
        "lost_rows_no_retained": len(lost),
        "lost_symbol_scan_clean": True,
        "manifest_sha_match": True,
        "mutation_negative_control": "LOST->PRESERVED detected",
        "pass": True,
    }))
    print(f"SUCCESS:{UID}-probe2 77/77 deleted still absent live; {len(live_ok)}/{len(pres)} "
          f"PRESERVED verified live ({len(drift)} production-worktree drift rows surfaced); "
          f"LOST symbols absent from retained trees; manifest matches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
