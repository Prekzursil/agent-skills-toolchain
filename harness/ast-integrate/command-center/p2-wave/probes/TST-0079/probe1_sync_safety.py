#!/usr/bin/env python3
"""Probe 1: sync refuses a diverged pair and proceeds on a one-directional pair.

Required tests:
  test_sync_refuses_on_a_diverged_pair
  test_sync_proceeds_on_a_strictly_one_directional_pair

Also runs the known-broken control: naive overwrite of the diverged pair
destroys the live-unique line (the Copy-Item -Force defect).
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
import sync_tool as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0079.json"
OUT = HERE / "probe1-sync-safety.raw.json"
REPO_UNIQUE = "REPO-UNIQUE-LINE:gamma"
LIVE_UNIQUE = "LIVE-UNIQUE-LINE:delta"
REPO_AHEAD_UNIQUE = "REPO-UNIQUE-LINE:alpha"
LIVE_AHEAD_UNIQUE = "LIVE-UNIQUE-LINE:beta"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0079-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:3000])
    return 1


def test_sync_refuses_on_a_diverged_pair(repo: Path, live: Path) -> dict:
    rel = "common/diverged.md"
    rp, lp = repo / rel, live / rel
    before_r, before_l = rp.read_bytes(), lp.read_bytes()
    if REPO_UNIQUE.encode() not in before_r or LIVE_UNIQUE.encode() not in before_l:
        raise AssertionError("diverged fixture missing unique lines")

    r2l = S.apply_sync_pair(rp, lp, S.DIR_REPO_TO_LIVE)
    after_r, after_l = rp.read_bytes(), lp.read_bytes()
    if r2l["decision"] != S.REFUSE or r2l["class_before"] != S.DIVERGED:
        raise AssertionError(f"repo-to-live did not refuse diverged: {r2l}")
    if after_r != before_r or after_l != before_l:
        raise AssertionError("diverged pair mutated on refused repo-to-live")
    if LIVE_UNIQUE.encode() not in after_l or REPO_UNIQUE.encode() not in after_r:
        raise AssertionError("unique lines lost on refused sync")

    l2r = S.apply_sync_pair(rp, lp, S.DIR_LIVE_TO_REPO)
    after_r2, after_l2 = rp.read_bytes(), lp.read_bytes()
    if l2r["decision"] != S.REFUSE:
        raise AssertionError(f"live-to-repo did not refuse diverged: {l2r}")
    if after_r2 != before_r or after_l2 != before_l:
        raise AssertionError("diverged pair mutated on refused live-to-repo")

    tree = S.sync_trees(repo, live, S.DIR_REPO_TO_LIVE)
    if not tree["refused"] or rel not in tree["blocking"]:
        raise AssertionError(f"tree sync did not refuse on diverged: {tree}")
    if rp.read_bytes() != before_r or lp.read_bytes() != before_l:
        raise AssertionError("tree refuse mutated files")

    return {
        "id": "test_sync_refuses_on_a_diverged_pair",
        "result": "PASS",
        "repo_to_live": r2l["decision"],
        "live_to_repo": l2r["decision"],
        "tree_blocking": tree["blocking"],
        "bytes_preserved": True,
    }


def test_sync_proceeds_on_a_strictly_one_directional_pair(root: Path) -> dict:
    trees = F.write_trees(root / "one-dir")
    repo, live = trees["repo"], trees["live"]
    rel = "common/repo-ahead.md"
    rp, lp = repo / rel, live / rel
    before_live = lp.read_bytes()
    if REPO_AHEAD_UNIQUE.encode() in before_live:
        raise AssertionError("live already had repo-unique line")

    result = S.apply_sync_pair(rp, lp, S.DIR_REPO_TO_LIVE)
    if result["decision"] != S.PROCEED or result["class_before"] != S.REPO_AHEAD:
        raise AssertionError(f"repo-ahead repo-to-live did not proceed: {result}")
    after_live = lp.read_bytes()
    if after_live != rp.read_bytes():
        raise AssertionError("repo-ahead live did not become repo bytes")
    if REPO_AHEAD_UNIQUE.encode() not in after_live:
        raise AssertionError("repo-unique line not copied")

    wrong = S.apply_sync_pair(
        repo / "common/live-ahead.md",
        live / "common/live-ahead.md",
        S.DIR_REPO_TO_LIVE,
    )
    if wrong["decision"] != S.REFUSE or wrong["class_before"] != S.LIVE_AHEAD:
        raise AssertionError(f"live-ahead repo-to-live must refuse: {wrong}")
    live_ahead_live = (live / "common/live-ahead.md").read_bytes()
    if LIVE_AHEAD_UNIQUE.encode() not in live_ahead_live:
        raise AssertionError("live-ahead unique line destroyed")

    ok_live = S.apply_sync_pair(
        repo / "common/live-ahead.md",
        live / "common/live-ahead.md",
        S.DIR_LIVE_TO_REPO,
    )
    if ok_live["decision"] != S.PROCEED:
        raise AssertionError(f"live-ahead live-to-repo did not proceed: {ok_live}")
    if (repo / "common/live-ahead.md").read_bytes() != (
        live / "common/live-ahead.md"
    ).read_bytes():
        raise AssertionError("live-ahead repo did not become live bytes")

    return {
        "id": "test_sync_proceeds_on_a_strictly_one_directional_pair",
        "result": "PASS",
        "repo_ahead_repo_to_live": result["decision"],
        "live_ahead_repo_to_live": wrong["decision"],
        "live_ahead_live_to_repo": ok_live["decision"],
    }


def naive_overwrite_destroys_diverged(root: Path) -> dict:
    trees = F.write_trees(root / "naive")
    repo, live = trees["repo"], trees["live"]
    rel = "common/diverged.md"
    rp, lp = repo / rel, live / rel
    live_before = lp.read_bytes()
    S.naive_overwrite(rp, lp)
    live_after = lp.read_bytes()
    destroyed = LIVE_UNIQUE.encode() in live_before and LIVE_UNIQUE.encode() not in live_after
    if not destroyed:
        raise AssertionError("naive overwrite control did not destroy live-unique line")
    return {
        "id": "naive_overwrite_destroys_diverged",
        "kind": "known-broken-control",
        "fired_on_bad_state": True,
        "destroyed_live_unique": True,
        "result": "PASS",
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0079":
        return fail("unit_id", doc.get("unit_id"))
    if "SUCCESS:TST-0079" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="tst0079-p1-") as tmp:
        root = Path(tmp)
        trees = F.write_trees(root / "base")
        t1 = test_sync_refuses_on_a_diverged_pair(trees["repo"], trees["live"])
        t2 = test_sync_proceeds_on_a_strictly_one_directional_pair(root)
        ctrl = naive_overwrite_destroys_diverged(root)

    payload = {"pass": True, "probe": "probe1-sync-safety", "unit_id": "TST-0079", "tests": [t1, t2, ctrl]}
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "refused_diverged=True proceeded_one_directional=True "
        "naive_overwrite_destroys=True"
    )
    print("SUCCESS:TST-0079-probe1 sync refuses diverged and proceeds one-directional")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
