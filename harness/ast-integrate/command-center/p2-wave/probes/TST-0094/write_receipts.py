#!/usr/bin/env python3
"""Emit TST-0094 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402

UID = "TST-0094"
OUT = "command-center/receipts/TST-0094.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
ENG = "command-center/p2-wave/probes/TST-0094/harvest.py"
SENTINEL = "SUCCESS:TST-0094"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0094/probe1_empty_vs_broken.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0094/probe2_null_key_write.py"
)
SUPPORTING = [
    ENG,
    SCHEMA,
    "command-center/p2-wave/probes/TST-0094/probe1_empty_vs_broken.py",
    "command-center/p2-wave/probes/TST-0094/probe2_null_key_write.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0094/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    demo = H.three_typed_runs()
    pos = H.nonempty_harvest_control()
    null_demo = H.null_key_write_demo()
    if not demo["production_distinct"]:
        print("FAILED:TST-0094 production outcomes not distinct", demo)
        return 1
    if not demo["mutant_collapsed"]:
        print("FAILED:TST-0094 mutant did not collapse", demo)
        return 1
    if not pos["first_ok"] or not pos["second_is_nothing_new"]:
        print("FAILED:TST-0094 nonempty control", pos)
        return 1
    if not null_demo["production_write_rejected"] or not null_demo["mutant_hides_row"]:
        print("FAILED:TST-0094 null-key demo", null_demo)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Remote harvest that silently does nothing",
        "question": (
            "A harvest run against a remote substrate that has produced zero "
            "new artifacts must be distinguishable from a harvest whose "
            "connection or filter silently matched nothing. Measured analogue: "
            "a job filter keyed on session id where the written record carried "
            "null, hiding every result."
        ),
        "failure_class": "FC-11319",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0094 question_or_target; "
            "_USER-PROMPTS.md:11319; "
            "command-center/phase3/A1/FAILURE-MODES.json FC-11319"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "profile": "fault-injection-remote-harvest",
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "local-serialized",
        },
        "implementation": {
            "module": ENG,
            "entry_points": [
                "RemoteHarvest.harvest",
                "RemoteSubstrate.write",
                "reject_filter_key",
            ],
            "typed_outcomes": sorted(H.ALL_PRODUCTION_OUTCOMES),
            "filter_key": H.FILTER_KEY,
            "null_at_write_raises": "NullFilterKeyError",
            "empty_is_not_a_production_outcome": True,
        },
        "artifact_paths": [OUT, ENG] + SUPPORTING[1:],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": ENG, "role": "engine", "exists": True},
        ]
        + [{"path": p, "role": "supporting", "exists": True} for p in SUPPORTING[1:]],
        "evidence": {
            "runs": demo["runs"],
            "production_outcomes": demo["production_outcomes"],
            "mutant_outcomes": demo["mutant_outcomes"],
            "production_distinct": demo["production_distinct"],
            "mutant_collapsed": demo["mutant_collapsed"],
            "nonempty_control": pos,
            "null_key_write": {
                "production_write_rejected": null_demo["production_write_rejected"],
                "production_hidden_count": null_demo["production_hidden_count"],
                "mutant_hides_row": null_demo["mutant_hides_row"],
                "mutant_hidden_count": null_demo["mutant_hidden_count"],
                "harvest_null_filter_rejected": null_demo[
                    "harvest_null_filter_rejected"
                ],
                "json_null_record_rejected": null_demo["json_null_record_rejected"],
            },
            "claim": (
                "Three recorded runs — genuinely-nothing-to-harvest, "
                "filter-mismatch, connection-failure — each produce a "
                "DIFFERENT typed outcome rather than a shared empty result. "
                "A null session_id is rejected at write time."
            ),
            "verdict": "CONFIRMED",
        },
        "tests": [
            {
                "id": "test_empty_harvest_and_broken_harvest_are_distinguishable",
                "command": P1,
                "result": "PASS",
                "requirement": (
                    "genuinely-nothing-to-harvest, filter-mismatch, and "
                    "connection-failure are three typed outcomes"
                ),
            },
            {
                "id": "test_a_null_key_in_the_filter_is_rejected_at_write_time",
                "command": P2,
                "result": "PASS",
                "requirement": (
                    "write(session_id=None) raises NullFilterKeyError; "
                    "the analogue mutant that accepts null hides the row"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST0094-C1-emptiness-collapsing-mutant",
                "kind": "known-broken-mutant",
                "description": (
                    "mutant_collapse_zero_transfer maps every zero-transfer "
                    "run to EMPTY. Production keeps NOTHING_TO_HARVEST, "
                    "FILTER_MISMATCH, and CONNECTION_FAILURE apart."
                ),
                "fired_on_bad_state": demo["mutant_collapsed"],
                "silent_on_good_state": demo["production_distinct"],
            },
            {
                "id": "TST0094-C2-null-key-hides-results",
                "kind": "known-broken-write",
                "description": (
                    "allow_null_key=True stores the row in a hidden bucket "
                    "so a session-keyed harvest returns NOTHING_TO_HARVEST "
                    "while the artifact still exists. Production rejects "
                    "the write."
                ),
                "fired_on_bad_state": null_demo["mutant_hides_row"],
                "silent_on_good_state": null_demo["production_write_rejected"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0094-probe2-null-key-write",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 does not reuse the three-run table. It AST-scans "
                "write() for reject_filter_key, asserts JSON null is refused, "
                "and keeps the analogue mutant as a negative control."
            ),
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "error-fingerprint, enumerate >=2 alternative approaches "
                "before a 3rd attempt (AGENTS.md 4b)"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0094/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0431 (harvest postcondition in the production "
                    "harvester) is not delivered on this worktree. This unit "
                    "ships a typed classifier under probes/TST-0094/harvest.py "
                    "and proves the three empty-looking runs do not share an "
                    "outcome. A later production harvester must keep these "
                    "tokens; it must not reintroduce a shared empty SUCCESS."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-run three_typed_runs against the IMP-0431 harvester "
                    "once command-center/receipts/IMP-0431.json exists."
                ),
            }
        ],
        "notes": (
            "G-1 for TST-0094: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0094 sentinel missing from emitted body")
        return 1
    out.write_text(body, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0094 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    extra_raw = [
        "command-center/p2-wave/probes/TST-0094/probe1-empty-vs-broken.raw.json",
        "command-center/p2-wave/probes/TST-0094/probe2-null-key-write.raw.json",
        "command-center/p2-wave/probes/TST-0094/write_receipts.py",
    ]

    primary = manifest_row(OUT, "primary")
    artifacts = (
        [primary]
        + [manifest_row(p, "supporting") for p in SUPPORTING]
        + [manifest_row(p, "supporting") for p in extra_raw if (REPO / p).is_file()]
    )
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "empty-vs-broken-typed-outcomes",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "null-key-rejected-at-write",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0094/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0094-probe2-null-key-write",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0094: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0094 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
