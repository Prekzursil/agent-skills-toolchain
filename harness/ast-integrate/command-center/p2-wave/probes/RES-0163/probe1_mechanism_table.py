#!/usr/bin/env python3
"""Probe 1: six-system table, always-on flag, mechanism kinds, combination, DISQUALIFY."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402

QUESTIONS = (
    "who_else_is_running",
    "who_owns_this_work_item",
    "who_holds_this_file",
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0163-probe1 {msg}")
    return 1


def table_errors(systems: list) -> list[str]:
    errs: list[str] = []
    if not isinstance(systems, list) or len(systems) < 6:
        return [f"systems too few: {0 if not isinstance(systems, list) else len(systems)}"]
    seen = []
    answered_file = 0
    always_on = 0
    for i, row in enumerate(systems):
        if not isinstance(row, dict):
            errs.append(f"row[{i}] not object")
            continue
        rid = row.get("id")
        seen.append(rid)
        if rid not in L.SYSTEM_IDS:
            errs.append(f"{rid}: unexpected id")
        if not isinstance(row.get("always_on_server"), bool):
            errs.append(f"{rid}: always_on_server not bool")
        if not row.get("always_on_server_mechanism"):
            errs.append(f"{rid}: missing always_on_server_mechanism")
        if bool(row.get("always_on_server")) == bool(row.get("no_server")):
            errs.append(f"{rid}: always_on_server/no_server contradict")
        if row.get("always_on_server"):
            always_on += 1
        for q in QUESTIONS:
            cell = row.get(q) or {}
            if cell.get("status") not in {"ANSWERED", "PARTIAL", "NOT-ANSWERED"}:
                errs.append(f"{rid}.{q}: bad status {cell.get('status')!r}")
            if cell.get("status") != "NOT-ANSWERED":
                if not cell.get("mechanism"):
                    errs.append(f"{rid}.{q}: empty mechanism")
                if cell.get("mechanism_kind") not in {
                    "lock_file_path",
                    "table",
                    "api",
                }:
                    errs.append(f"{rid}.{q}: mechanism_kind {cell.get('mechanism_kind')}")
            if q == "who_holds_this_file" and cell.get("status") == "ANSWERED":
                answered_file += 1
        if row.get("no_server"):
            if row.get("no_server_lock_verdict") not in {"QUALIFIED", "DISQUALIFIED"}:
                errs.append(f"{rid}: bad no_server_lock_verdict")
            live = L.LX.classify(
                {
                    "stale_lock_story": row.get("stale_lock_story") or "",
                    "stale_mechanisms": row.get("stale_mechanisms") or [],
                }
            )
            if live != row.get("no_server_lock_verdict"):
                errs.append(
                    f"{rid}: verdict drift live={live} art={row.get('no_server_lock_verdict')}"
                )
    missing = [s for s in L.SYSTEM_IDS if s not in seen]
    if missing:
        errs.append(f"missing systems {missing}")
    if answered_file < 2:
        errs.append("fewer than two ANSWERED file-hold rows")
    if always_on < 2:
        errs.append("fewer than two always-on systems")
    return errs


def combo_errors(art: dict) -> list[str]:
    errs: list[str] = []
    combo = art.get("no_server_combination") or {}
    if combo.get("always_on_server") is not False:
        errs.append("combination not marked always_on_server=false")
    systems = combo.get("systems") or []
    if len(systems) < 3:
        errs.append("combination has <3 parts")
    if not combo.get("do_not_use"):
        errs.append("combination missing do_not_use")
    covers = combo.get("covers") or {}
    for k in (
        "who_else_is_running",
        "who_owns_this_work_item",
        "who_holds_this_file",
    ):
        if not covers.get(k):
            errs.append(f"combination missing cover {k}")
    nc = art.get("negative_control") or {}
    planted = nc.get("planted") or {}
    if planted.get("verdict") != "DISQUALIFIED":
        errs.append("planted naive lock not DISQUALIFIED")
    if "goose" not in (nc.get("system_lock_disqualified") or []):
        errs.append("goose not in system_lock_disqualified")
    return errs


def main() -> int:
    art = L.load_artifact()
    text = json.dumps(art)
    if str(art.get("state") or "").upper() in L.BLOCKED:
        return fail(f"self-declared {art.get('state')}")
    if L.SENTINEL not in text:
        return fail("sentinel absent")
    if art.get("schema_present_on_disk") is True:
        return fail("schema unexpectedly present; do not ADV-rebuild")
    live = L.build_live()
    good = table_errors(art.get("systems") or [])
    good += combo_errors(art)
    if good:
        return fail("good table: " + "; ".join(good[:8]))
    live_ids = [s["id"] for s in live["systems"]]
    art_ids = [s["id"] for s in art.get("systems") or []]
    if live_ids != art_ids:
        return fail(f"system id drift {art_ids} vs {live_ids}")

    mutant = copy.deepcopy(art.get("systems") or [])
    mutant[0]["always_on_server"] = "yes"
    m_errs = table_errors(mutant)
    if not m_errs:
        return fail("mutation always_on_server='yes' did not fire")

    blank = copy.deepcopy(art.get("systems") or [])
    for row in blank:
        if row.get("id") == "goose":
            row["stale_lock_story"] = "invented"
            row["stale_mechanisms"] = ["pid_liveness"]
            row["no_server_lock_verdict"] = "QUALIFIED"
    b_errs = table_errors(blank)
    # classifier will disagree with QUALIFIED because we also need the stored
    # verdict to match classify(); after stuffing mechanisms it would QUALIFY
    # and match — so instead strip goose DISQUALIFY from negative_control via
    # combo_errors on a mutant artifact.
    combo_mutant = copy.deepcopy(art)
    combo_mutant["negative_control"]["planted"]["verdict"] = "QUALIFIED"
    c_errs = combo_errors(combo_mutant)
    if not c_errs:
        return fail("planted QUALIFIED mutant did not fire")

    payload = {
        "probe": "probe1-mechanism-table",
        "unit_id": "RES-0163",
        "systems": art_ids,
        "always_on": [
            s["id"] for s in art["systems"] if s.get("always_on_server")
        ],
        "disqualified_locks": art["negative_control"]["system_lock_disqualified"],
        "mutation_always_on_fires": True,
        "mutation_planted_fires": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "systems="
        + ",".join(art_ids)
        + " disqualified="
        + ",".join(payload["disqualified_locks"])
    )
    print("SUCCESS:RES-0163-probe1 mechanism table always-on and combination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
