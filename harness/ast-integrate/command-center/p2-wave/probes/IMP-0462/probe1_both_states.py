#!/usr/bin/env python3
"""Named probe 1: both-states — both-unique REFUSED, one-directional PERMITTED."""
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
from host import host_census  # noqa: E402
from sync.classifier import DIVERGED_BOTH_UNIQUE, REPO_LARGER  # noqa: E402
from sync.synchronizer import PERMIT, REFUSE, apply_sync  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0462-probe1 {msg}")
    return 1


def main() -> int:
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="imp0462-p1-") as tmp:
        spec = materialize(Path(tmp))
        refused = apply_sync(
            Path(spec["refuse_repo"]),
            Path(spec["refuse_live"]),
            direction="repo-to-live",
            apply=True,
        )
        permitted = apply_sync(
            Path(spec["permit_repo"]),
            Path(spec["permit_live"]),
            direction="repo-to-live",
            apply=True,
        )
        live_to_repo_refuse = apply_sync(
            Path(spec["refuse_repo"]),
            Path(spec["refuse_live"]),
            direction="live-to-repo",
            apply=True,
        )
        dest = Path(spec["permit_live"]) / spec["permit_path"]
        src = Path(spec["permit_repo"]) / spec["permit_path"]
        copied_ok = dest.is_file() and src.is_file() and dest.read_bytes() == src.read_bytes()

    host_after = host_census()
    if host_before != host_after:
        return _fail("host live tree fingerprint changed")

    if refused.get("tree_action") != REFUSE or refused.get("ok") is not False:
        return _fail(f"both-unique was not refused: {refused.get('tree_action')}")
    if refused.get("writes_executed") != 0:
        return _fail(f"refuse path wrote {refused.get('writes_executed')} files")
    if not refused.get("live_unchanged") or not refused.get("repo_unchanged"):
        return _fail("both-unique apply mutated a tree")
    rows = {r["path"]: r for r in refused["rows"]}
    hit = rows.get(spec["refuse_path"])
    if hit is None or hit["classification"] != DIVERGED_BOTH_UNIQUE:
        return _fail("refuse fixture not classified diverged-both-unique")
    if hit["action"] != REFUSE:
        return _fail(f"both-unique action={hit['action']}")
    if hit["repo_unique_line_count"] < 1 or hit["live_unique_line_count"] < 1:
        return _fail("refuse fixture is not both-unique")

    if permitted.get("tree_action") != PERMIT or permitted.get("ok") is not True:
        return _fail(f"one-directional was not permitted: {permitted.get('tree_action')}")
    if permitted.get("writes_executed") < 1:
        return _fail("permitted apply executed zero writes")
    if permitted.get("live_unchanged") is not False:
        return _fail("permitted apply did not update live")
    if permitted.get("repo_unchanged") is not True:
        return _fail("permitted apply mutated repo")
    if not copied_ok:
        return _fail("permitted copy did not reproduce repo bytes on live")
    prow = {r["path"]: r for r in permitted["rows"]}.get(spec["permit_path"])
    if prow is None or prow["classification"] != REPO_LARGER:
        return _fail("permit fixture not classified repo-larger")
    if prow["live_unique_line_count"] != 0 or prow["repo_unique_line_count"] < 1:
        return _fail("permit fixture is not purely one-directional")

    if live_to_repo_refuse.get("tree_action") != REFUSE:
        return _fail("both-unique live-to-repo was not refused")

    out = {
        "probe": "probe1-both-states",
        "unit_id": "IMP-0462",
        "both_states": {
            "bad_refused": True,
            "good_permitted": True,
            "refuse_writes": refused["writes_executed"],
            "permit_writes": permitted["writes_executed"],
        },
        "both_unique_refused": True,
        "one_directional_permitted": True,
        "host_present_nonempty_trees": host_after["present_nonempty_trees"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "refuse=REFUSE writes=0 permit=PERMIT writes="
        f"{permitted['writes_executed']} both_states=True"
    )
    print("SUCCESS:IMP-0462-probe1 both-unique refused, one-directional permitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
