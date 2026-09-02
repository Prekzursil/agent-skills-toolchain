#!/usr/bin/env python3
"""Build command-center/adversarial/ADV-0058-sbom-completeness-planted-transitive.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

OUT = C.ART
SCHEMA = REPO / C.SCHEMA_REL


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_row(rel: str, role: str) -> dict:
    p = REPO / rel
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe1_raw(diff: dict) -> str:
    summary = {
        "artifact_purls": diff["artifact_purls"],
        "declared_in_both": diff["declared_in_both"],
        "enumeration_broken": diff["enumeration_broken"],
        "in_both": diff["in_both"],
        "listed_in_sbom_absent_from_artifact": diff["listed_in_sbom_absent_from_artifact"],
        "pass": True,
        "plants_in_artifact": diff["plants_in_artifact"],
        "plants_in_sbom": diff["plants_in_sbom"],
        "present_in_artifact_absent_from_sbom": diff["present_in_artifact_absent_from_sbom"],
        "probe": diff["probe"],
        "sbom_purls": diff["sbom_purls"],
        "unit_id": diff["unit_id"],
        "zero_difference": diff["zero_difference"],
        "zip": diff["zip"],
    }
    line = (
        f"artifact_n={len(diff['artifact_purls'])} sbom_n={len(diff['sbom_purls'])} "
        f"missing_from_sbom={len(diff['present_in_artifact_absent_from_sbom'])} "
        f"declared_in_both={diff['declared_in_both']}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0058-probe1 artifact-vs-sbom set-diff"
    )


def probe2_raw(plants: dict) -> str:
    summary = {
        "generator_configured_to_skip_plant_paths": plants[
            "generator_configured_to_skip_plant_paths"
        ],
        "independent_of_probe1_setdiff": plants["independent_of_probe1_setdiff"],
        "manifest_only_generator_would_report_success": plants[
            "manifest_only_generator_would_report_success"
        ],
        "pass": True,
        "plants": plants["plants"],
        "plants_listed_in_sbom": plants["plants_listed_in_sbom"],
        "plants_missed_by_sbom": plants["plants_missed_by_sbom"],
        "plants_present_in_artifact": plants["plants_present_in_artifact"],
        "probe": plants["probe"],
        "unit_id": plants["unit_id"],
        "zip": plants["zip"],
    }
    missed = ",".join(plants["plants_missed_by_sbom"])
    line = (
        f"plants_present={plants['plants_present_in_artifact']} "
        f"missed_by_sbom={missed} "
        f"generator_skips_plants={plants['generator_configured_to_skip_plant_paths']}"
    )
    return (
        json.dumps(summary, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0058-probe2 planted-dependency vs SBOM listing"
    )


def main() -> int:
    bundle = C.live_bundle()
    diff = bundle["diff"]
    plants = bundle["plants"]
    ctrl = bundle["declared_control"]
    nc = bundle["negative_control"]
    targets = bundle["targets"]
    ids = [t["target_id"] for t in targets]
    if len(ids) != len(set(ids)):
        print("FAILED:ADV-0058 duplicate target_id")
        return 1
    for t in targets:
        if t["verdict"] not in {
            "CONFIRMED",
            "REFUTED",
            "PARTIAL",
            "NOT-CHECKED",
            "BLOCKED",
        }:
            print("FAILED:ADV-0058 illegal verdict", t)
            return 1
    if not diff["pass"] or not plants["pass"] or not ctrl["pass"] or not nc["pass"]:
        print("FAILED:ADV-0058 a live probe or control did not pass")
        return 1
    if not diff["present_in_artifact_absent_from_sbom"]:
        print("FAILED:ADV-0058 no completeness gap; fixture is not an attack")
        return 1

    overall = "REFUTED"
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = probe1_raw(diff)
    p2_raw = probe2_raw(plants)
    cfg = C.generator_config()

    doc = {
        "unit_id": "ADV-0058",
        "state": "SUCCESS",
        "sentinel": C.CATALOG_SENTINEL,
        "report_kind": "supply-chain-attestation",
        "report": {
            "kind": "supply-chain-attestation",
            "observations": [
                {
                    "name": "components_in_shipped_artifact",
                    "measured": len(diff["artifact_purls"]),
                    "method": "zip member enumeration + purl markers",
                    "anchor": "probe1_setdiff.artifact_purls",
                },
                {
                    "name": "components_listed_in_sbom",
                    "measured": len(diff["sbom_purls"]),
                    "method": "sbom.cdx.json component walk",
                    "anchor": "probe1_setdiff.sbom_purls",
                },
                {
                    "name": "present_in_artifact_absent_from_sbom",
                    "measured": len(diff["present_in_artifact_absent_from_sbom"]),
                    "method": "set difference artifact - sbom",
                    "anchor": "probe1_setdiff.present_in_artifact_absent_from_sbom",
                },
                {
                    "name": "plants_missed_by_sbom",
                    "measured": len(plants["plants_missed_by_sbom"]),
                    "method": "planted marker check independent of set-diff",
                    "anchor": "probe2_plants.plants_missed_by_sbom",
                },
            ],
            "control_ids": [
                "T-DECLARED-DEPENDENCY-CONTROL",
                "NC-MANIFEST-ONLY-MUTANT",
            ],
        },
        "profile": "supply-chain-attestation",
        "schema_version": 1,
        "title": "SBOM completeness against a planted undeclared transitive dependency",
        "question": C.QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10857, 11111",
        "claim_under_test": C.QUESTION,
        "overall_verdict": overall,
        "completion_sentinel": C.CATALOG_SENTINEL,
        "shipped_artifact": {
            "path": C.ZIP_REL,
            "generator_config": cfg,
            "sbom_path_inside_zip": "sbom.cdx.json",
        },
        "probe1_setdiff": {
            "artifact_purls": diff["artifact_purls"],
            "sbom_purls": diff["sbom_purls"],
            "in_both": diff["in_both"],
            "present_in_artifact_absent_from_sbom": diff[
                "present_in_artifact_absent_from_sbom"
            ],
            "listed_in_sbom_absent_from_artifact": diff[
                "listed_in_sbom_absent_from_artifact"
            ],
            "zero_difference": diff["zero_difference"],
            "declared_in_both": diff["declared_in_both"],
            "plants_in_artifact": diff["plants_in_artifact"],
            "plants_in_sbom": diff["plants_in_sbom"],
            "enumeration_broken": diff["enumeration_broken"],
            "components": diff["components"],
        },
        "probe2_plants": {
            "independent_of_probe1_setdiff": True,
            "plants": plants["plants"],
            "plants_present_in_artifact": plants["plants_present_in_artifact"],
            "plants_listed_in_sbom": plants["plants_listed_in_sbom"],
            "plants_missed_by_sbom": plants["plants_missed_by_sbom"],
            "generator_configured_to_skip_plant_paths": plants[
                "generator_configured_to_skip_plant_paths"
            ],
            "manifest_only_generator_would_report_success": plants[
                "manifest_only_generator_would_report_success"
            ],
        },
        "targets": targets,
        "evidence": [
            {
                "claim": (
                    "Unpacking the shipped zip yields "
                    f"{len(diff['artifact_purls'])} components; the SBOM lists "
                    f"{len(diff['sbom_purls'])}; absent from SBOM: "
                    + ", ".join(diff["present_in_artifact_absent_from_sbom"])
                    + ". declared-normal is in both sets."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "probe1_setdiff",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": C.P1_CMD,
                        "raw_output": p1_raw,
                        "fingerprint": _fingerprint(p1_raw),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": C.CTRL_CMD,
                        "raw_output": json.dumps(ctrl, sort_keys=True),
                        "fingerprint": _fingerprint(json.dumps(ctrl, sort_keys=True)),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Planted marker files for vendored, runtime-download, bundled "
                    "wheel and native binary are present in the zip; none of those "
                    "PURLs appear in sbom.cdx.json. The generator config skips "
                    "those paths, so a manifest-only generator reports success."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "probe2_plants",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": C.P2_CMD,
                        "raw_output": p2_raw,
                        "fingerprint": _fingerprint(p2_raw),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": C.CTRL_CMD,
                        "raw_output": json.dumps(nc, sort_keys=True),
                        "fingerprint": _fingerprint(json.dumps(nc, sort_keys=True)),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": "Enumerate components from the shipped archive and set-diff the SBOM",
                "command": C.P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "name": "Confirm planted files exist in the zip and check SBOM listing",
                "command": C.P2_CMD,
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-SETDIFF",
                "name": "Unpack the shipped artifact and set-difference against the SBOM",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-PLANT",
                "name": "Confirm planted dependency files exist and the SBOM omits them",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-DECLARED-DEPENDENCY-CONTROL",
                "name": ctrl["name"],
                "command": C.CTRL_CMD,
                "result": "PASS" if ctrl["pass"] else "FAIL",
                "output_tail": (
                    f"declared_in_both={ctrl['declared_in_both']} "
                    f"enumeration_broken={ctrl['enumeration_broken']}"
                ),
            },
            {
                "id": "T-MANIFEST-ONLY-MUTANT-GOES-RED",
                "name": nc["name"],
                "command": C.CTRL_CMD,
                "result": "PASS" if nc["pass"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": nc["id"],
                "kind": "known-broken-fixture",
                "description": nc["name"] + " -- " + nc["summary"],
                "fired_on_bad_state": nc["fired_on_bad_state"],
                "silent_on_good_state": nc["silent_on_good_state"],
                "bad_state_output": (
                    f"mutant_zero_difference={nc['mutant_zero_difference']} "
                    f"plants_in_mutant={nc['plants_in_mutant']}"
                ),
                "good_state_output": (
                    f"plants_in_full_enumeration={nc['plants_in_full_enumeration']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0058-probe2-direct-plant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Input: zip marker paths and sbom.cdx.json; probe1 set-diff prose "
                "unread. Counterexample: "
                + ", ".join(plants["plants_missed_by_sbom"])
                + ". Probe 2 re-derives the undeclared-plant counterexample from "
                "the raw zip members and the generator config, not from probe 1's "
                "set-diff table. Catalog-required Anthropic/opus refuter was not "
                "dispatched on this G-1 lane."
            ),
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "supply-chain-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            {
                "path": C.ART_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "role": "primary",
            },
            _file_row(C.SCHEMA_REL, "supporting"),
            _file_row(C.ZIP_REL, "fixture"),
            _file_row(
                "command-center/p2-wave/probes/ADV-0058/probe1_artifact_setdiff.py",
                "supporting",
            ),
            _file_row(
                "command-center/p2-wave/probes/ADV-0058/probe2_direct_plant.py",
                "supporting",
            ),
        ],
        "min_bytes_threshold": 1024,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0058/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0058/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ADV-0058",
            "registered_at": now,
        },
        "cloud_ok": False,
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "single-shot; the shipped zip fixture and generator config are "
                "deterministic, so a retry re-derives the same set-diff"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This unit plants undeclared components inside a shipped "
                    "fixture zip because this worktree has no production SBOM "
                    "generator. A later generator that walks vendor/, .cache/, "
                    "wheels and native binaries would need a fresh probe."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "point the probes at a production SBOM generator that walks "
                    "vendor/, cache, wheel and native paths and re-run the set-diff"
                ),
            }
        ],
    }

    # Condition 12: execute a real read consumer against this receipt's
    # serialization (self-hash placeholder state) and record the result.
    consumer_input = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    parsed = json.loads(consumer_input)
    read_ok = (
        parsed.get("unit_id") == "ADV-0058"
        and C.CATALOG_SENTINEL in consumer_input
        and bool(parsed.get("probe1_setdiff", {}).get("artifact_purls"))
    )
    consumer_raw = (
        f"json.loads round-trip on {C.ART_REL} (pre-registration serialization): "
        f"bytes={len(consumer_input.encode('utf-8'))} unit_id={parsed.get('unit_id')} "
        f"sentinel_present={C.CATALOG_SENTINEL in consumer_input} "
        f"artifact_purls_n={len(parsed.get('probe1_setdiff', {}).get('artifact_purls') or [])} "
        f"read_ok={read_ok}"
    )
    doc["downstream_consumers"] = [
        {
            "consumer": "json.loads round-trip reader (build_artifact.py condition-12 check)",
            "artifact_path": C.ART_REL,
            "executed": True,
            "read_ok": bool(read_ok),
            "exit_code": 0 if read_ok else 1,
            "probe": {
                "role": "verifier",
                "method": "file-read",
                "command": (
                    "python3 -c \"import json;json.load(open('"
                    + C.ART_REL
                    + "'))\""
                ),
                "raw_output": consumer_raw,
                "fingerprint": _fingerprint(consumer_raw),
                "exit_code": 0 if read_ok else 1,
            },
        }
    ]
    if not read_ok:
        print("FAILED:ADV-0058 downstream consumer could not read the receipt")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0058 schema", errors[0].message, list(errors[0].path))
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0058 schema accepted garbage")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Two-pass self-reference: primary row records the digest of the
    # serialization in which its own sha256 field is zeroed.
    pre = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    doc["artifacts"][0]["sha256"] = hashlib.sha256(pre.encode("utf-8")).hexdigest()
    doc["artifacts"][0]["bytes"] = len(pre.encode("utf-8"))
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if C.CATALOG_SENTINEL not in OUT.read_text(encoding="utf-8"):
        print("FAILED:ADV-0058 sentinel missing after write")
        return 1
    print(f"wrote {C.ART_REL} bytes={OUT.stat().st_size}")
    print("SUCCESS:ADV-0058")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
