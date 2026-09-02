#!/usr/bin/env python3
"""Named probe 2: EOL is not content drift; second differ recomputes; naive misses."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixtures import materialize  # noqa: E402
from sync.classifier import (  # noqa: E402
    DIVERGED_BOTH_UNIQUE,
    EOL_ONLY,
    IDENTICAL,
    classify_trees,
)
from sync.second_differ import classify_trees as classify_trees_second  # noqa: E402
from sync.second_differ import disagreements  # noqa: E402
from sync.synchronizer import PERMIT, apply_sync  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0462.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0462-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0462-p2-") as tmp:
        spec = materialize(Path(tmp))
        census = classify_trees(Path(spec["census_repo"]), Path(spec["census_live"]))
        second = classify_trees_second(
            Path(spec["census_repo"]), Path(spec["census_live"])
        )
        eol_plan = apply_sync(
            Path(spec["eol_repo"]),
            Path(spec["eol_live"]),
            direction="repo-to-live",
            apply=True,
        )
        dest = Path(spec["eol_live"]) / spec["eol_path"]
        src = Path(spec["eol_repo"]) / spec["eol_path"]
        eol_copied_ok = (
            dest.is_file() and src.is_file() and dest.read_bytes() == src.read_bytes()
        )

    expected = spec["expected"]
    counts = census["classification_counts"]
    for key, want in (
        ("identical", expected["identical"]),
        ("eol-only", expected["eol_only"]),
        ("repo-larger", expected["repo_larger"]),
        ("live-larger", expected["live_larger"]),
        ("diverged-both-unique", expected["diverged_both_unique"]),
    ):
        got = counts.get(key)
        if got != want:
            return _fail(f"census {key}={got} want={want}")

    if census["union_files"] != expected["union_files"]:
        return _fail(f"union={census['union_files']} want={expected['union_files']}")

    diffs = disagreements(census["rows"], second["rows"])
    if diffs:
        return _fail(f"second differ disagrees: {diffs[:5]}")
    if second["classification_counts"] != counts:
        return _fail("second differ counts do not match")

    by_path = {r["path"]: r for r in census["rows"]}
    eol_row = by_path.get(spec["eol_path"])
    if eol_row is None or eol_row["classification"] != EOL_ONLY:
        return _fail("EOL fixture not classified eol-only")
    if eol_row.get("content_divergence") is not False:
        return _fail("EOL-only flagged as content divergence")

    identical_rows = [r for r in census["rows"] if r["classification"] == IDENTICAL]
    if not identical_rows:
        return _fail("classifier flagged everything; identical control failed")

    naive_misses = census["naive_misses_both_unique"]
    if len(naive_misses) != expected["diverged_both_unique"]:
        return _fail(
            f"naive size summary missed {len(naive_misses)} both-unique, "
            f"want {expected['diverged_both_unique']}"
        )
    for rel in naive_misses:
        row = by_path[rel]
        if row["classification"] != DIVERGED_BOTH_UNIQUE:
            return _fail(f"{rel} listed as naive miss but not both-unique")
        if row["naive_size_class"] == DIVERGED_BOTH_UNIQUE:
            return _fail(f"{rel} naive unexpectedly detected both-unique")
        if row["byte_direction"] != "repo-larger":
            return _fail(f"{rel} planted both-unique should be byte-repo-larger")

    if eol_plan.get("tree_action") != PERMIT or eol_plan.get("ok") is not True:
        return _fail("EOL-only tree was refused as if it were content drift")
    if eol_plan.get("writes_executed") < 1:
        return _fail("EOL permit copy executed zero writes")
    if not eol_copied_ok:
        return _fail("EOL permit did not copy repo bytes")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"artifact self-declared {doc.get('state')}")
        art_counts = doc.get("classification_counts") or {}
        for key in (
            "identical",
            "eol-only",
            "repo-larger",
            "live-larger",
            "diverged-both-unique",
        ):
            if key not in art_counts:
                return _fail(f"artifact missing classification_counts.{key}")
        findings = doc.get("findings") or {}
        if findings.get("eol_not_content_divergence") is not True:
            return _fail("artifact missing eol_not_content_divergence")
        if findings.get("second_differ_agrees") is not True:
            return _fail("artifact missing second_differ_agrees")
        reviewers = doc.get("reviewers") or []
        if len(reviewers) < 2:
            return _fail("artifact missing two independent reviewers")

    out = {
        "probe": "probe2-eol-and-second-differ",
        "unit_id": "IMP-0462",
        "classification_counts": counts,
        "second_differ_disagreements": 0,
        "eol_not_content_divergence": True,
        "identical_control": True,
        "naive_misses_both_unique": naive_misses,
        "eol_permitted": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "eol_only="
        f"{counts['eol-only']} diverged={counts['diverged-both-unique']} "
        f"naive_misses={len(naive_misses)} second_agree=True"
    )
    print("SUCCESS:IMP-0462-probe2 EOL not content-divergence; second differ agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
