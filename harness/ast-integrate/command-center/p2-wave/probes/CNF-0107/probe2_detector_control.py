#!/usr/bin/env python3
"""Probe 2: detector control — mechanically different from the inventory census.

Fault-injects three broken uninstalls (orphan, scorched-earth, poison marker)
and requires the comparator to fire on each bad state and stay silent on the
healthy uninstall. A detector that cannot see residue is disqualified.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from compare import compare  # noqa: E402
from lifecycle import ORPHAN_LEFT, run_cycle  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0107-probe2 {msg}")
    return 1


def _run(tmp: Path, mode: str) -> dict:
    cycle = run_cycle(tmp / mode, mode=mode)  # type: ignore[arg-type]
    findings = compare(cycle["pre"], cycle["post_install"], cycle["post_uninstall"])
    findings["reinstall"] = cycle["reinstall"]
    findings["mode"] = mode
    return findings


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0107-p2-") as raw:
        tmp = Path(raw)
        good = _run(tmp, "healthy")
        orphan = _run(tmp, "leave_orphan")
        scorch = _run(tmp, "scorch")
        poison = _run(tmp, "poison")

    if good["orphans"] or good["data_loss"] or not good["out_of_scope_intact"]:
        return fail(f"healthy uninstall not silent {good}")
    if not good["reinstall"].get("succeeded"):
        return fail("healthy reinstall failed")

    if not orphan["orphans"]:
        return fail("leave_orphan did not surface owned residue")
    if not any(row["path"] == ORPHAN_LEFT for row in orphan["orphans"]):
        return fail(f"orphan paths {orphan['orphans']}")

    scorch_fires = bool(scorch["data_loss"]) or not scorch["out_of_scope_intact"]
    if not scorch_fires:
        return fail("scorched-earth uninstall was silent (detector blind)")

    if not poison["reinstall"].get("attempted"):
        return fail("poison reinstall not attempted")
    if poison["reinstall"].get("succeeded"):
        return fail("poisoned marker still allowed reinstall")
    if not poison["reinstall"].get("poisoned"):
        return fail("poisoned state not classified")

    # Both-states: same comparator, two outcomes.
    if not (
        not bool(good["orphans"])
        and bool(orphan["orphans"])
        and scorch_fires
        and not poison["reinstall"]["succeeded"]
    ):
        return fail("both-states discriminator collapsed")

    summary = {
        "probe": "probe2-detector-control",
        "unit_id": "CNF-0107",
        "silent_on_good": True,
        "orphan_fired": True,
        "scorch_fired": True,
        "poison_blocked_reinstall": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "good_silent=True orphan_fired=True scorch_fired=True "
        "poison_blocked_reinstall=True"
    )
    print("SUCCESS:CNF-0107-probe2 detector control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
