#!/usr/bin/env python3
"""Probe 2: partial-failure census matches the documented all-or-nothing guarantee.

Independent of probe 1: this is a filesystem census after a mid-collection kill,
plus the negative control that a mutually incompatible pair fails at definition
(no lockfile is written).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.collections import (  # noqa: E402
    CollectionDefinitionError,
    build_demo_index,
    define_collection,
    incompatible_collection,
    install_collection,
    observed_matches_guarantee,
    re_toolchain_collection,
)


def main() -> int:
    index = build_demo_index()
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td)
        try:
            define_collection(incompatible_collection(), index, lock_dir=dest)
            unsat_ok = False
            unsat_pair = None
            unsat_msg = "define_collection returned success"
        except CollectionDefinitionError as exc:
            unsat_ok = exc.stage == "definition" and exc.pair == (
                "capstone",
                "keystone",
            )
            unsat_pair = list(exc.pair) if exc.pair else None
            unsat_msg = str(exc)
        unsat_locks = list(dest.glob("*.lock.json"))

        defined = define_collection(re_toolchain_collection(), index)
        killed = install_collection(
            defined.lockfile, dest / "killed", index=index, fail_after=1
        )
        ok = install_collection(
            defined.lockfile, dest / "ok", index=index
        )
        leftover = []
        pkgs = dest / "killed" / "pkgs"
        if pkgs.is_dir():
            leftover = [p.name for p in pkgs.iterdir()]

        payload = {
            "full_install_lock_present": bool(ok.census.get("lock_present")),
            "full_install_members": list(ok.census.get("member_names") or []),
            "full_install_matches_guarantee": observed_matches_guarantee(ok),
            "full_install_status": ok.status,
            "killed_census": killed.census,
            "killed_failed_at": killed.failed_at,
            "killed_leftover_files": leftover,
            "killed_matches_guarantee": observed_matches_guarantee(killed),
            "killed_rolled_back": list(killed.rolled_back),
            "killed_status": killed.status,
            "unsat_definition_time": unsat_ok,
            "unsat_lockfiles": len(unsat_locks),
            "unsat_message": unsat_msg,
            "unsat_pair": unsat_pair,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not (
            unsat_ok
            and len(unsat_locks) == 0
            and killed.status == "rolled-back"
            and killed.rolled_back == ["binwalk"]
            and killed.failed_at == "ghidra"
            and leftover == []
            and observed_matches_guarantee(killed)
            and ok.status == "installed"
            and set(ok.census["member_names"]) == {"binwalk", "ghidra", "radare2"}
            and observed_matches_guarantee(ok)
        ):
            print("FAILED:IMP-0104-probe2 partial-failure census or negative control")
            return 1
        print(
            "SUCCESS:IMP-0104-probe2 all-or-nothing census and "
            "incompatible-pair definition failure"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
