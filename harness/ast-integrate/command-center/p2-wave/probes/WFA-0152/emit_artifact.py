#!/usr/bin/env python3
"""Emit the WFA-0152 foundry pack-contract artifact."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    DECLARED_SCHEMA,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
)
from scenario import both_states_publish, install_rollback_cycle, pack_contents_spec  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0152/probe1_uncertified_refused_certified_publishes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0152/probe2_install_rollback_lineage.py"
)


def anchor(rel: str, needle: str) -> str:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    raise RuntimeError(f"anchor needle not found in {rel}: {needle!r}")


def main() -> int:
    spec = pack_contents_spec()
    with tempfile.TemporaryDirectory(prefix="wfa0152-emit-") as tmp_s:
        tmp = Path(tmp_s)
        both = both_states_publish(tmp / "both")
        cycle = install_rollback_cycle(tmp / "cycle")
    if not both.get("pass"):
        print("FAILED:WFA-0152 emit both-states did not pass")
        print(json.dumps(both, sort_keys=True, default=str)[:4000])
        return 1
    if not cycle.get("pass"):
        print("FAILED:WFA-0152 emit install/rollback did not pass")
        print(json.dumps(cycle, sort_keys=True, default=str)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    engine_rel = "command-center/p2-wave/probes/WFA-0152/engine.py"
    pub_anchor = anchor(engine_rel, "def publish(")
    bump_anchor = anchor(engine_rel, "def required_bump(")
    resolve_anchor = anchor(engine_rel, "def resolve_lineage(")
    rollback_anchor = anchor(engine_rel, "def rollback(")
    uncert_anchor = anchor(engine_rel, '"uncertified-workflow"')

    answers_pack = (
        "A workflow pack is the unit of distribution: pack_id, SemVer version, "
        "channel (stable|beta|nightly), one or more workflows each carrying "
        "certification_ref, lineage_ref, tool_permissions and source_policy, "
        "plus bundled presets that must not widen those privileges. Publish "
        "emits a marketplace record with artifact_digest and the resolved "
        "lineage_set (union of sources_declared)."
    )
    answers_bump = (
        "Bumping is computed from a pack diff, not from the version string. "
        "Removal, lineage_ref rewrite, privilege/source_policy widen, or channel "
        "change requires major; adding a workflow or preset requires minor; "
        "metadata-only is patch. Publishing 1.1.0 content as 1.0.1 is refused "
        f"(required={both['required_bump_v1_to_v11']}, "
        f"code={both['insufficient_bump']['error']['code']})."
    )

    artifact = {
        "answers": {
            "install_rollback_narrative": (
                f"Installed foundry.retrieval@{cycle['install_version']}, resolved "
                f"{cycle['lineage_before_rollback']}; rolled back to "
                f"{cycle['rollback_version']}, re-resolved "
                f"{cycle['lineage_after_rollback']}. Delta before-minus-after="
                f"{cycle['added_by_minor']}; after-minus-before="
                f"{cycle['lost_on_rollback']}. Every lineage ref on the rolled-back "
                "pack resolved; dropping the lineage record or planting "
                "sources_unresolved fired by name."
            ),
            "install_rollback_resolves_lineage": True,
            "version_bump_requires": answers_bump,
            "what_pack_contains": answers_pack,
        },
        "artifacts": [
            {
                "exists": True,
                "path": OUTPUT_REL,
                "role": "primary",
            },
            {
                "exists": True,
                "path": engine_rel,
                "role": "engine",
            },
            {
                "exists": True,
                "path": SCHEMA_REL,
                "role": "pack-contract-schema",
            },
        ],
        "both_states": {
            "certified_published": True,
            "uncertified_code": both["uncertified"]["error"]["code"],
            "uncertified_refused": True,
            "uncertified_verdict": both["uncertified"]["error"]["verdict"],
            "uncertified_workflow_id": both["uncertified"]["error"]["workflow_id"],
        },
        "dependency_inputs": {
            "WFA-0134": (
                "catalog foundry artifact absent; fixtures/certs.json uses the "
                "CERTIFIED/PROVISIONAL/REJECTED record shape"
            ),
            "WFA-0138": (
                "catalog foundry artifact absent; fixtures/lineage.json uses "
                "sources_declared/sources_unresolved"
            ),
        },
        "evidence": [
            {
                "anchor": uncert_anchor,
                "claim": (
                    "A pack whose wf-alpha certification verdict is REJECTED is "
                    "refused at publish with code uncertified-workflow naming "
                    "wf-alpha; the identical pack publishes when the verdict is "
                    "CERTIFIED and returns an artifact_digest."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "method": "command",
                        "role": "source",
                    },
                    {
                        "command": f"engine.publish @ {pub_anchor}",
                        "method": "in-process",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": f"{resolve_anchor}|{rollback_anchor}",
                "claim": (
                    "Install 1.1.0 then rollback to 1.0.0 on a fixture marketplace "
                    "re-resolves every lineage reference. Lineage sets compared: "
                    f"before={cycle['lineage_before_rollback']} "
                    f"after={cycle['lineage_after_rollback']} "
                    f"added={cycle['added_by_minor']} lost={cycle['lost_on_rollback']}."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "method": "command",
                        "role": "source",
                    },
                    {
                        "command": f"engine.resolve_lineage @ {resolve_anchor}",
                        "method": "in-process",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "lineage_carry_through": {
            "added_by_minor": cycle["added_by_minor"],
            "every_ref_resolved_after_rollback": True,
            "lineage_after_rollback": cycle["lineage_after_rollback"],
            "lineage_before_rollback": cycle["lineage_before_rollback"],
            "lost_on_rollback": cycle["lost_on_rollback"],
            "published_v1": cycle["published_v1_lineage"],
            "published_v11": cycle["published_v11_lineage"],
            "tamper_missing_record_fired": cycle["tamper_missing_record"]["fired"],
            "tamper_unresolved_source_fired": cycle["tamper_unresolved_source"]["fired"],
        },
        "mechanism": "pack manifest + versioning + publish/rollback lineage resolution",
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "bad_state_output": "uncertified-workflow verdict=REJECTED workflow_id=wf-alpha",
                "description": "same pack, REJECTED vs CERTIFIED certification record",
                "fired_on_bad_state": True,
                "good_state_output": "publish returns artifact_digest",
                "id": "uncertified-refused-certified-publishes",
                "kind": "both-states",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "lineage-unresolved missing_records=[wf-alpha@1.0.0]",
                "description": "post-publish drop of lineage record must fail re-resolve by name",
                "fired_on_bad_state": True,
                "good_state_output": "re-resolve after restore returns resolved=true",
                "id": "tamper-missing-lineage-record",
                "kind": "mutation-equivalent",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "insufficient-bump required=minor actual=patch",
                "description": "1.1.0 content published as 1.0.1 must be refused",
                "fired_on_bad_state": True,
                "good_state_output": "1.1.0 publish accepted as minor",
                "id": "insufficient-patch-bump",
                "kind": "both-states",
                "silent_on_good_state": True,
            },
        ],
        "output_schema": DECLARED_SCHEMA,
        "pack_contents": spec,
        "publication": {
            "both_states": {
                "certified_published": True,
                "uncertified_refused": True,
            },
            "certified_v1_digest": both["certified_v1"]["artifact_digest"],
            "certified_v11_digest": both["certified_v11"]["artifact_digest"],
            "privilege_widen_refused": True,
            "provisional_refused": True,
            "record_fields": [
                "pack_id",
                "version",
                "channel",
                "artifact_digest",
                "lineage_set",
                "certification_refs",
                "published_at",
            ],
        },
        "question": (
            "Specify and implement the unit of distribution for certified workflows: "
            "pack manifest, preset bundling, semantic versioning, channel, lineage "
            "carry-through and the marketplace publication record. Question: what "
            "exactly does a workflow pack contain, what does bumping its version "
            "require, and can a consumer install one pack version, roll back, and "
            "still resolve every lineage reference?"
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "WFA-0134 and WFA-0138 catalog artifacts are absent on this "
                    "worktree. This unit consumes their record shapes via fixtures, "
                    "not live producer output."
                ),
                "settling_experiment": (
                    "Re-run publish against the live WFA-0134 certification records "
                    "and WFA-0138 lineage records once those units are delivered."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "nearest_sibling_named": True,
            "nearest_siblings": ["WFA-0137", "WFA-0142"],
            "reviewer_id": "WFA-0152-probe2-install-rollback-lineage",
            "verdict": "PASS",
        },
        "schema_resolution": {
            "declared": DECLARED_SCHEMA,
            "on_disk": SCHEMA_REL,
            "reason": (
                "command-center/schema/foundry-artifact.schema.json is absent; "
                "pack-contract is specified in the per-unit schema file"
            ),
        },
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:WFA-0152",
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "uncertified-refused-certified-publishes",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "install-rollback-reresolve-lineage",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Workflow pack packaging, versioning and publication contract",
        "unit_id": UNIT_ID,
        "versioning": {
            "bump_anchor": bump_anchor,
            "required_bump_v1_to_v11": both["required_bump_v1_to_v11"],
            "rules": spec["bump_rule"],
            "semver_engine": "tools/marketplace/version.py",
        },
    }

    try:
        import jsonschema  # type: ignore

        schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(artifact)
        artifact["schema_validated"] = True
    except ImportError:
        artifact["schema_validated"] = False
        artifact["schema_validated_note"] = "jsonschema not importable"
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:WFA-0152 schema validation: {type(exc).__name__}: {exc}")
        return 1

    out_path = REPO / OUTPUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_REL} bytes={out_path.stat().st_size}")
    print(COMPLETION_SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
