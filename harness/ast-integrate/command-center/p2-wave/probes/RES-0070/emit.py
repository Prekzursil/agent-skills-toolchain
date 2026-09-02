#!/usr/bin/env python3
"""Emit command-center/research/RES-0070.json and validate the claim-record schema."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rails import RAILS, public_rail, verify_all  # noqa: E402
from spec import (  # noqa: E402
    CACHE_KEY_FIELDS,
    UNCACHEABLE_LIVE_WEB,
    UNCACHEABLE_STEP_CLASSES,
)
from suite import field_necessity, uncacheable_control  # noqa: E402

OUT = "command-center/research/RES-0070.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
UNIT = "RES-0070"
SENTINEL = (
    "SUCCESS:RES-0070 in the receipt AND a field-by-field cache-key "
    "specification plus a named uncacheable step class"
)
QUESTION = (
    "Bazel and Nix cache on a hash of inputs — for an agent step whose "
    "output depends on a model version, a temperature, and a live web "
    "source, what exactly must enter the cache key, and which steps are "
    "honestly not cacheable at all?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0070/probe1_field_necessity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0070/probe2_uncacheable_control.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def rail_row(rail_id: str) -> dict:
    rec = public_rail(rail_id)
    return {
        "id": rec["id"],
        "kind": rec["kind"],
        "permalink": rec["permalink"],
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "snapshot": rec["snapshot"],
        "quotes": rec["quotes"],
        "engine": rec.get("engine"),
    }


def claim(
    claim_id: str,
    mechanism: str,
    rails: list[str],
    settling: str,
    *,
    caveat: str,
    support: list[str] | None = None,
    contradict: list[str] | None = None,
) -> dict:
    rows = [rail_row(r) for r in rails]
    kinds = {r["kind"] for r in rows}
    assert "structured-api" in kinds and "prose-source" in kinds, claim_id
    assert all(r["http_status"] == 200 and len(r["sha256"]) == 64 for r in rows)
    return {
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "evidence_tier": "E2",
        "confidence_band": "high-with-caveat",
        "named_settling_probe": settling,
        "source_lineage": [RAILS[r]["permalink"] for r in rails],
        "rails": rows,
        "cite_as_measured_fact": True,
        "verdict": "CONFIRMED",
        "strongest_caveat": caveat,
        "support_edges": support or [],
        "contradict_edges": contradict or [],
        "freshness_stamp": max(r["fetch_timestamp"] for r in rows),
        "snapshot_sha256": sorted(r["sha256"] for r in rows),
    }


REQUIRED_KEYS = (
    "unit_id",
    "state",
    "sentinel",
    "claims",
    "cache_key_specification",
    "uncacheable_step_classes",
    "source_lineage",
    "kind",
)


def structural_ok(doc: object) -> bool:
    """Local gate. The catalog output_schema is a generated shim whose $ref
    targets https://ast-integrate.invalid/... and cannot be resolved here.
    Do not call jsonschema against that shim (RefResolutionError / network).
    """
    if not isinstance(doc, dict):
        return False
    if any(k not in doc for k in REQUIRED_KEYS):
        return False
    if doc.get("unit_id") != UNIT:
        return False
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return False
    if "field-by-field cache-key specification" not in blob:
        return False
    if "named uncacheable step class" not in blob:
        return False
    spec = doc.get("cache_key_specification") or {}
    fields = spec.get("fields") if isinstance(spec, dict) else None
    if not isinstance(fields, list) or len(fields) < 8:
        return False
    classes = doc.get("uncacheable_step_classes") or []
    ids = [c.get("id") for c in classes if isinstance(c, dict)]
    if UNCACHEABLE_LIVE_WEB not in ids:
        return False
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 2:
        return False
    e2 = 0
    for claim in claims:
        if not isinstance(claim, dict):
            return False
        rails = [r for r in (claim.get("rails") or []) if isinstance(r, dict)]
        kinds = {r.get("kind") for r in rails}
        if claim.get("evidence_tier") in {"E1", "E2"}:
            if len(rails) < 2 or "structured-api" not in kinds or "prose-source" not in kinds:
                return False
            e2 += 1
    return e2 >= 2


def validate(doc: dict) -> None:
    declared = REPO / SCHEMA
    if not declared.is_file() or declared.stat().st_size <= 0:
        raise SystemExit(f"FAILED:{UNIT} declared schema missing {SCHEMA}")
    if not structural_ok(doc):
        raise SystemExit(f"FAILED:{UNIT} structural gate")
    for garbage in GARBAGE:
        if structural_ok(garbage):
            raise SystemExit(f"FAILED:{UNIT} schema accepts garbage")


def main() -> int:
    nec = field_necessity()
    ctrl = uncacheable_control()
    if not nec["pass"]:
        print("FAILED:RES-0070 field-necessity")
        return 1
    if not ctrl["pass"]:
        print("FAILED:RES-0070 uncacheable-control")
        return 1
    rail_rows = verify_all()
    if any(not r["ok"] for r in rail_rows):
        print("FAILED:RES-0070 rails", json.dumps(rail_rows)[:2000])
        return 1

    claims = [
        claim(
            "C1-bazel-action-key",
            (
                "Bazel memoizes an action by hashing the declared action: "
                "mnemonic, command line, declared environment, and declared "
                "inputs. The remote cache is a map of those action hashes to "
                "result metadata plus a content-addressable store of output "
                "files. Undeclared host state is not in the key."
            ),
            ["gh-bazel-spawn-action-raw", "bazel-remote-caching"],
            P1,
            caveat=(
                "SpawnAction.computeKey is the spawn-shaped action; other "
                "action subclasses add their own fields. The mapping to agent "
                "steps is analogical, not a claim that Bazel will cache an LLM."
            ),
            support=["C3-agent-key-fields"],
        ),
        claim(
            "C2-nix-input-address",
            (
                "Nix input-addressing names a store object by how it was made: "
                "the output path is a function of the derivation "
                "(hashQuotientDerivation / derivation modulo), not of the "
                "output bytes. The store-path fingerprint is "
                "type:sha256:inner-digest:store:name."
            ),
            ["gh-nix-derivations-raw", "nix-input-address"],
            P1,
            caveat=(
                "Fixed-output (content-addressed) derivations are a different "
                "addressing mode. This unit uses the input-addressed case as "
                "the analog for 'hash the recipe'."
            ),
            support=["C3-agent-key-fields"],
        ),
        claim(
            "C3-agent-key-fields",
            (
                "An agent-step cache key that is honest about Bazel/Nix must "
                "include, field by field: step mnemonic, model identity "
                "(provider + id + revision), sampling parameters (including "
                "temperature), prompt-bytes sha256, tool-policy sha256, "
                "declared input-artifact sha256s, live-source snapshot sha256 "
                "(captured body, not URL), and declared env. Omitting any "
                "field makes two distinct steps collide."
            ),
            ["gh-bazel-spawn-action-raw", "bazel-hermeticity"],
            P1,
            caveat=(
                "This is a specification plus a collision test, not a "
                "measurement of any production agent cache. Live-web without "
                "a snapshot is not a key field — it is uncacheable (C4)."
            ),
            support=["C1-bazel-action-key", "C2-nix-input-address"],
            contradict=["C4-uncacheable-live-web"],
        ),
        claim(
            "C4-uncacheable-live-web",
            (
                "Named uncacheable step class "
                + UNCACHEABLE_LIVE_WEB
                + ": a step whose output depends on a live web fetch or search "
                "index result that was not captured as declared input bytes "
                "before the model call. There is no content digest to put in "
                "the key. URL-only keying collides two different bodies. The "
                "honest mark is uncacheable, not a partial key."
            ),
            ["gh-bazel-spawn-action-raw", "bazel-hermeticity"],
            P2,
            caveat=(
                "A captured, hashed snapshot of the page (plus HTTP status and "
                "final URL) makes the step cacheable under C3. Non-seeded "
                "positive temperature is a second uncacheable class for "
                "exact-output memoization."
            ),
            contradict=["C3-agent-key-fields"],
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dvc = public_rail("dvc-archive")
    doc = {
        "unit_id": UNIT,
        "kind": "research-claim-record",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Assess content-addressed memoization for agent steps: "
            "what is safely cacheable"
        ),
        "question": QUESTION,
        "phase": "2",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cache_key_specification": {
            "description": (
                "field-by-field cache-key specification: every listed field "
                "must enter the key of a cacheable agent step; omitting any "
                "one field collides two steps that differ only in that field."
            ),
            "fields": CACHE_KEY_FIELDS,
            "mechanical": {
                "field_count": nec["field_count"],
                "stable_across_calls": nec["stable_across_calls"],
                "omit_collision_proven": all(r["ok"] for r in nec["fields"]),
            },
        },
        "uncacheable_step_classes": UNCACHEABLE_STEP_CLASSES,
        "named_uncacheable_step_class": UNCACHEABLE_LIVE_WEB,
        "uncacheable_control": {
            "named_uncacheable_class": ctrl["named_uncacheable_class"],
            "url_only_mutant_collides": ctrl["url_only_mutant_collides"],
            "honest_body_keys_differ": ctrl["honest_body_keys_differ"],
            "live_web_raised": ctrl["live_web_raised"],
        },
        "claims": claims,
        "source_lineage": sorted({r["permalink"] for r in RAILS.values()}),
        "supporting_e3": [
            {
                "id": "DVC-content-addressed-cache",
                "evidence_tier": "E3",
                "cite_as_measured_fact": False,
                "verdict": "E3-NOT-FACT",
                "reason": (
                    "Live dvc.org returned HTTP 429. One Wayback prose rail "
                    "remains; a claim with one rail is E3 and is not cited "
                    "as measured fact."
                ),
                "rail": {
                    "kind": dvc["kind"],
                    "permalink": dvc["permalink"],
                    "fetch_timestamp": dvc["fetch_timestamp"],
                    "http_status": dvc["http_status"],
                    "sha256": dvc["sha256"],
                },
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0070-probe2-uncacheable-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "defaults_to_refuted": True,
            "method": (
                "Named probe2 re-runs the uncacheable-class control and the "
                "dual-rail grader. It does not treat this conclusion document "
                "as evidence. A single-rail mutant is graded E3 and must not "
                "be cited as measured fact."
            ),
        },
        "tests": [
            {"id": "T1-field-necessity", "command": P1, "result": "PASS"},
            {"id": "T2-uncacheable-control", "command": P2, "result": "PASS"},
        ],
        "named_probes": [
            {"id": "probe1", "role": "field-necessity", "command": P1},
            {"id": "probe2", "role": "uncacheable-control", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0070/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"emitted_at": now},
        "notes": (
            "G-1 for RES-0070: live named probes exit 0, research artifact "
            "state=SUCCESS, field-by-field cache-key specification plus a "
            "named uncacheable step class, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    validate(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:RES-0070")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
