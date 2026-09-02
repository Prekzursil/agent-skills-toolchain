#!/usr/bin/env python3
"""Gold receipt plus ten single-condition mutants for the CC-0003 reducer.

The live reducer at platform/lib/completion_predicate.py evaluates twelve
conditions. Gold must SATISFY all twelve so COMPLETE is reachable. The catalog
for THIS unit contracts ten falsifiers (conditions 1-10). Conditions 11-12 stay
green on those mutants except where a missing file makes 3/4/5 NOT-CHECKED
(owned by condition 2).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

UNIT = "FX-0001"
SENTINEL = "SUCCESS:FX-0001"
SCHEMA_REL = "artifact.schema.json"
ART_REL = "artifact.json"
MANIFEST_REL = "ARTIFACT-MANIFEST.json"
ANCHOR_REL = "src/module.py"

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["unit_id", "sentinel", "kind", "payload"],
    "properties": {
        "unit_id": {"type": "string"},
        "sentinel": {"type": "string"},
        "kind": {"const": "fixture"},
        "payload": {"type": "string"},
    },
    "additionalProperties": True,
}


def _digest(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def gold_artifact() -> dict[str, Any]:
    return {
        "unit_id": UNIT,
        "sentinel": SENTINEL,
        "kind": "fixture",
        "payload": "P" * 180,
    }


def gold_receipt_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "min_bytes_threshold": 128,
        "artifact_schema": SCHEMA_REL,
        "output_schema": SCHEMA_REL,
        "artifacts": [
            {
                "path": ART_REL,
                "role": "primary",
                "exists": True,
                "sha256": "0" * 64,
                "bytes": 0,
            }
        ],
        "evidence": [
            {
                "claim": "fixture produced a measurable artifact",
                "verdict": "CONFIRMED",
                "anchor": f"{ANCHOR_REL}:10",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": f"read {ANCHOR_REL}:10",
                        "raw_output": "line 10",
                        "fingerprint": "fp-source-1",
                    },
                    {
                        "role": "verifier",
                        "method": "sha256",
                        "command": "sha256sum artifact.json",
                        "raw_output": "digest match",
                        "fingerprint": "fp-verifier-1",
                    },
                ],
            },
            {
                "claim": "the artifact is registered in the manifest",
                "verdict": "CONFIRMED",
                "anchor": "python -c manifest lookup",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "read ARTIFACT-MANIFEST.json",
                        "raw_output": "found artifact.json",
                        "fingerprint": "fp-source-2",
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": "sha256 compare",
                        "raw_output": "digest match",
                        "fingerprint": "fp-verifier-2",
                    },
                ],
            },
        ],
        "tests": [{"id": "t-gold", "command": "true", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "c-both",
                "kind": "known-broken-fixture",
                "description": "detector fires on missing artifact and is silent on gold",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "fixture-reader",
                "artifact_path": ART_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python -c read",
                    "raw_output": "ok",
                    "fingerprint": "fp-consumer-1",
                },
            }
        ],
    }


def write_tree(
    root: Path, artifact: dict[str, Any] | None, receipt: dict[str, Any]
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    (root / SCHEMA_REL).write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ANCHOR_REL).write_text(
        "\n".join(f"line {i}" for i in range(1, 61)) + "\n", encoding="utf-8"
    )
    art_path = root / ART_REL
    receipt = copy.deepcopy(receipt)
    if artifact is not None:
        raw = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode("utf-8")
        art_path.write_bytes(raw)
        digest, size = _digest(raw)
        receipt["artifacts"][0]["sha256"] = digest
        receipt["artifacts"][0]["bytes"] = size
        receipt["artifacts"][0]["exists"] = True
        manifest_sha, manifest_bytes = digest, size
    else:
        receipt["artifacts"][0]["sha256"] = "a" * 64
        receipt["artifacts"][0]["bytes"] = 4096
        receipt["artifacts"][0]["exists"] = True
        if art_path.exists():
            art_path.unlink()
        manifest_sha, manifest_bytes = "a" * 64, 4096
    (root / MANIFEST_REL).write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": ART_REL,
                        "bytes": manifest_bytes,
                        "sha256": manifest_sha,
                        "present": artifact is not None,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def gold_tree(root: Path) -> dict[str, Any]:
    return write_tree(root, gold_artifact(), gold_receipt_template())


def _mut_c1(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["state"] = "BLOCKED"
    return receipt, artifact


def _mut_c2(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, None]:
    del artifact
    return receipt, None


def _mut_c3(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    # Raise the floor above the real size so only condition 3 is unsatisfied.
    receipt["min_bytes_threshold"] = 10_000_000
    return receipt, artifact


def _mut_c4(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    artifact.pop("kind")
    return receipt, artifact


def _mut_c5(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    artifact["sentinel"] = "NO-SENTINEL"
    return receipt, artifact


def _mut_c6(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["evidence"][0]["probes"][1]["fingerprint"] = receipt["evidence"][0][
        "probes"
    ][0]["fingerprint"]
    return receipt, artifact


def _mut_c7(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["tests"][0]["result"] = "FAIL"
    return receipt, artifact


def _mut_c8(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["negative_controls"][0]["fired_on_bad_state"] = False
    return receipt, artifact


def _mut_c9(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["reviewer"]["verdict"] = "NOT-REVIEWED"
    return receipt, artifact


def _mut_c10(receipt: dict[str, Any], artifact: dict[str, Any]) -> tuple[dict, dict]:
    receipt["defects"] = [
        {
            "id": "FX-D1",
            "severity": "P0",
            "status": "open",
            "summary": "open blocker attached to a success fixture",
        }
    ]
    return receipt, artifact


MUTATORS: dict[int, tuple[str, Callable]] = {
    1: ("state set to BLOCKED (terminal, not completion)", _mut_c1),
    2: ("artifact path listed with fabricated digest; file not written", _mut_c2),
    3: ("primary artifact min_bytes_threshold raised above on-disk size", _mut_c3),
    4: ("required schema field 'kind' omitted", _mut_c4),
    5: ("sentinel token removed from artifact bytes", _mut_c5),
    6: ("evidence source/verifier fingerprints identical (same-probe-rerun)", _mut_c6),
    7: ("tests[0].result set to FAIL", _mut_c7),
    8: ("negative_control.fired_on_bad_state false", _mut_c8),
    9: ("reviewer.verdict set to NOT-REVIEWED", _mut_c9),
    10: ("open P0 defect attached", _mut_c10),
}


def mutant_tree(root: Path, n: int) -> dict[str, Any]:
    how, fn = MUTATORS[n]
    receipt = gold_receipt_template()
    artifact = gold_artifact()
    receipt, artifact = fn(receipt, artifact)
    receipt["_mutation"] = how
    return write_tree(root, artifact, receipt)
