#!/usr/bin/env python3
"""Probe 2: p100 observed path length from a 256-unit fan-out.

Independent of probe 1: creates 256 worktree directories on disk and
measures leaf length via Path.name / os.lstat, not via the generator's
return value alone. Catalog tests_required[1] / evidence (b).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import path_budget as PB  # noqa: E402

N = 256
PREFIXES = ("TS", "TST", "TEST", "TOOLS")  # 2, 3, 4, 5 chars -> id len 7..10


def fail(msg: str) -> int:
    print(f"FAILED:TST-0204-probe2 {msg}")
    return 1


def percentile(sorted_vals: list[int], pct: int) -> int:
    if not sorted_vals:
        return 0
    if pct >= 100:
        return sorted_vals[-1]
    idx = min(len(sorted_vals) - 1, max(0, (pct * len(sorted_vals)) // 100))
    return sorted_vals[idx]


def main() -> int:
    caps = PB.declared_caps()
    root_cap = caps["MAX_WORKTREE_NAME_LEN"]
    id_cap = caps["MAX_UNIT_ID_LEN"]

    contrib_lens: list[int] = []
    resolved_lens: list[int] = []
    rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="tst0204-fanout-") as tmp:
        base = Path(tmp) / "fan"
        base.mkdir()
        created = 0
        for i in range(N):
            prefix = PREFIXES[i % len(PREFIXES)]
            uid = PB.generate_unit_id(prefix, i)
            root = PB.generate_worktree_root(base, uid, shard=i)
            root.mkdir(parents=False)
            marker = root / "marker.txt"
            marker.write_text(f"{uid}\n", encoding="utf-8")
            if not root.is_dir():
                return fail(f"mkdir did not produce a directory for {uid}")
            st = os.lstat(root)
            if st.st_nlink < 1:
                return fail(f"lstat empty for {root}")
            leaf = root.name
            if leaf != PB.worktree_name(uid, i):
                return fail(f"disk name {leaf!r} != generator leaf")
            contrib = len(leaf)
            resolved = len(str(root.resolve()))
            if contrib > root_cap:
                return fail(f"disk leaf {leaf!r} len={contrib} > cap {root_cap}")
            if len(uid) > id_cap:
                return fail(f"id {uid!r} len={len(uid)} > cap {id_cap}")
            contrib_lens.append(contrib)
            resolved_lens.append(resolved)
            rows.append(
                {
                    "i": i,
                    "unit_id": uid,
                    "leaf": leaf,
                    "contrib_len": contrib,
                    "resolved_len": resolved,
                }
            )
            created += 1
        listing = sorted(p.name for p in base.iterdir() if p.is_dir())
        if len(listing) != N:
            return fail(f"fan-out listing {len(listing)} != {N}")

    if created != N:
        return fail(f"created {created} != {N}")

    contrib_sorted = sorted(contrib_lens)
    resolved_sorted = sorted(resolved_lens)
    p100_contrib = percentile(contrib_sorted, 100)
    p100_resolved = percentile(resolved_sorted, 100)
    longest = max(rows, key=lambda r: (r["contrib_len"], r["resolved_len"]))

    # Negative control: a convention-only long name would exceed the cap
    # and must not appear in the fan-out listing.
    planted = PB.convention_only_worktree_name("VERYLONGUNITID-0001", 0)
    if len(planted) <= root_cap:
        return fail(f"planted convention leaf not over-cap: {planted!r}")
    if planted in {r["leaf"] for r in rows}:
        return fail("convention-only over-cap name was allocated")

    payload = {
        "unit_id": "TST-0204",
        "probe": "probe2-fanout-p100",
        "pass": True,
        "n_units": N,
        "created": created,
        "caps": caps,
        "contrib_len_min": contrib_sorted[0],
        "contrib_len_p50": percentile(contrib_sorted, 50),
        "contrib_len_p90": percentile(contrib_sorted, 90),
        "contrib_len_p100": p100_contrib,
        "resolved_len_min": resolved_sorted[0],
        "resolved_len_p50": percentile(resolved_sorted, 50),
        "resolved_len_p90": percentile(resolved_sorted, 90),
        "resolved_len_p100": p100_resolved,
        "all_contrib_at_or_under_cap": p100_contrib <= root_cap,
        "longest_leaf": longest["leaf"],
        "longest_unit_id": longest["unit_id"],
        "longest_contrib_len": longest["contrib_len"],
        "longest_resolved_len": longest["resolved_len"],
        "prefixes": list(PREFIXES),
        "measurement": "os.lstat + Path.name on 256 mkdir'd worktrees",
        "convention_planted_absent": True,
        "independent_of_probe1": True,
    }
    if not payload["all_contrib_at_or_under_cap"]:
        return fail(f"p100 contrib {p100_contrib} > cap {root_cap}")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n={N} p100_contrib={p100_contrib}/{root_cap} "
        f"p100_resolved={p100_resolved} longest={longest['leaf']}"
    )
    print("SUCCESS:TST-0204-probe2 256-unit fan-out p100 under declared cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
