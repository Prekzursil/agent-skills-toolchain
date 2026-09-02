"""Executable dry-run vs real-run scenario for IMP-0227.

Computes (does not assert) declared-vs-observed write sets and side-effect
counters. Positive fixtures must be supersets. The under-declare fixture must
fail the superset check so a detector that always-passes cannot credit.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

from dryrun import (  # noqa: E402
    compare_trees,
    dry_run,
    execute,
    tree_digest,
    writes_superset,
)

POSITIVE = ("wf-linear.json", "wf-fanout.json", "wf-nested.json")
UNDERDECLARE = "wf-underdeclare.json"
ESCAPE_SPAWN = "wf-escape-spawn.json"
ESCAPE_EGRESS = "wf-escape-egress.json"
ESCAPE_WRITE = "wf-escape-write.json"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run_pair(name: str) -> dict[str, Any]:
    wf = load_fixture(name)
    dry = dry_run(wf)
    with tempfile.TemporaryDirectory(prefix="imp0227-real-") as tmp:
        real = execute(wf, Path(tmp))
        on_disk = sorted(
            p.relative_to(tmp).as_posix()
            for p in Path(tmp).rglob("*")
            if p.is_file()
        )
    sup = writes_superset(dry.declared_writes, real.observed_writes)
    disk_sup = writes_superset(dry.declared_writes, on_disk)
    return {
        "fixture": name,
        "workflow_id": wf.get("id"),
        "dry": dry.as_dict(),
        "real": real.as_dict(),
        "on_disk_writes": on_disk,
        "superset": sup,
        "disk_superset": disk_sup,
        "estimate_vs_actual": {
            "estimate_micro_cost": dry.estimate["micro_cost"],
            "actual_micro_cost": real.actual["micro_cost"],
            "estimate_blast": dry.estimate["blast_radius"],
            "actual_blast": real.actual["blast_radius"],
            "same_units": True,
            "micro_cost_estimate_ge_actual": dry.estimate["micro_cost"]
            >= real.actual["micro_cost"],
        },
        "zero_side_effects_dry": dry.ports.spawns == 0 and dry.ports.egress == 0,
        "dry_violation": dry.violation,
    }


def measure_side_effects() -> dict[str, Any]:
    wf = load_fixture("wf-linear.json")
    with tempfile.TemporaryDirectory(prefix="imp0227-dry-") as tmp:
        root = Path(tmp)
        (root / "canary.txt").write_text("unchanged\n", encoding="utf-8")
        before = tree_digest(root)
        result = dry_run(wf, workspace=root)
        after = tree_digest(root)
        tree = compare_trees(before, after)
        # both-states: the same workflow in real mode MUST change the tree
        real_root = root / "real-ws"
        real_root.mkdir()
        (real_root / "canary.txt").write_text("unchanged\n", encoding="utf-8")
        before_real = tree_digest(real_root)
        execute(wf, real_root)
        after_real = tree_digest(real_root)
        real_tree = compare_trees(before_real, after_real)
    return {
        "dry_tree": tree,
        "real_tree": real_tree,
        "dry_ports": result.ports.snapshot(),
        "dry_violation": result.violation,
        "detector_silent_on_dry": tree["identical"]
        and result.ports.spawns == 0
        and result.ports.egress == 0,
        "detector_fires_on_real_writes": real_tree["identical"] is False,
        "both_states": True,
    }


def measure_mutants() -> dict[str, Any]:
    spawn = dry_run(load_fixture(ESCAPE_SPAWN))
    egress = dry_run(load_fixture(ESCAPE_EGRESS))
    write = dry_run(load_fixture(ESCAPE_WRITE))
    return {
        "spawn": {
            "spawns": spawn.ports.spawns,
            "egress": spawn.ports.egress,
            "violation": spawn.violation,
            "fired": spawn.ports.spawns >= 1,
        },
        "egress": {
            "spawns": egress.ports.spawns,
            "egress": egress.ports.egress,
            "violation": egress.violation,
            "fired": egress.ports.egress >= 1,
        },
        "write": {
            "violation": write.violation,
            "fired": write.violation is not None
            and str(write.violation).startswith("write:"),
        },
    }


def measure_all() -> dict[str, Any]:
    positives = [run_pair(name) for name in POSITIVE]
    under = run_pair(UNDERDECLARE)
    side = measure_side_effects()
    mutants = measure_mutants()
    all_superset = all(
        p["superset"]["ok"] and p["disk_superset"]["ok"] for p in positives
    )
    under_fails = under["superset"]["ok"] is False
    return {
        "positives": positives,
        "underdeclare": under,
        "side_effects": side,
        "mutants": mutants,
        "all_positive_superset": all_superset,
        "underdeclare_fails_as_required": under_fails,
        "zero_side_effects_on_good_dry_run": side["detector_silent_on_dry"],
        "real_run_changes_tree": side["detector_fires_on_real_writes"],
        "spawn_mutant_trips_counter": mutants["spawn"]["fired"],
        "egress_mutant_trips_counter": mutants["egress"]["fired"],
        "write_mutant_refused": mutants["write"]["fired"],
        "pass": (
            all_superset
            and under_fails
            and side["detector_silent_on_dry"]
            and side["detector_fires_on_real_writes"]
            and mutants["spawn"]["fired"]
            and mutants["egress"]["fired"]
            and mutants["write"]["fired"]
        ),
    }
