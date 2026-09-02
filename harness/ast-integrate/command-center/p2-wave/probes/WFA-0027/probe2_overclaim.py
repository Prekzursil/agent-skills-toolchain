#!/usr/bin/env python3
"""Probe 2: overclaim / license-before-quote / published-source anchors.

Independent of probe1's behavioural sketch: re-read the artifact and the
cached published sources. A planted overclaim (Temporal Worker is SEPARABLE)
must be REFUTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:probe2 repo root not found")


REPO = repo_root(HERE)
sys.path.insert(0, str(HERE))

from mechanisms import MECHANISMS  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json"
CACHE = HERE / "cache"
LIC = HERE / "licenses.json"

REQUIRED_RUNTIMES = {
    "langgraph",
    "crewai",
    "autogen",
    "temporal",
    "airflow",
    "prefect",
    "dagster",
}
REQUIRED_MECHS = {
    "state_model",
    "checkpointing",
    "retry_semantics",
    "human_in_the_loop",
    "fan_out_and_barrier",
    "resume",
}


def licenses_before_mechanisms(raw: str) -> bool:
    i_lic = raw.find('"licenses"')
    i_mech = raw.find('"mechanisms"')
    return i_lic != -1 and i_mech != -1 and i_lic < i_mech


def excerpt_ok(row: dict) -> bool:
    cache = CACHE / Path(row["source_anchor"]["cache"]).name
    if not cache.is_file():
        return False
    lines = cache.read_text(encoding="utf-8", errors="replace").splitlines()
    line_no = int(row["source_anchor"]["line"])
    excerpt = row["source_anchor"]["excerpt"]
    if line_no < 1 or line_no > len(lines):
        return False
    return excerpt in lines[line_no - 1]


def refute_overclaim() -> bool:
    """Planted claim: Temporal Worker poller is SEPARABLE. Must REFUTE."""
    worker = [
        m
        for m in MECHANISMS
        if m["runtime"] == "temporal"
        and m["mechanism"] in {"state_model", "checkpointing", "resume"}
    ]
    if not worker:
        return False
    planted = {
        "runtime": "temporal",
        "mechanism": "state_model",
        "verdict": "SEPARABLE",
        "claim": "temporalio.worker.Worker is a library, not a control plane",
    }
    truth = next(m for m in worker if m["mechanism"] == "state_model")
    return truth["verdict"] == "NON-SEPARABLE" and planted["verdict"] != truth["verdict"]


def main() -> int:
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    lic = json.loads(LIC.read_text(encoding="utf-8"))
    rows = doc.get("mechanisms") or []
    runtime_set = {r["runtime"] for r in rows}
    mech_set = {r["mechanism"] for r in rows}

    checks = {
        "licenses_file_flag": lic.get("recorded_before_any_excerpt") is True,
        "licenses_before_mechanisms": licenses_before_mechanisms(raw),
        "seven_runtimes": runtime_set == REQUIRED_RUNTIMES,
        "six_mechanisms": REQUIRED_MECHS <= mech_set,
        "all_excerpts": all(excerpt_ok(r) for r in rows),
        "license_per_runtime": {r["id"] for r in lic["runtimes"]} == REQUIRED_RUNTIMES,
        "overclaim_temporal_worker_refuted": refute_overclaim(),
        "wholesale_second_plane_seven": len(
            doc.get("second_control_plane_if_imported_wholesale") or []
        )
        == 7,
        "sentinel": "SUCCESS:WFA-0027" in raw,
        "not_blocked": str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"},
        "tests_non_separable": (doc.get("tests_required") or {}).get(
            "non_separable_rejected_not_sketched"
        )
        is True,
    }
    print(json.dumps(checks, indent=1))
    if not all(checks.values()):
        print("FAILED:WFA-0027-probe2 overclaim/license/anchor")
        return 1
    print("SUCCESS:WFA-0027-probe2 overclaim anchors license-before-quote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
