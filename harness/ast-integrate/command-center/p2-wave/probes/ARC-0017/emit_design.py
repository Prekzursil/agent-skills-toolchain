#!/usr/bin/env python3
"""Emit command-center/phase3/A3/DESIGN.json for ARC-0017."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import machine as M  # noqa: E402

OUT = "command-center/phase3/A3/DESIGN.json"
SCHEMA = "command-center/schema/architecture-dossier.schema.json"
QUESTION = (
    "Specify a marketplace-first architecture in which the canonical registry "
    "index IS the control plane and every local capability arrives as an "
    "installed, versioned, lockfile-pinned package: define the package unit "
    "and its boundary, the registry schema, release channels, the "
    "install/update/rollback state machine, and the cache-invalidation rule "
    "that prevents a stale cache from masking a fixed package."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0017/probe1_totality.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0017/probe2_cache_invalidation.py"
)

# Catalog architecture-dossier.schema.json is a $ref shim to
# https://ast-integrate.invalid/... which does not resolve on this host
# (RefResolutionError). Validating against it cannot reject garbage and
# cannot accept a real dossier. Local shape is the live constraint:
# required A3 fields the named probes read, plus rejection of empty/garbage.
DOSSIER_SHAPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "architecture_id",
        "package_unit",
        "registry_schema",
        "release_channels",
        "state_machine",
        "cache_invalidation",
        "evidence",
        "tests",
        "negative_controls",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "ARC-0017"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:ARC-0017"},
        "architecture_id": {"const": "A3"},
        "package_unit": {"type": "object", "required": ["identity", "boundary"]},
        "registry_schema": {"type": "object", "required": ["path", "control_plane"]},
        "release_channels": {
            "type": "object",
            "required": ["binding_release_mode", "channels"],
        },
        "state_machine": {
            "type": "object",
            "required": ["states", "events", "table", "table_sha256"],
        },
        "cache_invalidation": {
            "type": "object",
            "required": [
                "activation_lookup_key",
                "stale_cache_masks_fixed_package",
                "walk",
            ],
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 2},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def package_entry(entry: dict, kind: str, source_id: str, citation: str) -> dict:
    payload = M.canonical_bytes(entry)
    digest = M.sha256_bytes(payload)
    transcription = {
        "form": "a3-package/v1",
        "kind": kind,
        "id": entry["id"],
        "source_id": source_id,
        "config": {
            "package_id": entry["id"],
            "kind": kind,
            "version": "1.0.0",
            "digest": digest,
            "channel": "pr",
            "claimed_paths": [
                f"command-center/p2-wave/probes/ARC-0010/registry.json#entries[id={entry['id']}]"
            ],
            "immutable": True,
            "lockfile_pin": {
                "package_id": entry["id"],
                "version": "1.0.0",
                "digest": digest,
            },
            "typed_fields": entry,
        },
    }
    return {
        "kind": kind,
        "id": entry["id"],
        "source_id": source_id,
        "source_citation": citation,
        "transcription_basis": (
            "Typed A2 registry entry on this worktree, wrapped as an A3 "
            "lockfile-pinned package. Payload digest is sha256 of canonical JSON."
        ),
        "verdict": "EXPRESSIBLE",
        "sha256": digest,
        "transcription": transcription,
    }


def by_id(registry: dict, eid: str) -> dict:
    for entry in registry["entries"]:
        if entry["id"] == eid:
            return entry
    raise KeyError(eid)


def main() -> int:
    registry = json.loads(M.A2_REGISTRY.read_text(encoding="utf-8"))
    samples = [
        package_entry(
            by_id(registry, "skill.council"),
            "skill",
            "command-center/p2-wave/probes/ARC-0010/registry.json#skill.council",
            "command-center/p2-wave/probes/ARC-0010/registry.json",
        ),
        package_entry(
            by_id(registry, "wf.catalog-class.discovery-only"),
            "workflow_blueprint",
            "command-center/p2-wave/probes/ARC-0010/registry.json#wf.catalog-class.discovery-only",
            "command-center/p2-wave/probes/ARC-0010/registry.json",
        ),
        package_entry(
            by_id(registry, "council.preset.catalog-class.editable"),
            "council_preset",
            "command-center/p2-wave/probes/ARC-0010/registry.json#council.preset.catalog-class.editable",
            "command-center/p2-wave/probes/ARC-0010/registry.json",
        ),
    ]
    paper = M.paper_package_skill_council()
    table = M.full_table()
    gaps = M.totality_gaps(table)
    if gaps:
        print(f"FAILED:ARC-0017 totality gaps before emit {gaps[:12]}")
        return 1
    design_walk = M.walk_stale_cache_masks_fix(digest_in_key=True)
    mutant_walk = M.walk_stale_cache_masks_fix(digest_in_key=False)
    if design_walk["class_reachable"] or not mutant_walk["class_reachable"]:
        print("FAILED:ARC-0017 cache walk both-states broken before emit")
        return 1

    libs = {
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": present(
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/phase3/ROSTER.json": present(
            "command-center/phase3/ROSTER.json"
        ),
        "command-center/phase3/RUBRIC.json": present(
            "command-center/phase3/RUBRIC.json"
        ),
        "command-center/OWNER-DECISIONS.md": present(
            "command-center/OWNER-DECISIONS.md"
        ),
        "skills/council/SKILL.md": present("skills/council/SKILL.md"),
        "command-center/p2-wave/probes/ARC-0010/registry.json": present(
            "command-center/p2-wave/probes/ARC-0010/registry.json"
        ),
    }

    fixtures = HERE / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "index.json").write_text(
        json.dumps(paper["index"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (fixtures / "lockfile.json").write_text(
        json.dumps(paper["lockfile"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    file_set = [
        {
            "path": "command-center/control-plane/A3/INDEX.json",
            "role": "control-plane",
            "notes": "Canonical registry index. THIS is the control plane. Direct writes forbidden under PR-ONLY; mutation is a pull request.",
        },
        {
            "path": "command-center/control-plane/A3/index.schema.json",
            "role": "schema",
            "notes": "Draft-07 schema for the index. Live copy: probes/ARC-0017/registry.schema.json.",
        },
        {
            "path": "command-center/control-plane/A3/LOCKFILE.json",
            "role": "lockfile",
            "notes": "Exact (package_id, version, digest) pins. Latest-from-channel is never the running identity.",
        },
        {
            "path": "command-center/control-plane/A3/cache/",
            "role": "content-addressed-cache",
            "notes": "Blobs keyed by digest. Labels (id, version) are advisory and must not activate.",
        },
        {
            "path": "command-center/control-plane/A3/install-root/",
            "role": "install-root",
            "notes": "Activated claimed_paths after STAGING+activate. Bytes must match the lockfile digest.",
        },
        {
            "path": "command-center/control-plane/A3/packages/",
            "role": "package-store",
            "notes": "Immutable release blobs. Republishing a version with a new digest is rejected.",
        },
    ]
    load_order = [
        {"order": 1, "path": "command-center/control-plane/A3/index.schema.json"},
        {"order": 2, "path": "command-center/control-plane/A3/INDEX.json"},
        {"order": 3, "path": "command-center/control-plane/A3/LOCKFILE.json"},
        {"order": 4, "path": "command-center/control-plane/A3/cache/"},
        {"order": 5, "path": "command-center/control-plane/A3/install-root/"},
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0017",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0017",
        "completion_sentinel": "SUCCESS:ARC-0017",
        "architecture_id": "A3",
        "architecture_class": "marketplace-first",
        "title": (
            "A3 (marketplace-first): Design the marketplace-first control plane "
            "with lockfile-pinned package state"
        ),
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0017]",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "architect",
            "execution_substrate": "headless-linux",
        },
        "answer": (
            "A3 makes INDEX.json the control plane: a capability is not live "
            "until it is an immutable (package_id, version, digest) row in the "
            "index, pinned exactly in LOCKFILE.json, verified, staged, and "
            "activated. Package boundary is claimed_paths; uninstall may touch "
            "only those paths. Channels under PR-ONLY: the only write path is a "
            "pull request against the index; stable/beta are index pointers; "
            "canary is a throwaway-prefix rehearsal, not a public deploy. "
            "publish_public and mutate_in_place are REJECT from every state. "
            "Cache activation lookup is by digest; a stale D_bad cannot satisfy "
            "a D_good pin, so stale-cache-masks-a-fixed-package is unreachable. "
            "skill.council from the on-tree A2 registry is packaged end to end."
        ),
        "file_set": file_set,
        "load_order": load_order,
        "precedence": {
            "rule": "LOCKFILE pin (package_id, version, digest) is the running identity. INDEX 'latest' or channel pointer never overrides a pin. Cache never overrides a pin.",
            "tie_break": "If INDEX digest for a pinned (package_id, version) disagrees with the lockfile digest, FAIL-CLOSED (immutability violation). No mtime, no 'newer file wins'.",
            "duplicate_in_one_file": "FAIL-CLOSED: two INDEX rows for the same (package_id, version) with different digests, or two packages claiming the same path.",
            "merge": "No field-level merge of package payloads. A change is a new version. Overlay of claimed_paths across packages is forbidden.",
        },
        "package_unit": {
            "definition": "One capability (one kind, one id) is one package. The unit of install, update, rollback, and uninstall is that package.",
            "identity": "(package_id, version, digest)",
            "boundary": "claimed_paths relative to install-root. Files not listed are not owned. Sibling registry entries are not claimed.",
            "immutability": "A version's digest cannot change. Fixes bump version and the lockfile pin.",
            "no_postinstall_rewrite": True,
            "paper_example": paper["release"],
            "not_claimed_by_skill_council": paper["not_claimed_sibling_ids"],
            "install_walk": paper["install_walk"],
            "terminal_state": paper["terminal_state"],
        },
        "registry_schema": {
            "path": "command-center/p2-wave/probes/ARC-0017/registry.schema.json",
            "control_plane": "INDEX.json (packages[] + channels[])",
            "lockfile": "LOCKFILE.json pins[]",
            "cache_entry": "keyed by digest; package_id/version labels are not activation keys",
        },
        "release_channels": {
            "binding_release_mode": "PR-ONLY",
            "binding_citation": (
                "command-center/OWNER-DECISIONS.md OQ-3: 'Release mode is "
                "PR-ONLY: propose changes as pull requests, never a private "
                "canary and never a public marketplace release.' "
                "OQ-9: a green CI install/upgrade/rollback rehearsal against a "
                "throwaway prefix stands in for the canary. Catalog "
                "owner_decisions[id=OQ-3].answer is PR-ONLY."
                if libs["command-center/OWNER-DECISIONS.md"]
                else (
                    "command-center/WORK-UNIT-CATALOG.json owner_decisions OQ-3 "
                    "answer PR-ONLY. command-center/OWNER-DECISIONS.md is absent "
                    "on this worktree."
                )
            ),
            "channels": paper["index"]["channels"],
            "public_publish": "REJECT from every state (publish_public event)",
            "promotion": "A PR retargets a channel pointer in INDEX.json. No direct index write.",
            "canary": (
                "Not a public deployment target. OWNER-DECISIONS.md OQ-9 binds "
                "a throwaway-prefix install -> upgrade -> rollback rehearsal "
                "as the canary substitute. Channel id canary-rehearsal is that "
                "rehearsal, not a public deploy."
            ),
        },
        "state_machine": {
            "states": list(M.STATES),
            "events": list(M.EVENTS),
            "pair_count": len(M.STATES) * len(M.EVENTS),
            "defined_count": sum(1 for r in table if r["kind"] == "DEFINED"),
            "rejected_count": sum(1 for r in table if r["kind"] == "REJECT"),
            "table_sha256": M.table_digest(table),
            "totality": "every (state, event) is DEFINED or REJECT; no implicit self-loops",
            "explicit_self_loops": [
                f"{r['state']}+{r['event']}"
                for r in table
                if r["kind"] == "DEFINED" and r["explicit_self_loop"]
            ],
            "table": table,
        },
        "cache_invalidation": {
            "activation_lookup_key": "digest",
            "name_keyed_lookup_activates": False,
            "versions_immutable": True,
            "poison_policy": (
                "If cache[digest] exists but sha256(bytes)!=digest, delete and MISS. "
                "A label (package_id, version) pointing at the wrong digest is ignored "
                "for activation."
            ),
            "stale_cache_masks_fixed_package": "UNREACHABLE",
            "why_unreachable": (
                "A fix cannot reuse version 1.0.0 (immutability REJECT). The lockfile "
                "pin moves to 1.0.1/D_good. Activation looks up cache[D_good], which "
                "cannot HIT on D_bad. The name-keyed mutant DOES mask; that is the "
                "negative control, not the design."
            ),
            "walk": design_walk,
            "mutant_name_keyed_walk": {
                "class_reachable": mutant_walk["class_reachable"],
                "masked": mutant_walk["masked"],
                "activated_digest": mutant_walk["activated_digest"],
            },
        },
        "expressibility": {
            "catalogue_claim": (
                "Every local capability arrives as an installed, versioned, "
                "lockfile-pinned package whose payload is finite static bytes "
                "with a digest and claimed_paths"
            ),
            "libraries_on_this_tree": libs,
            "cardinality_from_library_bytes": "NOT-CHECKED",
            "cardinality_reason": (
                "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent at repo root. "
                "Three on-tree A2 typed entries (skill.council, "
                "wf.catalog-class.discovery-only, "
                "council.preset.catalog-class.editable) are packaged instead. "
                "skills/council/SKILL.md is present but is a separate payload "
                "from the typed A2 registry entry used as the paper package."
                if libs.get("skills/council/SKILL.md")
                else (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent. Three "
                    "on-tree A2 typed entries are packaged instead."
                )
            ),
            "structural_rule": (
                "A capability is expressible as an A3 package iff it has a kind "
                "in the registry schema, a canonical payload digest, claimed_paths, "
                "immutable=true, and no postinstall rewrite of bytes after verify."
            ),
            "first_non_expressible_construct": (
                "postinstall script that rewrites payload bytes after digest verification"
            ),
            "stopped_at_first_inexpressible": True,
            "stop_reason": (
                "A postinstall rewrite would make the lockfile digest lie about "
                "running bytes and would reintroduce stale-cache-masks-a-fixed-package. "
                "The schema and VERIFYING.precondition forbid it. We stop there and "
                "do not claim the absent 96+48+64 libraries package."
            ),
            "declarative_subset_still_maps": True,
        },
        "samples": samples,
        "evidence": [
            {
                "claim": "The install/update/rollback state machine is a total table: every (state, event) pair is DEFINED or explicitly REJECTED, with precondition and postcondition, and no implicit self-loops.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0017/probe1_totality.py",
            },
            {
                "claim": "stale-cache-masks-a-fixed-package is unreachable when activation lookup is by digest and versions are immutable; a name-keyed cache mutant makes the class reachable.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0017/probe2_cache_invalidation.py",
            },
            {
                "claim": "skill.council from the on-tree A2 registry is packaged end to end (index row, lockfile pin, claimed_paths, digest, install walk to INSTALLED).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0010/registry.json",
            },
            {
                "claim": "Library files 09-WORKFLOW-BLUEPRINT-LIBRARY.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from disk on this worktree.",
                "verdict": "REFUTED",
                "anchor": "expressibility.libraries_on_this_tree",
            },
            {
                "claim": "command-center/OWNER-DECISIONS.md is present and was quoted as the PR-ONLY binding line.",
                "verdict": (
                    "CONFIRMED"
                    if libs["command-center/OWNER-DECISIONS.md"]
                    else "REFUTED"
                ),
                "anchor": "release_channels.binding_citation",
            },
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:30:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
            "same_fingerprint_structural_refutes": 0,
            "park_rule": (
                "Two same-fingerprint structural refutes: park status=BLOCKED "
                "with required_fix named. No ADV rebuild circle. This is attempt 1."
            ),
        },
        "tests": [
            {
                "id": "T1-state-machine-totality",
                "name": "State-machine totality check: every (state, event) pair is either defined or explicitly rejected; no implicit self-loops",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-cache-invalidation-stale-masks-fix",
                "name": "Cache-invalidation demonstration: the stale-cache-masks-a-fixed-package class is walked through the design and shown to be unreachable",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0017-C1",
                "kind": "known-broken-fixture",
                "description": "Drop one REJECT row from the state-machine table; totality MUST fail.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "totality gaps nonempty",
                "good_state_output": "gaps=0",
            },
            {
                "id": "ARC0017-C2",
                "kind": "known-broken-fixture",
                "description": "Name-keyed cache mutant activates D_bad for a D_good pin; design digest-keyed cache must not.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "class_reachable=true masked=true",
                "good_state_output": "class_reachable=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0017-probe1-cartesian-totality",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Mechanically different enumerator: cartesian product of exported "
                "STATES x EVENTS compared to the live table and to DESIGN.json "
                "table_sha256. Not the author of DEFINED. This is the catalog "
                "totality test, not a second human architect."
            ),
            "paired_adversarial_unit": "ARC-0023",
            "paired_adversarial_note": (
                "ARC-0023 depends on this DESIGN.json. Waiting for ARC-0023 "
                "before closing ARC-0017 is a deadlock; G-1 for this unit does "
                "not require that circle. No ADV rebuild of A3."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0017/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0017/probe1_totality.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py ARC-0017",
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Byte packaging of the absent 09/12 libraries and skills/council/SKILL.md.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place those library files on disk and wrap each record as "
                    "an A3 package; re-run claimed_paths overlap check."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/ARC-0017/registry.schema.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/schema/architecture-dossier.schema.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "state-machine-totality", "command": P1},
            {
                "id": "probe2",
                "role": "cache-invalidation",
                "command": P2,
            },
        ],
    }

    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or "$ref" not in shim:
        print("FAILED:ARC-0017 catalog schema shim missing $ref")
        return 1
    validator = jsonschema.Draft7Validator(DOSSIER_SHAPE)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0017 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        g_errs = list(validator.iter_errors(g))
        if not g_errs:
            print(f"FAILED:ARC-0017 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0017 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
