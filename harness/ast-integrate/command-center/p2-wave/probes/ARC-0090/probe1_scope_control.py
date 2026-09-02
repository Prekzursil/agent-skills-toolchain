#!/usr/bin/env python3
"""Probe 1: wrong-scope disable is inert; effective-scope disable holds.

Catalog evidence pair:
  1. the configuration file that holds the setting
  2. the live OS process table (independent /proc walk, not Adapter._children)

Both-states: conforming adapter still spawns under a user-scope disable
when project is enabled; the any-scope-disable mutant does not spawn, so
first-scope-wins is what kept the process alive.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cases import SCOPE_CASES, SERVER  # noqa: E402
from model import (  # noqa: E402
    Adapter,
    Policy,
    SCOPE_FILE,
    STUB,
    iter_marked_pids,
    process_table_count,
    resolve_enabled,
)

ART = REPO / "command-center/phase4/contracts/ARC-0090.json"
SENTINEL = "SUCCESS:ARC-0090"
DECL = {"command": ["python3", str(STUB)]}


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0090-probe1 {msg}")
    return 1


def independent_proc_pids(mark: str) -> list[int]:
    """Duplicate /proc walk so this probe is not a wrapper around the model census."""
    found: list[int] = []
    proc = Path("/proc")
    needle = mark.encode("utf-8")
    stub = b"stub_server.py"
    self_pid = os.getpid()
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == self_pid:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if stub in raw and needle in raw:
            found.append(pid)
    return sorted(found)


def load_scope_file(config_dir: Path, scope: str) -> dict:
    path = config_dir / SCOPE_FILE[scope]
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ARC-0090":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    table = doc.get("scope_decision_table") or []
    if len(table) < 6:
        return fail(f"table rows={len(table)} want>=6")

    by_id = {c["id"]: c for c in SCOPE_CASES}
    nfail = 0
    for row in table:
        rid = row.get("id")
        src = by_id.get(rid)
        if src is None:
            print(f"FAILED:ARC-0090-probe1 unknown row {rid}")
            nfail += 1
            continue
        live = resolve_enabled(src["enable"], SERVER, any_scope_disable=False)
        if live["enabled"] != row.get("computed_enabled"):
            print(
                f"FAILED:ARC-0090-probe1 {rid} live={live['enabled']} "
                f"stored={row.get('computed_enabled')}"
            )
            nfail += 1
            continue
        print(
            f"row {rid} enabled={live['enabled']} "
            f"scope={live['effective_scope']} family={row.get('family')}"
        )

    if len(table) != len(SCOPE_CASES):
        print(f"FAILED:ARC-0090-probe1 stored={len(table)} cases={len(SCOPE_CASES)}")
        nfail += 1

    enabled_vals = {r["computed_enabled"] for r in table}
    if enabled_vals != {True, False}:
        print(f"FAILED:ARC-0090-probe1 table not two-sided {enabled_vals}")
        nfail += 1

    mark_ok = f"p1ok{uuid.uuid4().hex[:10]}"
    mark_mut = f"p1mu{uuid.uuid4().hex[:10]}"
    with tempfile.TemporaryDirectory(prefix="arc0090-p1-") as tmp:
        config_dir = Path(tmp) / "good"
        with Adapter(config_dir=config_dir, mark=mark_ok) as good:
            good.set_enabled(SERVER, True, scope="project")
            good.set_enabled(SERVER, False, scope="user")
            wrong = good.mount(SERVER, transport="stdio", declaration=DECL)
            user_doc = load_scope_file(config_dir, "user")
            user_shows_disable = user_doc.get("enabled", {}).get(SERVER) is False
            pids_indep = independent_proc_pids(mark_ok)
            pids_model = iter_marked_pids(mark_ok)
            proc_present = len(pids_indep) >= 1 and wrong.get("pid") in pids_indep
            print(
                f"inert-user-disable config_shows_false={user_shows_disable} "
                f"mounted={wrong.get('mounted')} "
                f"proc_indep={pids_indep} proc_model={pids_model}"
            )
            if not user_shows_disable:
                print("FAILED:ARC-0090-probe1 user config did not hold the disable")
                nfail += 1
            if not (wrong.get("mounted") and proc_present):
                print("FAILED:ARC-0090-probe1 user disable was not inert on the process table")
                nfail += 1
            if pids_indep != pids_model:
                print(f"FAILED:ARC-0090-probe1 census mismatch {pids_indep} vs {pids_model}")
                nfail += 1
            if process_table_count(mark_ok) != len(pids_indep):
                print("FAILED:ARC-0090-probe1 library count diverged from independent /proc")
                nfail += 1
            good.unmount(SERVER)

            good.set_enabled(SERVER, False, scope="project")
            right = good.mount(SERVER, transport="stdio", declaration=DECL)
            project_doc = load_scope_file(config_dir, "project")
            project_shows_disable = project_doc.get("enabled", {}).get(SERVER) is False
            pids_after = independent_proc_pids(mark_ok)
            print(
                f"effective-project-disable config_shows_false={project_shows_disable} "
                f"mounted={right.get('mounted')} proc_indep={pids_after}"
            )
            if not project_shows_disable:
                print("FAILED:ARC-0090-probe1 project config did not hold the disable")
                nfail += 1
            if right.get("mounted") or pids_after:
                print("FAILED:ARC-0090-probe1 project disable still left a process")
                nfail += 1

        mutant_dir = Path(tmp) / "mutant"
        with Adapter(
            config_dir=mutant_dir,
            mark=mark_mut,
            policy=Policy(any_scope_disable=True),
        ) as mutant:
            mutant.set_enabled(SERVER, True, scope="project")
            mutant.set_enabled(SERVER, False, scope="user")
            treated_real = mutant.mount(SERVER, transport="stdio", declaration=DECL)
            mutant_pids = independent_proc_pids(mark_mut)
            fired = (not treated_real.get("mounted")) and not mutant_pids
            print(
                f"mutant-any-scope-disable mounted={treated_real.get('mounted')} "
                f"proc={mutant_pids} fired_on_bad={fired}"
            )
            if not fired:
                print("FAILED:ARC-0090-probe1 mutant did not treat user disable as real")
                nfail += 1

    if nfail:
        print(f"FAILED:ARC-0090-probe1 failures={nfail}")
        return 1
    print("asserted=scope-table+config-file+process-table")
    print("SUCCESS:ARC-0090-probe1 scope control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
