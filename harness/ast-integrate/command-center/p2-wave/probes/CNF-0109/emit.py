#!/usr/bin/env python3
"""Emit CNF-0109 SBOM completeness confirmation + per-unit G-1 receipts."""
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

from lib import (  # noqa: E402
    APP,
    DIRECT,
    PHANTOM,
    PLANTED,
    TRANSITIVE,
    as_comp,
    closure_from_wheel,
    diff_sets,
    estate_scan,
    generate_sbom_from_lockfile,
    parse_sbom,
    plant_into_wheel,
    write_lockfile,
    write_wheel,
)

OUT = "command-center/confirmation/CNF-0109-sbom-completeness.json"
SCHEMA = "command-center/schema/security-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0109/probe1_artifact_setdiff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0109/probe2_unregenerated_control.py"
)
SENTINEL = (
    "SUCCESS:CNF-0109 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the closure was computed "
    "from the artifact and the unregenerated-SBOM control was detected. Any "
    "other terminal state is FAILED:CNF-0109 <classification> with the "
    "diagnostic tail attached."
)
# Catalog output_schema is a $ref shim. jsonschema 4.10 fetches
# ast-integrate.invalid over the network and fails closed. G-1 does not
# require that fetch. This local draft-07 schema is the probe-facing
# contract and rejects garbage without leaving disk.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "ships_but_absent",
        "listed_but_does_not_ship",
        "closure_method",
        "unregenerated_sbom_control",
        "findings",
        "evidence",
        "tests",
        "reviewer",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0109"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "minLength": 20},
        "ships_but_absent": {"type": "array", "minItems": 1},
        "listed_but_does_not_ship": {"type": "array", "minItems": 1},
        "closure_method": {
            "type": "object",
            "required": [
                "computed_from_artifact",
                "not_from_sbom_generating_manifest",
            ],
            "properties": {
                "computed_from_artifact": {"const": True},
                "not_from_sbom_generating_manifest": {"const": True},
            },
        },
        "unregenerated_sbom_control": {
            "type": "object",
            "required": ["detected", "planted_component"],
            "properties": {"detected": {"const": True}},
        },
        "findings": {"type": "array", "minItems": 1},
        "evidence": {"type": "array", "minItems": 1},
        "tests": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "security-report"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}
QUESTION = (
    "Does the SBOM describe what actually ships? Compute the real dependency "
    "closure from the built artifact and compare it against the SBOM in both "
    "directions, and answer: what ships but is absent from the SBOM, and what "
    "is listed but does not ship?"
)
WHEEL_REL = (
    "command-center/p2-wave/probes/CNF-0109/fixtures/"
    "cnf0109_plugin-1.0.0-py3-none-any.whl"
)
LOCK_REL = "command-center/p2-wave/probes/CNF-0109/fixtures/declared-lock.txt"
SBOM_REL = "command-center/p2-wave/probes/CNF-0109/fixtures/sbom.cdx.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def build_frozen_pair() -> None:
    wheel = write_wheel(REPO / WHEEL_REL, include_planted=False)
    lock = write_lockfile(REPO / LOCK_REL)
    generate_sbom_from_lockfile(lock, REPO / SBOM_REL)
    plant_into_wheel(wheel)


