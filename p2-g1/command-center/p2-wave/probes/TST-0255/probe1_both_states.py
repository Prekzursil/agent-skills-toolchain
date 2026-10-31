#!/usr/bin/env python3
"""TST-0255 probe 1: both-states internal-anchor control.

GOOD state: the fixture blob at the fixture revision HAS line 10 -> OK. BAD
states: line 1010 -> BEYOND-EOF; missing path -> MISSING. The shape-only
detector control proves a path:digits regex accepts the off-by-1000
(known-broken fixture fires), while the cat-file checker reports it. The
probe also records the live worktree's object-store fact (the receipt's
documented REFUTED residual: this tree carries no git object store, so the
full docs-conformance PASS conjunction is false on this tree - a documented
residual, not a probe failure).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from blob import resolve_anchor, shape_only_accepts, worktree_has_object_store  # noqa: E402

FIXTURE_DIR = HERE / "fixtures" / "anchor-store"


def ensure_fixture() -> tuple[str, str]:
    """Idempotently create the fixture git store (rev = commit); return (rev, path)."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    target = FIXTURE_DIR / "target.txt"
    if not target.is_file():
        lines = [f"fixture line {i}" for i in range(1, 21)]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    rev_file = FIXTURE_DIR / "rev.txt"
    if rev_file.is_file():
        rev = rev_file.read_text(encoding="utf-8").strip()
        if rev:
            return rev, "target.txt"
    subprocess.run(
        ["git", "init", "-q", str(FIXTURE_DIR)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "-C", str(FIXTURE_DIR), "add", "target.txt"],
        check=True,
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "-C", str(FIXTURE_DIR), "-c", "user.name=p2-fixture",
         "-c", "user.email=p2-fixture@invalid", "commit", "-q", "-m",
         "TST-0255 anchor fixture: 20-line target.txt"],
        check=True,
        capture_output=True,
        timeout=120,
    )
    p = subprocess.run(
        ["git", "-C", str(FIXTURE_DIR), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    rev = p.stdout.strip()
    rev_file.write_text(rev + "\n", encoding="utf-8", newline="\n")
    return rev, "target.txt"


def main() -> int:
    checks: dict[str, bool] = {}
    rev, path = ensure_fixture()
    good = resolve_anchor(rev, path, 10, FIXTURE_DIR)
    checks["good_line_10_ok"] = good["classification"] == "OK"
    off1000 = resolve_anchor(rev, path, 1010, FIXTURE_DIR)
    checks["off_by_1000_beyond_eof"] = off1000["classification"] == "BEYOND-EOF"
    missing = resolve_anchor(rev, "no-such-target.txt", 1, FIXTURE_DIR)
    checks["missing_reported"] = missing["classification"] == "MISSING"
    checks["fixture_line_count_20"] = good.get("line_count") == 20
    checks["shape_only_accepts_off_by_1000"] = shape_only_accepts(path, 1010)
    checks["worktree_has_no_object_store_documented"] = (
        worktree_has_object_store(REPO) is False
    )

    out = {
        "probe": "probe1_both_states",
        "unit": "TST-0255",
        "signal": "(a) internal anchor resolution via git cat-file plus line-count",
        "fixture_rev": rev,
        "fixture_line_count": good.get("line_count"),
        "good_classification": good["classification"],
        "off_by_1000_classification": off1000["classification"],
        "missing_classification": missing["classification"],
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-both-states.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
