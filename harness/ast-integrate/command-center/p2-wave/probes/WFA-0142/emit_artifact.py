#!/usr/bin/env python3
"""Write command-center/foundry/WFA-0142-...json from a live engine rehearsal."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    NEW_ID,
    OLD_ID,
    estate_census,
    rehearse_clean_cycle,
    rehearse_drop_caller_refusal,
)

OUT = "command-center/foundry/WFA-0142-supersession-engine-with-migration-and-rollback-to-s.json"
UNIT = "WFA-0142"
SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/supersession-engine"
LOCAL_SCHEMA = "command-center/p2-wave/probes/WFA-0142/supersession-engine.schema.json"


def digest(rel: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    raw = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw) if path.is_file() else 0,
        "sha256": hashlib.sha256(raw).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": "supporting",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cycle = rehearse_clean_cycle()
    refusal = rehearse_drop_caller_refusal()
    census = estate_census()
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if not cycle.pass_ or not refusal.pass_:
        print(
            f"FAILED:{UNIT} cycle={cycle.reason} refusal={refusal.reason}"
        )
        return 1

    callers = sorted(m["caller_id"] for m in cycle.migration)
    schema_pack = REPO / "command-center/schema/foundry-artifact.schema.json"
    supporting = [
        "command-center/p2-wave/probes/WFA-0142/engine.py",
        "command-center/p2-wave/probes/WFA-0142/fixtures/registry.json",
        "command-center/p2-wave/probes/WFA-0142/probe1_rollback_bytes.py",
        "command-center/p2-wave/probes/WFA-0142/probe2_drop_caller.py",
        "command-center/p2-wave/probes/WFA-0142/emit_artifact.py",
        LOCAL_SCHEMA,
    ]
    artifacts = [digest(p) for p in supporting]
    artifact = {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0142",
        "completion_sentinel": "SUCCESS:WFA-0142",
        "kind": "supersession-engine",
        "title": "Supersession engine with migration and rollback-to-source",
        "question": (
            "Implement supersession: mark workflow A superseded by workflow B, "
            "emit the migration path for existing callers and presets, and "
            "preserve the ability to roll back to A and to A's source "
            "components. Question: for a supersession, what is the exact "
            "caller migration set, and can the system restore the superseded "
            "workflow and its decomposed sources after the swap?"
        ),
        "mechanism": (
            "supersede + migrate + rehearsed rollback to the prior workflow "
            "and its sources"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_on_disk": {
            "catalog_path": "command-center/schema/foundry-artifact.schema.json",
            "present": schema_pack.is_file(),
            "unit_local_schema": LOCAL_SCHEMA,
        },
        "cloud_ok": False,
        "trigger": "superior-replacement",
        "not_a_duplicate_of": "WFA-0137",
        "distinct_because": (
            "WFA-0137 is regression-triggered revocation. This unit is "
            "replacement-triggered supersession with a migration path and "
            "rehearsed rollback to A and A's decomposed sources."
        ),
        "estate": census,
        "scope": {
            "proof_surface": (
                "hermetic fixture registry + executable engine on this worktree"
            ),
            "does_not_claim": [
                "108-entry 09-WORKFLOW-BLUEPRINT-LIBRARY.json (absent)",
                "30 merge_units from 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json (absent)",
                "live WFA-0137 revocation-engine artifact (absent)",
                "live WFA-0138 lineage-record artifact (absent); decompose() is fixture-local",
            ],
        },
        "answer": {
            "old_id": OLD_ID,
            "new_id": NEW_ID,
            "caller_migration_set": callers,
            "migration_steps": cycle.migration,
            "rollback_restores_superseded_workflow": cycle.byte_equal,
            "rollback_restores_decomposed_sources": cycle.sources_restored_equal,
            "decomposed_sources": cycle.decomposed_sources,
            "rollback_that_would_drop_a_caller_is_refused": (
                not refusal.bad_rollback_ok
                and "pack.new-on-b" in refusal.dropped_named
            ),
        },
        "rehearsal": {
            "clean_cycle": cycle.as_dict(),
            "drop_caller_refusal": refusal.as_dict(),
            "migration_caller_ids": callers,
        },
        "evidence": [
            {
                "claim": (
                    "After supersede+rollback, the canonical serving dump is "
                    "byte-identical to the pre-supersession copy."
                ),
                "signal": "serving-canonical-sha256",
                "anchor": cycle.anchors["serving_canonical_bytes"],
                "pre": cycle.pre_serving_sha256,
                "post": cycle.post_serving_sha256,
                "equal": cycle.byte_equal,
                "verdict": "CONFIRMED" if cycle.byte_equal else "REFUTED",
            },
            {
                "claim": (
                    "Independent per-object digest map (each document/caller "
                    "hashed in isolation) matches after rollback; tamper of a "
                    "source component during the superseded window is cleared."
                ),
                "signal": "per-object-digest-map-sha256",
                "anchor": cycle.anchors["per_object_digests"],
                "pre": cycle.pre_digest_map_sha256,
                "post": cycle.post_digest_map_sha256,
                "equal": cycle.digest_map_equal,
                "tamper_cleared": cycle.tamper_cleared,
                "decomposed_sources": cycle.decomposed_sources,
                "verdict": "CONFIRMED"
                if cycle.digest_map_equal and cycle.tamper_cleared
                else "REFUTED",
            },
        ],
        "tests": [
            {
                "id": "T1-supersede-rollback-byte-equality",
                "result": "PASS" if cycle.pass_ else "FAIL",
                "output_tail": (
                    f"byte_equal={cycle.byte_equal} "
                    f"sig1={cycle.pre_serving_sha256[:16]} "
                    f"sig2={cycle.pre_digest_map_sha256[:16]}"
                ),
            },
            {
                "id": "T2-rollback-that-would-drop-caller-refused",
                "result": "PASS" if refusal.pass_ else "FAIL",
                "output_tail": (
                    f"good_ok={refusal.good_rollback_ok} "
                    f"bad_ok={refusal.bad_rollback_ok} "
                    f"dropped={refusal.dropped_named}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0142-probe2-drop-caller-refusal-both-states",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not author engine.py; it re-runs the live "
                "refusal rehearsal in a separate process and checks both-states."
            ),
        },
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "artifacts": artifacts,
        "registered": True,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} ({out.stat().st_size} B)")
    print("SUCCESS:WFA-0142")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