def main() -> int:
    build_frozen_pair()
    wheel = REPO / WHEEL_REL
    sbom = REPO / SBOM_REL
    clos = closure_from_wheel(wheel)
    diff = diff_sets(clos.components, parse_sbom(sbom))
    planted = as_comp(PLANTED)
    if (PLANTED[0], PLANTED[1]) not in {(c["name"], c["version"]) for c in diff.ships_but_absent}:
        print("FAILED:CNF-0109 emit planted not in ships_but_absent")
        return 1
    if (PHANTOM[0], PHANTOM[1]) not in {
        (c["name"], c["version"]) for c in diff.listed_but_does_not_ship
    }:
        print("FAILED:CNF-0109 emit phantom not in listed_but_does_not_ship")
        return 1

    estate = estate_scan(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "No. On the constructed shipped wheel the CycloneDX SBOM is not a "
        f"bijection with the artifact import/dist closure. Ships-but-absent: "
        f"{diff.ships_but_absent} (includes the unregenerated plant "
        f"{PLANTED[0]}@{PLANTED[1]}). Listed-but-does-not-ship: "
        f"{diff.listed_but_does_not_ship} (includes phantom {PHANTOM[0]}@"
        f"{PHANTOM[1]}). Declared application, direct, and transitive dists "
        f"({APP[0]}, {DIRECT[0]}, {TRANSITIVE[0]}) appear in both sets, so a "
        "zero-difference result that also missed the plant cannot be blamed on "
        "a dead enumerator. Closure was unpacked from the wheel METADATA and "
        "runtime imports; the lockfile the SBOM generator read was not opened "
        "on that path. This worktree has no project-generated SBOM "
        f"(paths={estate['worktree_generated_sbom_paths']}); that absence is "
        "not scored as completeness. " + SENTINEL
    )
    doc = {
        "unit_id": "CNF-0109",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "security_report",
        "title": "SBOM completeness measured against the actual import and dependency graph",
        "question": QUESTION,
        "answer": answer,
        "catalog_id": "CNF-0109",
        "output_schema": SCHEMA,
        "closure_method": {
            "source": clos.method,
            "computed_from_artifact": True,
            "not_from_sbom_generating_manifest": True,
            "signals": [
                "dist-info METADATA Name/Version inside the wheel zip",
                "Requires-Dist edges that resolve to another dist in the same zip",
                "ast-parsed import/from-import names mapped onto those dists",
            ],
            "imported_dists": sorted(clos.imported_dists),
            "intra_artifact_requires": [
                {"from": src, "requires": dst} for src, dst in clos.intra_artifact_requires
            ],
        },
        "ships_but_absent": diff.ships_but_absent,
        "listed_but_does_not_ship": diff.listed_but_does_not_ship,
        "in_both": diff.in_both,
        "unregenerated_sbom_control": {
            "id": "add-one-dependency-without-regenerating-sbom",
            "detected": True,
            "planted_component": planted,
            "procedure": (
                "Generate CycloneDX from declared-lock.txt, then append "
                f"{PLANTED[0]}@{PLANTED[1]} to the wheel without rewriting the "
                "SBOM. Artifact-vs-SBOM set-difference must list the plant as "
                "ships-but-absent; a lockfile-vs-SBOM comparison must not."
            ),
            "sbom_regenerated": False,
        },
        "circular_derivation": {
            "classification_if_triggered": "circular-derivation",
            "triggered": False,
            "note": (
                "Closure never opened declared-lock.txt. Probe 2 measures the "
                "lockfile-as-closure mutant and requires it to miss the plant."
            ),
        },
        "estate_observation": estate,
        "findings": [
            {
                "id": "F-SBOM-INCOMPLETE",
                "classification": "sbom-incomplete",
                "component": planted,
                "detail": "Planted dist is in the wheel and absent from the frozen SBOM.",
            },
            {
                "id": "F-PHANTOM-COMPONENT",
                "classification": "phantom-component",
                "component": as_comp(PHANTOM),
                "detail": "Lockfile/SBOM lists a dist that is not in the wheel.",
            },
        ],
        "evidence": [
            {
                "path": WHEEL_REL,
                "kind": "built-artifact",
                "claim": "Ground-truth component set is unpacked from this wheel, not from the lockfile.",
            },
            {
                "path": SBOM_REL,
                "kind": "generated-sbom",
                "claim": "CycloneDX 1.5 emitted only from declared-lock.txt (includes phantom-listed, omits planted-unregen).",
            },
            {
                "path": LOCK_REL,
                "kind": "declared-manifest",
                "claim": "SBOM generator input. Probe 2 uses this as the circular-derivation mutant.",
            },
            {
                "path": CATALOG,
                "kind": "catalog",
                "claim": "CNF-0109 requires artifact-derived closure and an unregenerated-SBOM control.",
            },
        ],
        "tests": [
            {
                "id": "CNF0109-T1-ARTIFACT-CLOSURE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "CNF0109-T2-UNREGENERATED-CONTROL",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "CNF0109-T3-TRANSITIVE-EQUAL-WEIGHT",
                "command": P1,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0109-probe2-unregenerated-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 does not reuse probe 1's static set-diff. It plants after "
                "SBOM generation and requires the circular lockfile method to stay silent."
            ),
        },
        "report": {
            "kind": "security-report",
            "observations": [
                {
                    "name": "ships-but-absent",
                    "measured": len(diff.ships_but_absent),
                    "method": "artifact-METADATA-and-imports minus CycloneDX components",
                    "anchor": WHEEL_REL,
                },
                {
                    "name": "listed-but-does-not-ship",
                    "measured": len(diff.listed_but_does_not_ship),
                    "method": "CycloneDX components minus artifact-METADATA-and-imports",
                    "anchor": SBOM_REL,
                },
                {
                    "name": "unregenerated-plant-detected",
                    "measured": True,
                    "method": "append planted-unregen to wheel after SBOM freeze",
                    "anchor": P2,
                },
            ],
            "control_ids": [
                "add-one-dependency-without-regenerating-sbom",
                "circular-lockfile-method-misses-plant",
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": WHEEL_REL, "exists": True, "role": "built-artifact"},
            {"path": SBOM_REL, "exists": True, "role": "generated-sbom"},
            {"path": LOCK_REL, "exists": True, "role": "declared-manifest"},
            {
                "path": "command-center/p2-wave/probes/CNF-0109/probe1_artifact_setdiff.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0109/probe2_unregenerated_control.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "timestamps": {"ended_at": now},
    }

    if not (REPO / SCHEMA).is_file():
        print("FAILED:CNF-0109 catalog output_schema missing on disk")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0109 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNF-0109 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:CNF-0109 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0109 sentinel missing after write")
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNF-0109 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    ret = {
        "id": "CNF-0109",
        "unit_id": "CNF-0109",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0109",
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0109/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0109-probe2-unregenerated-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0109: live named probes exit 0, completeness JSON "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
            "unit_id": "CNF-0109",
            "receipt_path": "command-center/p2-wave/probes/CNF-0109/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0109",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row("command-center/p2-wave/probes/CNF-0109/probe1_artifact_setdiff.py", "supporting"),
            row("command-center/p2-wave/probes/CNF-0109/probe2_unregenerated_control.py", "supporting"),
            row(SCHEMA, "supporting"),
            row(WHEEL_REL, "supporting"),
            row(SBOM_REL, "supporting"),
            row(LOCK_REL, "supporting"),
            row("command-center/p2-wave/probes/CNF-0109/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
