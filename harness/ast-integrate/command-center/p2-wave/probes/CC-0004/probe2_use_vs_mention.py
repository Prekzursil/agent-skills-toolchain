#!/usr/bin/env python3
"""Probe 2: use-vs-mention + independent method-shaped plant + live census."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CC-0004-probe2 {msg}")
    return 1


def locators(rows: list[dict]) -> set[str]:
    return {D.locator(r) for r in rows}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cc0004-p2-") as tmp:
        root = Path(tmp)
        meta = F.write_clean_tree(root)
        plant = F.plant_method_fork(root)
        planted = D.scan(root, skip_prefixes=())
        want_fork = f"{plant['plant_rel']}:{plant['plant_line']}:{plant['plant_name']}"
        if want_fork not in locators(planted["forks"]):
            return fail(
                f"method plant silent want={want_fork} got={locators(planted['forks'])}"
            )
        notes = root / meta["mention_py"]
        text = notes.read_text(encoding="utf-8")
        if "def artifact_delivered" not in text:
            return fail("mention fixture lost payload text")
        mention_forks = [
            h for h in planted["forks"] if h["path"] == meta["mention_py"]
        ]
        if mention_forks:
            return fail(f"use-vs-mention failed: notes.py classified as fork {mention_forks}")
        md = root / meta["mention_md"]
        if not md.is_file() or "artifact_delivered" not in md.read_text(encoding="utf-8"):
            return fail("markdown mention fixture missing payload")
        md_hits = [h for h in planted["forks"] if h["path"] == meta["mention_md"]]
        if md_hits:
            return fail(f"markdown mention fired {md_hits}")

        want_resolved = (
            f"{meta['resolved_rel']}:{meta['resolved_line']}:{meta['resolved_name']}"
        )
        if want_resolved not in locators(planted["resolved"]):
            return fail("independent re-run lost known-present import site")

    live = D.scan(REPO)
    live_forks = locators(live["forks"])
    live_canon = locators(live["canonical"])
    ready = REPO / "command-center" / "ready_units.py"
    if not ready.is_file():
        return fail("live ready_units.py missing")
    ready_line = F.def_lineno(ready, "artifact_delivered")
    want_live = f"command-center/ready_units.py:{ready_line}:artifact_delivered"
    if want_live not in live_forks:
        return fail(f"live known-broken missing {want_live} got={sorted(live_forks)}")
    if not live["shared_module_present"]:
        return fail("CC-0003 reducer missing at platform/lib/completion_predicate.py")
    shared_paths = set(live["shared_module_paths"] or [])
    if "platform/lib/completion_predicate.py" not in shared_paths:
        return fail(f"shared path not classified {sorted(shared_paths)}")
    if not any(
        loc.startswith("platform/lib/completion_predicate.py:")
        and loc.endswith(":is_complete")
        for loc in live_canon
    ):
        return fail(f"canonical is_complete missing got={sorted(live_canon)}")
    extra_sites = (
        ("hooks/bg-registry/_common.py", "artifact_complete"),
        ("platform/lib/workflows/mechanisms.py", "unit_complete"),
    )
    extra_locs = []
    for rel, name in extra_sites:
        path = REPO / rel
        if not path.is_file():
            continue
        loc = f"{rel}:{F.def_lineno(path, name)}:{name}"
        extra_locs.append(loc)
        if loc not in live_forks:
            return fail(f"live fork missing {loc} got={sorted(live_forks)}")

    print(
        f"mention_silent=True method_plant={want_fork} "
        f"live_fork={want_live} extra_forks={extra_locs} "
        f"live_forks={live['fork_count']} "
        f"shared_present={live['shared_module_present']} "
        f"canonical={sorted(live_canon)} files={live['files_scanned']}"
    )
    print("SUCCESS:CC-0004-probe2 use-vs-mention method-plant live-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
