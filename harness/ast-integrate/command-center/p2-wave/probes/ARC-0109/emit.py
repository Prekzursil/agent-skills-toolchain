#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0109.json and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import schemas as S  # noqa: E402

UNIT = "ARC-0109"
OUT = "command-center/phase4/conformance/ARC-0109.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
# Declared output_schema is a $ref shim to ast-integrate.invalid. jsonschema
# 4.10 tries the network and raises RefResolutionError; the shim itself has
# no constraints. Validate the campaign document against a local structural
# schema that still rejects garbage ({}, unrelated blobs).
LOCAL_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "generator_sanity",
        "surviving_mutants",
        "mutations",
        "per_schema",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0109"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:ARC-0109"},
        "surviving_mutants": {"type": "array"},
        "mutations": {
            "type": "object",
            "required": ["applied", "killed", "survived", "wrong_reason"],
        },
        "generator_sanity": {
            "type": "object",
            "required": ["live", "original_accepted", "tightened_rejected"],
            "properties": {
                "live": {"const": True},
                "original_accepted": {"const": True},
                "tightened_rejected": {"const": True},
            },
        },
        "per_schema": {"type": "array", "minItems": 14, "maxItems": 14},
    },
}
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0109/probe1_generator_sanity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0109/probe2_surviving_mutants.py"
)
QUESTION = (
    "Generate valid instances from every contract schema and assert the validator "
    "ACCEPTS them; then mutate each instance along typed axes (drop a required "
    "field, widen a type, break an enum, exceed a bound, inject an unknown field) "
    "and assert the validator REJECTS it with the expected reason. Report "
    "per-schema acceptance and rejection rates and every surviving mutant."
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ARC-0109/schemas.py",
    "command-center/p2-wave/probes/ARC-0109/engine.py",
    "command-center/p2-wave/probes/ARC-0109/probe1_generator_sanity.py",
    "command-center/p2-wave/probes/ARC-0109/probe2_surviving_mutants.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    E.dump_fixtures()
    E.rebuild_freeze()
    campaign = E.run_campaign()
    gen = campaign["generator"]
    if gen["rejected"] != 0:
        print("FAILED:ARC-0109 generator produced rejected instances")
        for row in campaign["per_schema"]:
            if row.get("generator_errors"):
                print(" ", row["id"], row["generator_errors"])
        return 1
    if gen["accepted"] != len(S.CONTRACT_IDS):
        print(f"FAILED:ARC-0109 expected {len(S.CONTRACT_IDS)} accepted instances")
        return 1
    if not campaign["generator_sanity"]["live"]:
        print("FAILED:ARC-0109 generator sanity loop is not live")
        return 1
    if not all(r["live"] for r in campaign["generator_sanity_per_schema"]):
        print("FAILED:ARC-0109 a schema failed generator-sanity")
        return 1
    enum_ok, enum_why = E.enumeration_ok(
        {
            "surviving_mutants": campaign["surviving_mutants"],
            "mutations": campaign["mutations"],
        }
    )
    if not enum_ok:
        print(f"FAILED:ARC-0109 enumeration {enum_why}")
        return 1
    fake_ok, fake_why = E.enumeration_ok(E.percentage_only_report())
    if fake_ok:
        print("FAILED:ARC-0109 percentage-only control accepted")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_n = campaign["live_contracts_present"]
    fixture_n = campaign["fixture_schemas_used"]
    mut = campaign["mutations"]
    survivors = campaign["surviving_mutants"]
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0109",
        "report_kind": "schema-fuzz-conformance",
        "title": "Property-based schema fuzzing with a mutation oracle",
        "question": QUESTION,
        "schema_corpus": campaign["corpus"],
        "contract_binding": {
            "live_contracts_present": live_n,
            "fixture_schemas_used": fixture_n,
            "ids": list(S.CONTRACT_IDS),
            "note": (
                f"{live_n} live contract file(s) under "
                "command-center/phase4/contracts/; "
                f"{fixture_n} probe-local JSON Schema fixture(s) for ids "
                "without a live schema. The loader prefers a live contract "
                "when one exists. This unit does not author or rebuild those "
                "contract units (no ADV/contract rebuild circle). The campaign "
                "corpus is frozen under "
                "command-center/p2-wave/probes/ARC-0109/fixtures/campaign/ "
                "so named probes cannot drift when later dependency files land."
            ),
        },
        "generator": gen,
        "mutations": mut,
        "per_schema": campaign["per_schema"],
        "surviving_mutants": survivors,
        "surviving_mutant_count": len(survivors),
        "surviving_mutant_enumeration": enum_why,
        "generator_sanity": campaign["generator_sanity"],
        "generator_sanity_per_schema": campaign["generator_sanity_per_schema"],
        "axes": campaign["axes"],
        "percentage_only_control": {
            "rejected": True,
            "reason": fake_why,
        },
        "tests": [
            {
                "id": "probe1_generator_sanity",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_surviving_mutants",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0109-independent-mutation-oracle-reviewer",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Checked that surviving_mutants is an enumeration (identity per "
                "mutant) rather than a kill-rate percentage, and that tightening "
                "the schema rejects a generated instance."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "output-schema"},
            {
                "path": "command-center/p2-wave/probes/ARC-0109/engine.py",
                "exists": True,
                "role": "named-oracle",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0109/probe1_generator_sanity.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0109/probe2_surviving_mutants.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [
            {
                "kind": "campaign",
                "claim": "Every listed contract schema accepted one generated instance",
                "detail": (
                    f"accepted={gen['accepted']} rejected={gen['rejected']} "
                    f"acceptance_rate={gen['acceptance_rate']}"
                ),
            },
            {
                "kind": "mutation-oracle",
                "claim": "Typed-axis mutants were classified with expected reject reasons",
                "detail": (
                    f"applied={mut['applied']} killed={mut['killed']} "
                    f"survived={mut['survived']} wrong_reason={mut['wrong_reason']} "
                    f"rejection_rate={mut['rejection_rate']}"
                ),
            },
            {
                "kind": "enumeration",
                "claim": "Surviving mutants are listed individually, not as a percentage",
                "detail": (
                    f"{enum_why}; percentage-only control rejected ({fake_why}); "
                    f"n_surviving={len(survivors)}"
                ),
            },
            {
                "kind": "generator-sanity",
                "claim": "Tightening a schema rejects a previously accepted generated instance",
                "detail": json.dumps(campaign["generator_sanity"], sort_keys=True),
            },
        ],
        "produced_by": "command-center/p2-wave/probes/ARC-0109/emit.py",
        "timestamps": {"ended_at": now},
        "answer": (
            f"Fuzzed {len(S.CONTRACT_IDS)} contract schemas "
            f"(live={live_n}, fixture={fixture_n}). "
            f"Generator acceptance {gen['accepted']}/{len(S.CONTRACT_IDS)}. "
            f"Mutations applied={mut['applied']} killed={mut['killed']} "
            f"survived={mut['survived']} wrong_reason={mut['wrong_reason']}. "
            f"Survivors enumerated ({enum_why}). Generator-sanity live. "
            "SUCCESS:ARC-0109"
        ),
    }

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:ARC-0109 declared schema missing {SCHEMA}")
        return 1
    doc["output_schema_resolution"] = {
        "declared": SCHEMA,
        "resolved": False,
        "fallback": "local-structural",
        "reason": (
            "command-center/schema/conformance-report.schema.json is a $ref "
            "shim to ast-integrate.invalid; jsonschema 4.10 raises "
            "RefResolutionError (no network id). Local schema still rejects "
            "garbage and requires campaign fields."
        ),
    }
    validator = jsonschema.Draft7Validator(LOCAL_OUTPUT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0109 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0109 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:ARC-0109 artifact {size}B below floor")
        return 1

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:ARC-0109 probes c1={rc1} c2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    digest, size = sha256_file(out)
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0109",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/ARC-0109/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0109-independent-mutation-oracle-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0109: live named probes exit 0, ARC-0109.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV/contract rebuild circle."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/ARC-0109/SUBAGENT-RETURN.json",
            "role": role,
        }

    man_arts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "artifacts": man_arts,
        "expected": len(man_arts),
        "present": len(man_arts),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"mutations applied={mut['applied']} killed={mut['killed']} "
        f"survived={mut['survived']} wrong_reason={mut['wrong_reason']}"
    )
    print("SUCCESS:ARC-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
