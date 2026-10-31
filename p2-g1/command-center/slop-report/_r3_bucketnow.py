"""Four-bucket classification of every untracked candidate, at the CURRENT rev.

Reuses what already shipped rather than rebuilding it: the census comes from
`_g2_census.py`, EXECUTED as a subprocess. The first version of this probe read
`_g2_census.out.json` off disk instead -- and that file is a stale shell
redirect, because `_g2_census.py` only ever writes to stdout. It reported
`__pycache__` at 1,676 files / 47.5 MB while the live tree held 2,644 / 59.8 MB,
and nothing in the probe could tell. So the fix ships with the control that
would have caught it: `c6_census_rev_is_current` compares the artifact's OWN
recorded head against `git rev-parse HEAD` and fails closed when they differ.

The same control is applied to `_g2_classify.out.json`, which is NOT re-executed
(it is a ~10 s index-wide scan owned by the grounding lane); its numbers are
reported with their rev attached and flagged when that rev is not HEAD, rather
than silently presented as current.

Run:  python command-center/slop-report/_r3_bucketnow.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
OUT = Path(__file__).with_suffix(".out.json")


def sh(args: list[str]) -> str:
    return subprocess.run(
        args, cwd=REPO, capture_output=True, check=True
    ).stdout.decode("utf-8", "replace")


def main() -> int:
    rev = sh(["git", "rev-parse", "HEAD"]).strip()

    untracked = [
        p
        for p in sh(["git", "ls-files", "-z", "--others", "--exclude-standard"]).split(
            "\0"
        )
        if p
    ]
    tracked = {p for p in sh(["git", "ls-files", "-z"]).split("\0") if p}

    # EXECUTED, not read off disk.
    census = json.loads(
        subprocess.run(
            [sys.executable, str(HERE / "_g2_census.py")],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    )
    classify = json.loads((HERE / "_g2_classify.out.json").read_text(encoding="utf-8"))
    classify_head = str(classify.get("head", ""))[:8]

    by_tree: dict[str, int] = {}
    for p in untracked:
        key = p.split("/", 1)[0] if "/" in p else "<root>"
        by_tree[key] = by_tree.get(key, 0) + 1

    ghost = f"command-center/{uuid.uuid4().hex}.py"
    controls = {
        "c1_untracked_nonempty": bool(untracked),
        "c2_untracked_disjoint_from_tracked": not (set(untracked) & tracked),
        "c3_uuid_in_neither": ghost not in tracked and ghost not in set(untracked),
        "c4_census_has_caches": "caches" in census,
        "c5_classify_loaded": bool(classify.get("buckets_n")),
        # the control that would have caught the stale read
        "c6_census_rev_is_current": str(census.get("head", ""))[:8] == rev[:8],
    }

    payload = {
        "rev": rev,
        "untracked_total": len(untracked),
        "tracked_total": len(tracked),
        "untracked_by_tree": dict(sorted(by_tree.items(), key=lambda kv: -kv[1])),
        "caches": census.get("caches"),
        "caches_total_files": census.get("caches_total_files"),
        "caches_total_bytes": census.get("caches_total_bytes"),
        "empty_dirs": census.get("empty_dirs"),
        "empty_dirs_n": census.get("empty_dirs_n"),
        "frozen": census.get("frozen"),
        "classify_rev": classify_head,
        "classify_rev_is_current": classify_head == rev[:8],
        "classify_buckets_n": classify.get("buckets_n"),
        "classify_bucket_b_bytes": classify.get("bucket_b_bytes"),
        "classify_bucket_d_bytes": classify.get("bucket_d_bytes"),
        "classify_target_scope": classify.get("target_scope"),
        "controls": controls,
        "all_controls_pass": all(controls.values()),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"rev={rev}")
    print(f"untracked={len(untracked)} tracked={len(tracked)}")
    print(f"by tree: {payload['untracked_by_tree']}")
    print(
        f"caches: {payload['caches_total_files']} files / "
        f"{payload['caches_total_bytes']} bytes  {payload['caches']}"
    )
    print(f"empty dirs: {payload['empty_dirs_n']}")
    print(f"frozen: {payload['frozen']}")
    print(
        f"classify buckets (rev {classify_head}, current={payload['classify_rev_is_current']}): "
        f"{payload['classify_buckets_n']} scope={payload['classify_target_scope']}"
    )
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-bucketnow a control did not pass")
        return 1
    print(f"SUCCESS:r3-bucketnow -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
