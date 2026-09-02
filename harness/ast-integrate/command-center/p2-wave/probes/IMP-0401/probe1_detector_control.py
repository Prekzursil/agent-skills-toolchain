#!/usr/bin/env python3
"""Probe 1: detector control on planted repo-only, live-only, and both.

Planted repo-only and live-only MUST appear. A capability present in both
must NOT appear in either gap list. Indexed repo-only (and index-only)
must be flagged selectable-but-unloadable.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_presence_gap():
    path = REPO / "tools" / "router" / "presence_gap.py"
    spec = importlib.util.spec_from_file_location("imp0401_presence_gap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sys.path.insert(0, str(HERE))
    import fixtures as F  # noqa: E402

    pg = load_presence_gap()
    report = pg.detect(
        F.fixture_repo_roots(),
        F.fixture_live_roots(),
        index=F.INDEX_PATH,
    )
    if not report["disjoint"]:
        print("FAILED:IMP-0401-probe1 repo_only and live_only overlap")
        print(json.dumps(report["overlap_illegal"]))
        return 1

    repo_only = set(report["repo_only"])
    live_only = set(report["live_only"])
    both = set(report["both"])

    if F.PLANTED_REPO_ONLY not in repo_only:
        print(f"FAILED:IMP-0401-probe1 planted repo-only missing: {sorted(repo_only)}")
        return 1
    if F.PLANTED_LIVE_ONLY not in live_only:
        print(f"FAILED:IMP-0401-probe1 planted live-only missing: {sorted(live_only)}")
        return 1
    if F.PLANTED_BOTH in repo_only or F.PLANTED_BOTH in live_only:
        print(f"FAILED:IMP-0401-probe1 both-present leaked into a gap list both={sorted(both)}")
        return 1
    if F.PLANTED_BOTH not in both:
        print(f"FAILED:IMP-0401-probe1 both-present not classified both={sorted(both)}")
        return 1
    if repo_only != {F.PLANTED_REPO_ONLY}:
        print(f"FAILED:IMP-0401-probe1 unexpected repo_only={sorted(repo_only)}")
        return 1
    if live_only != {F.PLANTED_LIVE_ONLY}:
        print(f"FAILED:IMP-0401-probe1 unexpected live_only={sorted(live_only)}")
        return 1

    indexed = report["indexed"]
    if F.PLANTED_REPO_ONLY not in indexed["repo_only"]:
        print("FAILED:IMP-0401-probe1 indexed repo-only missing")
        return 1
    if F.PLANTED_LIVE_ONLY not in indexed["live_only"]:
        print("FAILED:IMP-0401-probe1 indexed live-only missing")
        return 1
    if F.PLANTED_BOTH in indexed["repo_only"] or F.PLANTED_BOTH in indexed["live_only"]:
        print("FAILED:IMP-0401-probe1 indexed both leaked into a gap list")
        return 1
    unloadable = set(indexed["selectable_but_unloadable"])
    if F.PLANTED_REPO_ONLY not in unloadable:
        print("FAILED:IMP-0401-probe1 repo-only not flagged selectable-but-unloadable")
        return 1
    if F.PLANTED_INDEX_ONLY not in unloadable:
        print("FAILED:IMP-0401-probe1 index-only not flagged selectable-but-unloadable")
        return 1
    if F.PLANTED_BOTH in unloadable or F.PLANTED_LIVE_ONLY in unloadable:
        print("FAILED:IMP-0401-probe1 loadable id flagged unloadable")
        return 1

    by_id = {
        r["capability_id"]: r for r in report["annotated_index"]["capabilities"]
    }
    if by_id[F.PLANTED_REPO_ONLY]["router_defect"] != pg.DEFECT_UNLOADABLE:
        print("FAILED:IMP-0401-probe1 annotated repo-only missing defect")
        return 1
    if by_id[F.PLANTED_REPO_ONLY]["loadable"] is not False:
        print("FAILED:IMP-0401-probe1 annotated repo-only marked loadable")
        return 1
    if by_id[F.PLANTED_BOTH]["router_defect"] is not None:
        print("FAILED:IMP-0401-probe1 annotated both carries a defect")
        return 1
    if by_id[F.PLANTED_BOTH]["loadable"] is not True:
        print("FAILED:IMP-0401-probe1 annotated both not loadable")
        return 1
    if by_id[F.PLANTED_LIVE_ONLY]["presence"] != "live-only":
        print("FAILED:IMP-0401-probe1 annotated live-only presence wrong")
        return 1

    payload = {
        "probe": "probe1-detector-control",
        "unit_id": "IMP-0401",
        "pass": True,
        "repo_only": report["repo_only"],
        "live_only": report["live_only"],
        "both": report["both"],
        "indexed_repo_only_count": indexed["repo_only_count"],
        "indexed_live_only_count": indexed["live_only_count"],
        "selectable_but_unloadable": indexed["selectable_but_unloadable"],
        "method": report["method"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "repo_only="
        + ",".join(report["repo_only"])
        + " live_only="
        + ",".join(report["live_only"])
        + " both="
        + ",".join(report["both"])
        + " unloadable="
        + ",".join(indexed["selectable_but_unloadable"])
    )
    print("SUCCESS:IMP-0401-probe1 detector control planted both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
