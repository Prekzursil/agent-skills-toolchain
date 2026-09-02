#!/usr/bin/env python3
"""Probe 1: mutation fires the extended gate; regeneration silences it; cycles fail.

Does not leave the live sidecar mutated.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import phase_graph as pg  # noqa: E402


def _copy_live(root: Path) -> None:
    src = pg.resolve_authored_path(cat.command_center_dir())
    assert src is not None
    (root / "sources").mkdir(parents=True)
    shutil.copy2(src, root / "sources" / "phase-graph-authored.json")
    pg.write_sidecar(root)


def main() -> int:
    live_rc = pg.check(cat.command_center_dir())
    if live_rc != 0:
        print("FAILED:CC-0016-probe1 live sidecar already drifting")
        return 1
    with tempfile.TemporaryDirectory(prefix="cc-0016-probe1-") as tmp:
        root = Path(tmp) / "command-center"
        _copy_live(root)
        clean_drift = pg.sidecar_drift(root)
        clean_acyclic = True
        doc = json.loads(pg.sidecar_path(root).read_text(encoding="utf-8"))
        clean_acyclic = bool(doc["acyclic"]) and pg.is_acyclic(
            doc["edges"], [p["id"] for p in doc["phases"]]
        )

        mutant = json.loads(pg.sidecar_path(root).read_text(encoding="utf-8"))
        mutant["edges"][0]["to"] = "16"
        pg.sidecar_path(root).write_text(
            json.dumps(mutant, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        mutant_drift = pg.sidecar_drift(root)
        mutant_acyclic = pg.is_acyclic(
            mutant["edges"], [p["id"] for p in mutant["phases"]]
        )

        pg.write_sidecar(root)
        regen_drift = pg.sidecar_drift(root)

        cycled = json.loads(pg.sidecar_path(root).read_text(encoding="utf-8"))
        cycled["edges"].append(
            {
                "id": "E-CYCLE",
                "from": "15",
                "to": "0",
                "kind": "HARD",
                "contested": False,
                "reason": "probe1 planted cycle",
                "author": "CC-0016-probe1",
                "provenance": "authored-from-spec-prose",
            }
        )
        cycle_flag = pg.is_acyclic(
            cycled["edges"], [p["id"] for p in cycled["phases"]]
        )

        result = {
            "unit_id": "CC-0016",
            "probe": "probe1-mutation-regen-acyclicity",
            "live_check_exit": live_rc,
            "unmodified_drift": clean_drift,
            "unmodified_acyclic": clean_acyclic,
            "mutant_drift": mutant_drift,
            "mutant_still_acyclic": mutant_acyclic,
            "regen_drift": regen_drift,
            "planted_cycle_acyclic": cycle_flag,
            "pass": (
                live_rc == 0
                and clean_drift == []
                and clean_acyclic is True
                and bool(mutant_drift)
                and regen_drift == []
                and cycle_flag is False
            ),
        }
        print(json.dumps(result, sort_keys=True))
        if not result["pass"]:
            print("FAILED:CC-0016-probe1 mutation/regen/acyclicity")
            return 1
        print(
            "unmodified_silent=True mutant_fires=True regen_silent=True "
            f"cycle_caught={not cycle_flag}"
        )
        print("SUCCESS:CC-0016-probe1 mutation fires, regen silent, cycle caught")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
