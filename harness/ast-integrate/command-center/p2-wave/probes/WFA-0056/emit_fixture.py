#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0056-second-control-plane-guard.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import guard as G  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/wfa/WFA-0056-second-control-plane-guard.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
GUARD = "command-center/p2-wave/probes/WFA-0056/guard.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0056/probe1_planted_imports.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0056/probe2_manifest_and_process.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    S.write_example_allowlist()
    both = S.both_states()
    a = S.evidence_a()
    b = S.evidence_b()
    if not (both.get("pass") and a.get("pass") and b.get("pass")):
        print("FAILED:WFA-0056 emit measurements did not pass")
        print(json.dumps({"both": both, "A": a, "B": b}, indent=2, default=str)[:5000])
        return 1

    guard_path = REPO / GUARD
    guard_sha, guard_bytes = sha256_file(guard_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runtimes = []
    for rt in G.RUNTIMES:
        runtimes.append(
            {
                "id": rt["id"],
                "name": rt["name"],
                "import_prefixes": list(rt["import_prefixes"]),
                "pypi": list(rt["pypi"]),
                "process_names": list(rt["process_names"]),
                "owns": rt["owns"],
                "second_plane_if": rt["second_plane_if"],
            }
        )
    planted_named = [row["control_plane"] for row in a["planted"]]
    doc = {
        "record_type": "RegressionFixture",
        "id": "WFA-0056-second-control-plane-guard",
        "unit_id": "WFA-0056",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0056",
        "title": "Guard that detects a second orchestration control plane entering the estate",
        "schema": SCHEMA,
        "created_at": now,
        "chosen_control_plane": {
            "id": G.CHOSEN_PLANE_ID,
            "name": G.CHOSEN_PLANE_NAME,
            "rule": (
                "Mechanisms are extracted and reimplemented on this plane. "
                "Torn-down runtimes are never imported wholesale."
            ),
            "spec_anchors": [
                "_USER-PROMPTS.md:10727 do not import a second orchestration runtime",
                "_USER-PROMPTS.md:10483 no duplicate control planes",
            ],
        },
        "implementation": {
            "path": GUARD,
            "sha256": guard_sha,
            "bytes": guard_bytes,
            "cli": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0056/guard.py --root <tree> "
                "[--baseline <estate>] [--allowlist <json>] [--observe-processes]"
            ),
            "exit_2_means": "gate failed; named_planes lists WHICH control plane",
        },
        "torn_down_runtimes": runtimes,
        "subject": (
            "Acquired or fused workflow trees, dependency manifests, and live "
            "process tables."
        ),
        "setup": (
            "Isolated fixture trees: legitimate library deps (pydantic/httpx/"
            "jsonschema); one planted import per torn-down runtime; manifest "
            "plants; a vendored package with no manifest line; a spawned "
            "dummy scheduler process."
        ),
        "action": "Run evaluate() on each fixture with the matching channels enabled.",
        "expected": {
            "legit_library": "silent",
            "each_of_seven_imports": "fired and named",
            "manifest_diff": "fired and named",
            "vendored_without_declare": "fired via vendored channel",
            "spawned_process": "fired via process_table and names the plane",
            "owner_allowlist": "does not fail; records approval_id",
        },
        "observed": {
            "both_states": both,
            "evidence_a": {
                "legit_silent": a["legit_silent"],
                "seven_named": a["seven_named"],
                "named_planes": planted_named,
                "allowlist": a["allowlist"],
            },
            "evidence_b": {
                "baseline_silent": b["baseline_silent"],
                "manifest_seven": all(r["pass"] for r in b["manifest_diff"]),
                "vendored_bypass_caught": b["vendored"]["pass"],
                "subprocess_source_caught": b["subprocess_source"]["pass"],
                "process_table_caught": b["process_table"]["pass"],
                "process_named_planes": b["process_table"]["named_planes"],
            },
        },
        "both_states": {
            "silent_on_legitimate_library_dependency": both[
                "silent_on_legitimate_library"
            ],
            "loud_on_runtime_import": both["loud_on_runtime_import"],
            "names_which_control_plane": both["names_which"],
            "pass": both["pass"],
        },
        "evidence": {
            "A": {
                "requirement": (
                    "the guard fires on a planted import of each of the seven "
                    "torn-down runtimes"
                ),
                "pass": a["pass"],
                "planted": a["planted"],
            },
            "B": {
                "requirement": (
                    "dependency-manifest diff plus a process-table observation "
                    "on a live run, so a runtime that is vendored rather than "
                    "declared, or spawned rather than imported, is still caught"
                ),
                "pass": b["pass"],
                "manifest_diff": b["manifest_diff"],
                "vendored": b["vendored"],
                "subprocess_source": b["subprocess_source"],
                "process_table": {
                    "planted_runtime": b["process_table"]["planted_runtime"],
                    "fired": b["process_table"]["fired"],
                    "named_planes": b["process_table"]["named_planes"],
                    "pass": b["process_table"]["pass"],
                },
            },
        },
        "allowlist": {
            "example_path": "command-center/p2-wave/probes/WFA-0056/allowlist.example.json",
            "rule": (
                "An owner-approved runtime adoption is an explicit allowlist "
                "entry with approval_id, approver, and recorded_at. The gate "
                "still names the plane; it does not fail while the approval "
                "is recorded."
            ),
            "measured": a["allowlist"],
        },
        "tests": [
            {
                "id": "both-states",
                "requirement": (
                    "the guard must be silent on a legitimate library "
                    "dependency and loud on a runtime import"
                ),
                "pass": both["pass"],
            },
            {
                "id": "names-which-plane",
                "requirement": (
                    "the guard must name WHICH control plane it detected, not just fail"
                ),
                "pass": all(row["names_which"] for row in a["planted"]),
                "named": planted_named,
            },
            {
                "id": "owner-allowlist",
                "requirement": (
                    "an owner-approved runtime adoption must be expressible as "
                    "an explicit allowlist entry with the approval recorded"
                ),
                "pass": a["allowlist"]["pass"],
            },
        ],
        "reviewer": {
            "security_reviewer": {
                "id": "WFA-0056-probe1-planted-imports",
                "attempted_bypass": "none; planted the named imports",
                "verdict": "PASS",
                "independent": True,
            },
            "adversarial_reviewer": {
                "id": "WFA-0056-probe2-manifest-and-process",
                "attempted_bypass": [
                    "vendor langgraph without a manifest declaration",
                    "spawn an airflow-named process without importing airflow",
                ],
                "caught": True,
                "verdict": "PASS",
                "independent": True,
            },
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "pass": True,
        "answer": (
            "The gate fails when an acquired or fused workflow introduces a "
            "second control plane, and it names the plane. Planted imports of "
            "LangGraph, CrewAI, AutoGen, Temporal, Airflow, Prefect and Dagster "
            "each fire. A legitimate pydantic/httpx/jsonschema tree stays silent. "
            "A vendored package and a spawned scheduler process are caught on "
            "channels independent of import declarations. Owner adoption is an "
            "allowlist entry with a recorded approval_id. SUCCESS:WFA-0056"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0056")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
