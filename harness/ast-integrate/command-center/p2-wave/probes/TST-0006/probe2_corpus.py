#!/usr/bin/env python3
"""Probe 2: corpus P/R vs committed labels, overclaim, fence-strip mutation."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from path_linter import UNVERIFIED, VERIFIED, lint_file, lint_payload  # noqa: E402
from score import score_payloads  # noqa: E402

ART = REPO / "command-center/receipts/TST-0006.json"
LABELS = HERE / "labels.json"
SCHEMA = REPO / "command-center/schema/test-receipt.schema.json"
ILLUS = "command-center/p2-wave/probes/TST-0006/fixtures/ILLUSTRATIVE-ONLY-ABSENT.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0006-probe2 {msg}")
    return 1


def _close(a, b, tol: float = 1e-12) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    if not ART.is_file():
        return _fail("receipt missing")
    if not LABELS.is_file():
        return _fail("labels.json missing")
    if not SCHEMA.is_file():
        return _fail("test-receipt schema missing")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    missing = [k for k in schema.get("required", []) if k not in doc]
    if missing:
        return _fail(f"schema-required-missing:{missing}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:TST-0006" not in ART.read_text(encoding="utf-8"):
        return _fail("sentinel-absent")
    if labels.get("n") != 100 or len(labels.get("payloads") or []) != 100:
        return _fail(f"labels n={labels.get('n')} want 100")

    paths = []
    for row in labels["payloads"]:
        rel = str(row.get("path") or "")
        path = REPO / rel
        if not path.is_file():
            return _fail(f"labelled-payload-absent:{rel}")
        paths.append(path)

    live = score_payloads(paths, REPO)
    metrics = doc.get("metrics") or {}
    for axis in ("token", "payload"):
        want = metrics.get(axis) or {}
        got = live[axis]
        for key in ("tp", "fp", "fn", "precision", "recall"):
            if not _close(want.get(key), got.get(key)):
                return _fail(f"overclaim {axis}.{key} receipt={want.get(key)} live={got.get(key)}")
    illus_r = (metrics.get("illustrative") or {}).get("false_positive_rate")
    illus_l = live["illustrative"]["false_positive_rate"]
    if not _close(illus_r, illus_l):
        return _fail(f"overclaim illustrative.fp receipt={illus_r} live={illus_l}")

    # Labels must match a fresh gold pass (committed labels are not a frozen lie).
    for i, (row, path) in enumerate(zip(labels["payloads"], paths)):
        from gold_label import label_file

        gold = label_file(path, REPO)
        if gold["gold_status"] != row.get("gold_status"):
            return _fail(f"label-drift[{i}] {path.name}")
        if list(gold["should_flag"]) != list(row.get("should_flag") or []):
            return _fail(f"should_flag-drift[{i}] {path.name}")

    # Fence-strip mutation: the planted illustrative path must be silent with
    # stripping and flagged without it.
    md = HERE / "fixtures" / "fenced_mention.md"
    ok = lint_file(md, REPO)
    mutant = lint_payload(md.read_text(encoding="utf-8"), REPO, strip_fences=False)
    print(f"fenced_control status={ok.status} mutant={mutant.status}")
    if ok.status != VERIFIED or any(ILLUS in p for p in ok.flagged_paths):
        return _fail(f"planted fenced path flagged: {ok.flagged_paths}")
    if mutant.status != UNVERIFIED or not any(ILLUS in p for p in mutant.flagged_paths):
        return _fail(f"fence-strip mutant did not fire: {mutant.flagged_paths}")

    # Receipt must not claim a 1.0 that live did not earn.
    mutant_doc = copy.deepcopy(doc)
    mutant_doc["metrics"]["token"]["precision"] = 1.0
    if _close(mutant_doc["metrics"]["token"]["precision"], live["token"]["precision"]):
        print("note: live token precision is already 1.0; overclaim mutant skipped")
    else:
        if _close(1.0, live["token"]["precision"]):
            return _fail("precision-1 live unexpectedly")
        print("overclaim_mutant precision=1.0 rejected against live")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return _fail("reviewer not independent")

    tests = doc.get("tests") or []
    if any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        return _fail("receipt tests not all PASS")

    print(
        "live token P={p} R={r} illus_fp={fp} n={n}".format(
            p=live["token"]["precision"],
            r=live["token"]["recall"],
            fp=live["illustrative"]["false_positive_rate"],
            n=live["n_payloads"],
        )
    )
    print("SUCCESS:TST-0006-probe2 corpus-pr overclaim fence-mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
