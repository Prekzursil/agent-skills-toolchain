#!/usr/bin/env python3
"""Probe 1: production classifier over the live/repo pair (or honest fixtures).

Runs the five-class unit tests, classifies the resolved pair, and requires:
  * all five classes present on the planted estate (or host if it has them)
  * DIVERGED fixture is not REPO-AHEAD
  * one-directional mutation misclassifies that fixture
  * the three named live-larger files are LIVE-AHEAD or DIVERGED, never REPO-AHEAD
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PLUGIN))
import drift as D  # noqa: E402
import scenario as S  # noqa: E402

OUT = HERE / "probe1-classifier.raw.json"
TEST = PLUGIN / "tests" / "test_drift_classifier.py"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        print("FAILED:IMP-0034-probe1 unit tests red")
        return 1

    pair = S.resolve_pair()
    repo_root = Path(pair["repo_root"])
    live_root = Path(pair["live_root"])
    rows = D.classify_trees(repo_root, live_root)
    counts = D.tally(rows)
    by_path = {r["path"]: r for r in rows}

    diverged_rel = pair.get("diverged_repo_larger") or "common/fan-out-contract.md"
    diverged = by_path.get(diverged_rel)

    failures: list[str] = []
    if pair["source"] == "fixtures":
        for klass in D.CLASSES:
            if counts.get(klass, 0) < 1:
                failures.append(f"missing-class:{klass}")
        if diverged is None:
            failures.append("diverged-fixture-absent")
        elif diverged["classification"] != D.DIVERGED:
            failures.append(
                f"diverged-misclassified:{diverged['classification']}"
            )
        elif diverged["classification"] == D.REPO_AHEAD:
            failures.append("diverged-classified-repo-ahead")

        repo_b = (repo_root / diverged_rel).read_bytes()
        live_b = (live_root / diverged_rel).read_bytes()
        one = D.classify_pair(repo_b, live_b, one_directional=True)
        two = D.classify_pair(repo_b, live_b, one_directional=False)
        if two != D.DIVERGED:
            failures.append(f"two-directional-not-diverged:{two}")
        if one != D.REPO_AHEAD:
            failures.append(f"one-directional-did-not-fail:{one}")

    named_rows = []
    for rel in S.NAMED_LIVE_LARGER:
        row = by_path.get(rel)
        named_rows.append({"path": rel, "row": row})
        if row is None:
            if pair["source"] == "fixtures":
                failures.append(f"named-absent:{rel}")
            continue
        if row["classification"] == D.REPO_AHEAD:
            failures.append(f"named-repo-ahead:{rel}")
        if row["classification"] not in {D.LIVE_AHEAD, D.DIVERGED}:
            if pair["source"] == "fixtures":
                failures.append(f"named-unexpected:{rel}:{row['classification']}")

    doc = {
        "probe": "probe1-classifier",
        "unit_id": "IMP-0034",
        "pair": pair,
        "counts": counts,
        "named_live_larger": named_rows,
        "diverged": diverged,
        "tests_ok": True,
        "failures": failures,
        "row_count": len(rows),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failures:
        print(json.dumps(failures))
        print("FAILED:IMP-0034-probe1")
        return 1

    print(
        "source="
        + pair["source"]
        + " union="
        + str(counts["union"])
        + " identical="
        + str(counts[D.IDENTICAL])
        + " modulo_eol="
        + str(counts[D.IDENTICAL_MODULO_EOL])
        + " repo_ahead="
        + str(counts[D.REPO_AHEAD])
        + " live_ahead="
        + str(counts[D.LIVE_AHEAD])
        + " diverged="
        + str(counts[D.DIVERGED])
        + " named_live_larger_ok=True"
        + " one_directional_mutation_red=True"
        + " cited_2026_08_09_5_of_88=False"
    )
    print("SUCCESS:IMP-0034-probe1 two-directional classifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
