#!/usr/bin/env python3
"""Probe 1: effective-voice counting on an all-identical 8-seat roster.

Catalog falsifier: a council of 8 seats that are 8 copies of one configuration
must report effective independence count of 1. Evidence channel 2: the same
roster's first-round texts are pairwise identical, corroborating the config
verdict. Identity labels and tool-order permutations must not mint voices.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario  # noqa: E402

REPO = scenario.REPO
DUPES_PY = scenario.DUPES_PATH


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0279-probe1 {msg}")
    return 1


def main() -> int:
    if not DUPES_PY.is_file() or DUPES_PY.stat().st_size <= 0:
        return fail(f"module-absent {DUPES_PY.relative_to(REPO).as_posix()}")
    scenario.write_fixture_files()
    dupes = scenario.load_dupes()
    cloned = scenario.roster_eight_copies()
    audit = dupes.audit_roster(cloned["seats"], cloned["outputs"])
    labels = scenario.roster_labels_only()
    labels_audit = dupes.audit_roster(labels["seats"], labels["outputs"])

    checks = {
        "module_path": DUPES_PY.relative_to(REPO).as_posix(),
        "seat_count": audit["seat_count"],
        "effective_independence_count": audit["effective_independence_count"],
        "duplicate_cluster_count": audit["duplicate_cluster_count"],
        "flagged_size": audit["flagged"][0]["size"] if audit["flagged"] else 0,
        "fingerprint_fields": audit["fingerprint_fields"],
        "identity_excluded": audit["identity_fields_excluded"],
        "mean_pairwise_jaccard": audit["similarity"]["mean_pairwise_jaccard"],
        "corroboration": audit["corroboration"]["verdict"],
        "labels_only_independence": labels_audit["effective_independence_count"],
        "cli_eight_copies_independence": None,
    }

    if audit["seat_count"] != 8:
        return fail(f"seat-count {audit['seat_count']}")
    if audit["effective_independence_count"] != 1:
        return fail(
            f"independence={audit['effective_independence_count']} "
            f"(expected 1 for eight copies)"
        )
    if audit["duplicate_cluster_count"] != 1 or audit["flagged"][0]["size"] != 8:
        return fail(f"flagged={audit['flagged']}")
    if set(audit["fingerprint_fields"]) != {
        "vendor",
        "model",
        "system_prompt",
        "tools",
        "context",
    }:
        return fail(f"fingerprint-fields {audit['fingerprint_fields']}")
    if "seat_id" not in audit["identity_fields_excluded"]:
        return fail("seat_id must be excluded from the voice fingerprint")
    if audit["similarity"]["mean_pairwise_jaccard"] < 0.99:
        return fail(f"outputs not identical {audit['similarity']['mean_pairwise_jaccard']}")
    if audit["corroboration"]["verdict"] != "CORROBORATED":
        return fail(f"corroboration {audit['corroboration']}")
    if labels_audit["effective_independence_count"] != 1:
        return fail(
            "labels-only roster minted voices; seat names are not independence"
        )

    # Second instrument: CLI over the on-disk fixture, not the in-memory call.
    import subprocess

    fixture = HERE / "fixtures" / "roster_eight_copies.json"
    proc = subprocess.run(
        [sys.executable, "-B", str(DUPES_PY), "--roster", str(fixture)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return fail(f"cli-exit {proc.returncode} {proc.stderr[-400:]}")
    cli = json.loads(proc.stdout)
    checks["cli_eight_copies_independence"] = cli.get("effective_independence_count")
    if cli.get("effective_independence_count") != 1:
        return fail(f"cli independence {cli.get('effective_independence_count')}")
    if cli.get("corroboration", {}).get("verdict") != "CORROBORATED":
        return fail(f"cli corroboration {cli.get('corroboration')}")

    print(json.dumps(checks, sort_keys=True))
    print(
        "eight_copies independence=1 flagged=8/8 mean_jaccard="
        f"{audit['similarity']['mean_pairwise_jaccard']} "
        f"corroborated={audit['corroboration']['agrees']}"
    )
    print("SUCCESS:IMP-0279-probe1 effective-voice count on eight copies is 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
