#!/usr/bin/env python3
"""Isolated fixture: artifact exists, parses, carries sentinel; registration varies.

Writer claim: receipt.manifest_registration.registered=true in BOTH trees, and
unit_manifest.derive() includes the unit from receipts. On-disk
command-center/ARTIFACT-MANIFEST.json either omits the row or contains it.
Live evaluate() must read that FILE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import c11 as C  # noqa: E402

FIXTURE_UNIT = "FIX-0149"
FIXTURE_SENTINEL = "SUCCESS:FIX-0149"
ART_REL = "outputs/FIX-0149.json"
SCHEMA_REL = "outputs/FIX-0149.schema.json"
DECOY_REL = "outputs/DEC-0001.txt"
RECEIPT_REL = "command-center/receipts/FIX-0149.json"
DECOY_RECEIPT_REL = "command-center/receipts/DEC-0001.json"
MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
ANCHOR_REL = "src/module.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _encoded(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def _schema_text() -> str:
    return (HERE / "fixture.schema.json").read_text(encoding="utf-8")


def _fixture_receipt(*, live_sha: str, live_bytes: int) -> dict:
    return {
        "schema_version": 1,
        "unit_id": FIXTURE_UNIT,
        "state": "SUCCESS",
        "sentinel": FIXTURE_SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10631-10644",
        "min_bytes_threshold": 512,
        "artifacts": [
            {
                "path": ART_REL,
                "bytes": live_bytes,
                "sha256": live_sha,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": "condition 5 is evaluated against the artifact bytes",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{ANCHOR_REL}:42",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": f"read {ANCHOR_REL}:42",
                        "raw_output": "line 42",
                        "fingerprint": "fp-source-fix0149-a",
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "python -m pytest -k condition5",
                        "raw_output": "1 passed",
                        "fingerprint": "fp-verifier-fix0149-a",
                    },
                ],
            },
            {
                "claim": "the artifact is registered in the manifest",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{ANCHOR_REL}:8",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "read ARTIFACT-MANIFEST.json",
                        "raw_output": f"found {ART_REL}",
                        "fingerprint": "fp-source-fix0149-b",
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": "sha256 compare",
                        "raw_output": "digest match",
                        "fingerprint": "fp-verifier-fix0149-b",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "fixture self-check",
                "command": "python -c fixture",
                "result": "PASS",
            }
        ],
        "negative_controls": [
            {
                "id": "NC1",
                "kind": "mutation",
                "description": "unregistered artifact must fail condition 11",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "codex-fresh-context",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
        },
        "defects": [
            {
                "id": "D-1",
                "severity": "P3",
                "status": "resolved",
                "summary": "cosmetic",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center render.py",
                "artifact_path": ART_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python tools/command-center/render.py --check",
                    "raw_output": "SUCCESS:cc-render",
                    "fingerprint": "fp-consumer-fix0149",
                },
            }
        ],
        "timestamps": {
            "started_at": "2026-08-25T00:00:00Z",
            "ended_at": "2026-08-25T00:01:00Z",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "implementer",
        },
        "residual_unknowns": [],
    }


def populate(root: Path, *, persist_manifest: bool) -> dict:
    artifact_body = {
        "unit_id": FIXTURE_UNIT,
        "verdict": "CONFIRMED",
        "sentinel": FIXTURE_SENTINEL,
        "body": "measured body text for TST-0149 condition 11. " * 40,
    }
    art_path = root / ART_REL
    _write(art_path, _encoded(artifact_body))
    live_sha, live_bytes = C.digest_file(art_path)
    _write(root / SCHEMA_REL, _schema_text())
    _write(
        root / ANCHOR_REL,
        "\n".join(f"line {i}" for i in range(1, 61)) + "\n",
    )

    decoy = root / DECOY_REL
    _write(decoy, "decoy-for-nonempty-manifest\n")
    decoy_sha, decoy_bytes = C.digest_file(decoy)
    _write(
        root / DECOY_RECEIPT_REL,
        json.dumps({"unit_id": "DEC-0001", "artifacts": [{"path": DECOY_REL}]}, indent=2)
        + "\n",
    )

    receipt = _fixture_receipt(live_sha=live_sha, live_bytes=live_bytes)
    _write(root / RECEIPT_REL, _encoded(receipt))

    um = C.load_unit_manifest_mod()
    derived = um.derive(root)
    in_memory = C.c11_from_in_memory_derive(
        derived,
        unit_id=FIXTURE_UNIT,
        artifact_rel=ART_REL,
        live_sha256=live_sha,
    )
    writer_return = {
        "registered": True,
        "source": "receipt.manifest_registration.registered plus unit_manifest.derive()",
        "derived_expected": derived.get("expected"),
        "in_memory_c11": in_memory,
    }

    decoy_row = {
        "path": DECOY_REL,
        "sha256": decoy_sha,
        "bytes": decoy_bytes,
        "present": True,
        "unit_id": "DEC-0001",
        "receipt_path": DECOY_RECEIPT_REL,
    }
    unit_row = {
        "path": ART_REL,
        "sha256": live_sha,
        "bytes": live_bytes,
        "present": True,
        "unit_id": FIXTURE_UNIT,
        "receipt_path": RECEIPT_REL,
    }
    if persist_manifest:
        on_disk = {
            "schema_version": 1,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "persisted-from-derive",
            "artifacts": [decoy_row, unit_row],
        }
    else:
        on_disk = {
            "schema_version": 1,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "stale-writer-did-not-persist-this-unit",
            "artifacts": [decoy_row],
        }
    _write(root / MANIFEST_REL, _encoded(on_disk))

    pre = C.artifact_preconditions(art_path, FIXTURE_SENTINEL)
    live = C.live_evaluate(receipt, root, output_schema=SCHEMA_REL)
    trust = C.c11_trust_writer(writer_return)
    return {
        "root": str(root),
        "persist_manifest": persist_manifest,
        "unit_id": FIXTURE_UNIT,
        "sentinel": FIXTURE_SENTINEL,
        "artifact_rel": ART_REL,
        "artifact_path": str(art_path),
        "receipt_rel": RECEIPT_REL,
        "schema_rel": SCHEMA_REL,
        "live_sha256": live_sha,
        "live_bytes": live_bytes,
        "manifest_rel": MANIFEST_REL,
        "preconditions": pre,
        "live": live,
        "c11_disk": live["c11"],
        "c11_writer_trust": trust,
        "c11_in_memory_derive": in_memory,
        "writer_return": {
            "registered": writer_return["registered"],
            "source": writer_return["source"],
            "derived_expected": writer_return["derived_expected"],
        },
        "condition_vector": live["conditions"],
        "shared_predicate_present": C.shared_predicate_path().is_file(),
        "reducer_id": live["reducer_id"],
    }


def evaluate() -> dict:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tst0149-unreg-") as unreg:
        unregistered = populate(Path(unreg), persist_manifest=False)
    with tempfile.TemporaryDirectory(prefix="tst0149-reg-") as reg:
        registered = populate(Path(reg), persist_manifest=True)

    pre_ok = (
        unregistered["preconditions"]["exists"]
        and unregistered["preconditions"]["parses"]
        and unregistered["preconditions"]["sentinel_present"]
        and registered["preconditions"]["exists"]
        and registered["preconditions"]["parses"]
        and registered["preconditions"]["sentinel_present"]
    )
    isolated = (
        unregistered["live"]["c2"]["outcome"] == "SATISFIED"
        and unregistered["live"]["c4"]["outcome"] == "SATISFIED"
        and unregistered["live"]["c5"]["outcome"] == "SATISFIED"
        and registered["live"]["c2"]["outcome"] == "SATISFIED"
        and registered["live"]["c4"]["outcome"] == "SATISFIED"
        and registered["live"]["c5"]["outcome"] == "SATISFIED"
    )
    both_states = (
        unregistered["c11_disk"]["outcome"] == "UNSATISFIED"
        and registered["c11_disk"]["outcome"] == "SATISFIED"
    )
    writer_trust_wrongly_passes = (
        unregistered["c11_writer_trust"]["outcome"] == "SATISFIED"
        and unregistered["writer_return"]["registered"] is True
    )
    in_memory_wrongly_passes = (
        unregistered["c11_in_memory_derive"]["outcome"] == "SATISFIED"
    )
    disk_ignores_writer = (
        unregistered["c11_disk"]["outcome"] != unregistered["c11_writer_trust"]["outcome"]
    )
    ok = (
        pre_ok
        and isolated
        and both_states
        and writer_trust_wrongly_passes
        and in_memory_wrongly_passes
        and disk_ignores_writer
        and unregistered["shared_predicate_present"]
    )
    return {
        "pass": ok,
        "preconditions_hold": pre_ok,
        "exists_parses_sentinel_while_c11_fails": isolated and both_states,
        "isolated_c2_c4_c5_satisfied": isolated,
        "both_states": both_states,
        "writer_trust_wrongly_passes_unregistered": writer_trust_wrongly_passes,
        "in_memory_derive_wrongly_passes_unregistered": in_memory_wrongly_passes,
        "disk_check_disagrees_with_writer": disk_ignores_writer,
        "shared_predicate_present": C.shared_predicate_path().is_file(),
        "shared_predicate_path": str(C.shared_predicate_path().relative_to(C.REPO)),
        "reducer_id": unregistered["reducer_id"],
        "unregistered": unregistered,
        "registered": registered,
    }


def main() -> int:
    result = evaluate()
    slim = {
        k: result[k]
        for k in (
            "pass",
            "preconditions_hold",
            "isolated_c2_c4_c5_satisfied",
            "both_states",
            "writer_trust_wrongly_passes_unregistered",
            "in_memory_derive_wrongly_passes_unregistered",
            "disk_check_disagrees_with_writer",
            "shared_predicate_present",
            "reducer_id",
        )
    }
    slim["unregistered_c11_disk"] = result["unregistered"]["c11_disk"]["outcome"]
    slim["registered_c11_disk"] = result["registered"]["c11_disk"]["outcome"]
    slim["unregistered_writer_trust"] = result["unregistered"]["c11_writer_trust"][
        "outcome"
    ]
    print(json.dumps(slim, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0149-scenario")
        return 1
    print("SUCCESS:TST-0149-scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
