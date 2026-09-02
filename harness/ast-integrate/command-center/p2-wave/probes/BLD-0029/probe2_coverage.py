#!/usr/bin/env python3
"""Probe 2: UNVERIFIED coverage + execute two experiments from text alone."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import harvest as H  # noqa: E402
import parse_register as R  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0029.json"
ALLOW = "command-center/p2-wave/probes/BLD-0029/fixtures/"


def _nested(doc: dict, *keys: str):
    cur: object = doc
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _harvest_block(doc: dict) -> dict:
    for path in (
        ("harvest",),
        ("extensions", "harvest"),
        ("report", "harvest"),
    ):
        block = _nested(doc, *path)
        if isinstance(block, dict) and block.get("tags"):
            return block
    return {}


def _unregistered(doc: dict) -> list:
    for path in (
        ("unregistered",),
        ("extensions", "unregistered"),
        ("report", "unregistered"),
    ):
        rows = _nested(doc, *path)
        if isinstance(rows, list):
            return rows
    return []


def _register(doc: dict) -> dict:
    for path in (
        ("register",),
        ("extensions", "register"),
        ("report", "register"),
    ):
        block = _nested(doc, *path)
        if isinstance(block, dict):
            return block
    return {}


def _execute(experiment: object) -> dict:
    parts = C.experiment_parts(experiment)
    named = C.named_experiment(experiment)
    cmd = parts["command"]
    inp = parts["input"]
    if not named["pass"] or not cmd:
        return {"ran": False, "named": False, "reason": named["reason"]}
    if ALLOW not in cmd.replace("\\", "/"):
        return {"ran": False, "named": True, "reason": "not-allowlisted"}
    full = cmd if not inp or inp in cmd else f"{cmd} {inp}"
    proc = subprocess.run(
        full,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "ran": True,
        "named": True,
        "exit_code": proc.returncode,
        "observation_met": "SETTLED:yes" in out and proc.returncode == 0,
        "stdout": out[-500:],
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:BLD-0029-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0029":
        print("FAILED:BLD-0029-probe2 unit_id", doc.get("unit_id"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:BLD-0029" not in blob:
        print("FAILED:BLD-0029-probe2 sentinel absent")
        return 1

    live = H.harvest_live(REPO)
    recorded_tags = (_harvest_block(doc).get("tags") or [])
    if not recorded_tags:
        print("FAILED:BLD-0029-probe2 harvest tags absent from receipt")
        return 1
    recorded = {
        (t["source_path"], t["json_path"], t["tag"])
        for t in recorded_tags
        if isinstance(t, dict)
    }
    got = {(t["source_path"], t["json_path"], t["tag"]) for t in live}
    # Catalog coverage is UNVERIFIED-in-register-or-unregistered, not a frozen
    # exact-set. Extra live tags (estate growth) are not a unit failure; tags
    # the receipt claimed that vanished are.
    extra = recorded - got
    if extra:
        print(
            f"FAILED:BLD-0029-probe2 harvest claimed-absent extra={len(extra)}"
        )
        print(list(extra)[:5])
        return 1

    planted = H.harvest_tree(
        HERE / "fixtures" / "harvest_tree", REPO, skip_self=False
    )
    unverified = [t for t in planted if t["tag"] == "UNVERIFIED"]
    mentions = [t for t in planted if t["key"] == "documentation"]
    if len(unverified) != 1:
        print(f"FAILED:BLD-0029-probe2 planted UNVERIFIED count={len(unverified)}")
        return 1
    if mentions:
        print("FAILED:BLD-0029-probe2 documentation mention harvested")
        return 1

    unreg_ids = {u["id"] for u in _unregistered(doc) if isinstance(u, dict)}
    register = _register(doc)
    if unverified[0]["id"] not in unreg_ids:
        print("FAILED:BLD-0029-probe2 planted UNVERIFIED not listed unregistered")
        return 1

    live_unv = [t for t in live if t["tag"] == "UNVERIFIED"]
    for tag in live_unv:
        listed = tag["id"] in unreg_ids
        registered = any(
            (u.get("id") == tag["id"]) for u in register.get("rows") or []
        )
        if not listed and not registered:
            print(f"FAILED:BLD-0029-probe2 live UNVERIFIED unlisted {tag['id']}")
            return 1

    rows = {r["id"]: r for r in R.parse_file(HERE / "fixtures" / "register.md")}
    well = _execute(rows["U-WELL-FORMED"]["experiment"])
    vac = _execute(rows["U-VACUOUS"]["experiment"])
    if not well.get("ran") or well.get("exit_code") != 0 or not well.get("observation_met"):
        print(f"FAILED:BLD-0029-probe2 well-formed execute {well}")
        return 1
    if vac.get("ran") or vac.get("named"):
        print(f"FAILED:BLD-0029-probe2 vacuous should be unnamed {vac}")
        return 1

    print(
        f"live_tags={len(live)} live_unverified={len(live_unv)} "
        f"planted_unverified=1 mention=0 well_exec=ok vacuous_unnamed=ok"
    )
    print("SUCCESS:BLD-0029-probe2 coverage+reviewer-execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
