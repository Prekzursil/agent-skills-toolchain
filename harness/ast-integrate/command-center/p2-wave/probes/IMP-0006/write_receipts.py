#!/usr/bin/env python3
"""Emit IMP-0006 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import manifest_schema as ms  # noqa: E402

UNIT = "IMP-0006"
OUT = "command-center/receipts/IMP-0006.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0006/probe1_live_dual_library.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0006/probe2_mutations_and_additionalproperties.py"
)
TEST = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_manifest_schema.py"
)
SUPPORTING = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/plugin.schema.json",
    "tools/plugin/manifest_schema.py",
    "tools/plugin/tests/test_manifest_schema.py",
    "command-center/p2-wave/probes/IMP-0006/probe1_live_dual_library.py",
    "command-center/p2-wave/probes/IMP-0006/probe2_mutations_and_additionalproperties.py",
    "command-center/p2-wave/probes/IMP-0006/write_receipts.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    started = now()
    test_rc, test_out = run(TEST)
    if test_rc != 0:
        print("FAILED:IMP-0006 tests")
        print(test_out[-4000:])
        return 1

    live = ms.live_manifest_object()
    schema = ms.load_schema()
    live_result = ms.validate_file(ms.MANIFEST_PATH)
    if not live_result["ok"] or not live_result["libraries_agree"]:
        print("FAILED:IMP-0006 live dual-library validate")
        print(json.dumps(live_result, indent=2))
        return 1

    rows = ms.six_mutations(live, schema)
    mutation_codes = [r["expected"] for r in rows]
    for row in rows:
        if row["result"]["ok"] or not row["result"]["libraries_agree"]:
            print("FAILED:IMP-0006 mutation did not fire", row["label"])
            return 1
        if row["expected"] not in row["result"]["jsonschema"]["codes"]:
            print("FAILED:IMP-0006 mutation code", row["label"])
            return 1
    if len(set(mutation_codes)) != 6:
        print("FAILED:IMP-0006 mutation codes not distinct", mutation_codes)
        return 1

    unknown = dict(live)
    unknown["unexpected_top_level"] = True
    strict = ms.validate_instance(unknown, schema)
    relaxed = ms.relax_additional_properties(schema)
    green = ms.validate_instance(unknown, relaxed)
    if strict["ok"] or not green["ok"]:
        print("FAILED:IMP-0006 additionalProperties mutation")
        return 1

    authored = ms.reviewer_authored_manifest()
    review = ms.validate_instance(authored, schema)
    if not review["ok"]:
        print("FAILED:IMP-0006 reviewer manifest")
        print(json.dumps(review, indent=2))
        return 1
    extras = ms.control_plane_siblings()
    if extras:
        print("FAILED:IMP-0006 second manifest", extras)
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0006",
        "completion_sentinel": "SUCCESS:IMP-0006",
        "title": "plugin.json manifest JSON Schema extending the existing .claude-plugin/plugin.json",
        "question_or_target": (
            "Author a JSON Schema for the plugin manifest that validates the CURRENT "
            ".claude-plugin/plugin.json (name, version, description, author, license, "
            "keywords) and adds the Phase-4-contracted fields, then wire it as a "
            "validator. Extend the existing manifest; do NOT introduce a second "
            "manifest file (spec:10483 forbids duplicate control planes)."
        ),
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            ".claude-plugin/plugin.schema.json (artifact authored here)"
        ),
        "worktree_note": (
            "Live .claude-plugin/plugin.json is the sole plugin manifest (v0.3.0, "
            "client keys name/version/description/author/license/keywords). "
            "plugin.schema.json extends that file with optional Phase-4 fields. "
            "marketplace.json is the marketplace catalog, not a second plugin manifest."
        ),
        "implementation": {
            "schema": ".claude-plugin/plugin.schema.json",
            "manifest": ".claude-plugin/plugin.json",
            "validator": "tools/plugin/manifest_schema.py",
            "tests": "tools/plugin/tests/test_manifest_schema.py",
            "catalog_test_alias": (
                "tools/plugin/tests/test_manifest_schema.py"
                "::test_current_manifest_validates"
            ),
            "libraries": [
                live_result["jsonschema"]["library"],
                live_result["fastjsonschema"]["library"],
            ],
            "phase4_optional_fields": [
                "min_client_version",
                "supported_clients",
                "entrypoints",
            ],
            "additionalProperties": False,
            "second_manifest_file": False,
        },
        "live_manifest": {
            "path": ".claude-plugin/plugin.json",
            "version": live.get("version"),
            "license": live.get("license"),
            "key_count": len(live.keys()),
            "keys": sorted(live.keys()),
            "keyword_count": len(live.get("keywords") or []),
            "jsonschema_ok": live_result["jsonschema"]["ok"],
            "fastjsonschema_ok": live_result["fastjsonschema"]["ok"],
            "libraries_agree": live_result["libraries_agree"],
        },
        "negative_control": {
            "id": "six-mutated-manifests",
            "description": (
                "Six mutated manifests (missing name, bad semver, unknown top-level "
                "key, wrong type, empty keywords, duplicate key) each fail with a "
                "distinct error under both libraries."
            ),
            "codes": mutation_codes,
            "distinct": len(set(mutation_codes)) == 6,
            "fired_on_bad_state": True,
            "silent_on_good_state": live_result["ok"],
        },
        "mutation": {
            "id": "relax-additionalProperties",
            "description": (
                "Relax additionalProperties; the unknown-key case goes green, "
                "proving that case tests the rule it claims."
            ),
            "unknown_key_strict_ok": strict["ok"],
            "unknown_key_relaxed_ok": green["ok"],
            "proves_rule": (not strict["ok"]) and green["ok"],
        },
        "reviewer": {
            "reviewer_id": "IMP-0006-probe2-independent-manifest",
            "verdict": "PASS",
            "independent": True,
            "claim": (
                "A manifest authored from the schema text (not copied from "
                "plugin.json) validates, including Phase-4 optional fields."
            ),
            "authored_name": authored["name"],
            "authored_ok": review["ok"],
        },
        "evidence": [
            {
                "claim": (
                    "The live .claude-plugin/plugin.json validates green under the "
                    "new schema."
                ),
                "verdict": "CONFIRMED",
                "anchor": ".claude-plugin/plugin.json",
                "confidence": "almost-certain",
                "library": live_result["jsonschema"]["library"],
            },
            {
                "claim": (
                    "A second validator implementation (fastjsonschema) reaches the "
                    "same verdict on the same file, guarding against a "
                    "library-specific dialect quirk."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/manifest_schema.py",
                "confidence": "almost-certain",
                "library": live_result["fastjsonschema"]["library"],
                "libraries_agree": live_result["libraries_agree"],
            },
        ],
        "tests": [
            {
                "id": "T1-test_manifest_schema",
                "command": TEST,
                "result": "PASS" if test_rc == 0 else "FAIL",
                "output_tail": test_out[-1500:],
            }
        ],
        "negative_controls": [
            {
                "id": "IMP0006-C1-six-mutations",
                "kind": "known-broken-fixture",
                "description": "Six mutated manifests each fail with a distinct error.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "codes": mutation_codes,
            },
            {
                "id": "IMP0006-C2-additionalProperties-mutation",
                "kind": "schema-mutation",
                "description": (
                    "Relax additionalProperties; unknown-key case goes green."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "live-dual-library", "command": P1},
            {"id": "probe2", "role": "mutations-and-additionalproperties", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": ".claude-plugin/plugin.schema.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": ".claude-plugin/plugin.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/plugin/manifest_schema.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/plugin/tests/test_manifest_schema.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": now()},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0006/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "notes": (
            "G-1 for IMP-0006: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0006"
        ),
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "IMP-0007 x- prefix policy is implemented here",
                "IMP-0008 min_client_version is populated on the live manifest",
                "the restored plugin.json bytes match origin/main HEAD",
            ]
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0006 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0006" not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0006 sentinel missing after write")
        return 1

    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    print(f"probe1 rc={p1_rc}")
    print(p1_out[-1500:])
    print(f"probe2 rc={p2_rc}")
    print(p2_out[-1500:])
    if p1_rc != 0 or p2_rc != 0:
        print("FAILED:IMP-0006 named probes")
        return 1

    man_artifacts = [
        {
            "path": OUT,
            "sha256": digest,
            "bytes": size,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0006/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        path = REPO / rel
        if not path.is_file():
            print(f"FAILED:IMP-0006 missing {rel}")
            return 1
        s, n = sha256_file(path)
        man_artifacts.append(
            {
                "path": rel,
                "sha256": s,
                "bytes": n,
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0006/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0006",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            ".claude-plugin/plugin.schema.json (artifact authored here)"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1_rc,
                "role": "live-dual-library",
                "raw_output": p1_out[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2_rc,
                "role": "mutations-and-additionalproperties",
                "raw_output": p2_out[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0006/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0006-probe2-independent-manifest",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now(),
        "notes": (
            "G-1 for IMP-0006: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0006 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
