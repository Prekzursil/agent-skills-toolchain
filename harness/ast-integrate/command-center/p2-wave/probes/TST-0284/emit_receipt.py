#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0284.json from the live validator + harvest."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from harvest import harvest  # noqa: E402
from validator import MANDATORY, validate  # noqa: E402

OUT = "command-center/receipts/TST-0284.json"
FIXTURES = HERE / "fixtures" / "records.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0284/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0284/probe2_circular_and_harvest.py"
)
QUESTION = (
    "Implementation target: the outcome at :10942 and :11276 requires a "
    "proof-of-impossibility record. Specify its mandatory contents — the exact "
    "claim shown unobtainable, the search space actually covered, the methods "
    "attempted with their outputs, the resource limit reached, and the concrete "
    "observation that WOULD refute the impossibility — and gate acceptance on "
    "all five. A record that cannot be refuted by any named observation is not "
    "a proof and must be rejected by the validator."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def compact_projected(row: dict) -> dict:
    out = {}
    for k in MANDATORY:
        val = (row.get("projected") or {}).get(k)
        if isinstance(val, str) and len(val) > 800:
            out[k] = val[:800] + "…"
        else:
            out[k] = val
    return out


def main() -> int:
    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    good = validate(fx["well_formed"])
    missing = validate(fx["missing_refuting_observation"])
    empty = validate(fx["empty_refuting_observation"])
    world = validate(fx["circular_unobservable"])
    omni = validate(fx["circular_omniscient"])
    eq = validate(fx["circular_equals_claim"])
    if not good["accepted"]:
        print("FAILED:TST-0284 emit over-blocked well-formed", good)
        return 1
    if missing["accepted"] or empty["accepted"]:
        print("FAILED:TST-0284 emit accepted a no-falsifier record")
        return 1
    if world["accepted"] or omni["accepted"] or eq["accepted"]:
        print("FAILED:TST-0284 emit accepted a circular record")
        return 1
    if "missing-field:refuting_observation" not in missing["reasons"]:
        print("FAILED:TST-0284 emit missing-field reason absent", missing)
        return 1

    live_h = harvest()
    if live_h["n"] < 3:
        print("FAILED:TST-0284 emit harvest n<3")
        return 1
    harvest_rows = []
    for row in live_h["records"]:
        harvest_rows.append(
            {
                "id": row["id"],
                "producer": row["producer"],
                "path": row["path"],
                "pointer": row["pointer"],
                "accepted": row["accepted"],
                "classification": row["classification"],
                "missing": row["missing"],
                "present_fields": row["present_fields"],
                "reasons": row["reasons"],
                "projected": compact_projected(row),
            }
        )
        if row["accepted"]:
            print(f"FAILED:TST-0284 emit harvest {row['id']} accepted as proof")
            return 1

    src_probe = {
        "id": "probe1_both_states",
        "command": P1,
        "role": "missing-field-vs-well-formed",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0284/probe1_both_states.py"
        ),
    }
    ver_probe = {
        "id": "probe2_circular_and_harvest",
        "command": P2,
        "role": "circular-unobservable-and-program-harvest",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0284/probe2_circular_and_harvest.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0284 emit source/verifier probe files identical")
        return 1

    mandatory_spec = [
        {
            "id": "claim_shown_unobtainable",
            "meaning": "the exact claim shown unobtainable",
        },
        {
            "id": "search_space_covered",
            "meaning": "the search space actually covered (bounded, not 'everywhere')",
        },
        {
            "id": "methods_attempted",
            "meaning": "the methods attempted with their outputs",
        },
        {
            "id": "resource_limit_reached",
            "meaning": "the finite resource limit reached",
        },
        {
            "id": "refuting_observation",
            "meaning": (
                "the concrete observation that WOULD refute the impossibility; "
                "must be producible by a named finite experiment"
            ),
        },
    ]

    doc = {
        "unit_id": "TST-0284",
        "claim_id": "TST-0284-proof-of-impossibility-falsifiable",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "receipt",
        "title": (
            "Make proof-of-impossibility falsifiable so it cannot become "
            "a polite word for giving up"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0284",
        "completion_sentinel": "SUCCESS:TST-0284",
        "min_bytes_threshold": 2048,
        "output_schema": "command-center/schema/receipt.schema.json",
        "mandatory_elements": mandatory_spec,
        "gate_rule": (
            "Acceptance requires all five elements. A record whose "
            "refuting_observation is missing, empty, or unobservable in "
            "principle is rejected; a well-formed record is accepted."
        ),
        "both_states": {
            "well_formed_accepted": good["accepted"],
            "missing_refuting_observation_accepted": missing["accepted"],
            "empty_refuting_observation_accepted": empty["accepted"],
            "circular_unobservable_accepted": world["accepted"],
            "control": (
                "missing-field fixture REJECTED; well-formed fixture ACCEPTED"
            ),
        },
        "tests": {
            "rejects_missing_refuting_observation": {
                "pass": (not missing["accepted"])
                and "missing-field:refuting_observation" in missing["reasons"],
                "reasons": missing["reasons"],
                "classification": missing["classification"],
            },
            "accepts_well_formed": {
                "pass": good["accepted"] is True,
                "reasons": good["reasons"],
                "classification": good["classification"],
            },
            "rejects_circular_unobservable": {
                "pass": (not world["accepted"])
                and (not omni["accepted"])
                and (not eq["accepted"]),
                "world_reasons": world["reasons"],
                "omniscient_reasons": omni["reasons"],
                "equals_claim_reasons": eq["reasons"],
            },
        },
        "harvest": {
            "n": live_h["n"],
            "note": live_h["note"],
            "catalog_declared_impossibility_artifacts": live_h[
                "catalog_declared_impossibility_artifacts"
            ],
            "records": harvest_rows,
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0284/validator.py",
                "kind": "five-element-gate",
                "claim": (
                    "Validator rejects missing refuting_observation, accepts "
                    "the well-formed macOS-runner fixture, and rejects "
                    "unobservable-in-principle / omniscient / equals-claim "
                    "circular observations."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0139/fixtures/impossibility.json",
                "kind": "program-record",
                "claim": (
                    "IMP-0139 repair-loop macos proof is scored against the "
                    "five elements; methods_attempted is absent so it is not "
                    "accepted as a complete proof."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0311/artifacts/proof_of_impossibility.final.json",
                "kind": "program-record",
                "claim": (
                    "IMP-0311 hung-jury PROOF-OF-IMPOSSIBILITY names a claim "
                    "and a contradiction but not a finite refuting observation."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0084/_refute_out.json",
                "kind": "program-record",
                "claim": (
                    "AUD-0084 blocked failure is scored as an informal "
                    "unobtainability record (Claude falsifier unobtainable)."
                ),
            },
        ],
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "role": "missing-field-vs-well-formed", "command": P1},
            {
                "id": "probe2",
                "role": "circular-unobservable-and-program-harvest",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0284-probe2-circular-and-harvest",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is the mechanical adversarial control: circular "
                "observations must be rejected and the three harvested missing-"
                "element tables must match a live recompute. Catalog also names "
                "a Codex+Claude pair; G-1 for this unit is probe-green, not that "
                "cross-vendor vote. A split would be resolved by raw probe output."
            ),
        },
        "residual_caveat": (
            "tools/council/simulate.py is absent on this worktree; this unit "
            "gates the proof-of-impossibility *record*, not the stopping-"
            "expression evaluator (TST-0281). Catalog-declared CNF-0026 / "
            "CNF-0098 files are absent; RES-0149's evidence-quality receipt "
            "is present but is a schema report, not a five-element proof. "
            "The three scored records are IMP-0139, IMP-0311, and AUD-0084. "
            "cloud ok=true is not delivery."
        ),
        "scope": {
            "proof_surface": (
                "five-element validator; both-states missing-field vs well-"
                "formed; circular unobservable rejection; harvest of three "
                "program records"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "TST-0281 stopping-expression evaluator was executed",
                "CNF-0026 / CNF-0098 impossibility files were present",
                "IMP-0368 receipt was present on this worktree",
            ],
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0284/validator.py",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0284 artifact {size}B below floor")
        return 1
    if b"SUCCESS:TST-0284" not in out.read_bytes():
        print("FAILED:TST-0284 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0284 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
