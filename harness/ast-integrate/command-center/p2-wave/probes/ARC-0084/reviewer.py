"""Independent contract reviewer. Does not import schema_build or emit_contract."""
from __future__ import annotations

import json
from pathlib import Path

from validate_schema import check_contract_is_schema, envelope_errors, load_contract

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

MANDATED = (
    "artifact_id",
    "producing_unit",
    "content_hash",
    "byte_size",
    "schema_reference",
    "sentinel",
    "evidence_anchors",
    "retention_class",
    "manifest_registration",
)


def review() -> dict:
    doc = load_contract()
    failed: list[str] = []
    schema_errs = check_contract_is_schema(doc)
    if schema_errs:
        failed.append(f"meta-schema: {schema_errs[0][:200]}")

    required = list(
        ((doc.get("$defs") or {}).get("artifact_envelope") or {}).get("required") or []
    )
    for name in MANDATED:
        if name not in required:
            failed.append(f"required-missing:{name}")

    floors = doc.get("size_floors") or {}
    if not isinstance(floors, dict) or not floors:
        failed.append("size_floors-absent")
    for cls, floor in floors.items():
        if not isinstance(floor, int) or floor <= 1:
            failed.append(f"floor-not-real:{cls}={floor}")

    derivation = doc.get("size_floor_derivation") or {}
    classes = derivation.get("classes") or {}
    if not classes:
        failed.append("derivation-absent")
    for cls, row in classes.items():
        if not isinstance(row, dict):
            failed.append(f"derivation-row:{cls}")
            continue
        members = row.get("members") or []
        if cls != "contract" and len(members) < 1:
            failed.append(f"derivation-empty:{cls}")
        live_sizes: list[int] = []
        floor = int(floors.get(cls) or 0)
        for member in members:
            rel = str(member.get("path") or "")
            path = REPO / rel
            if not path.is_file():
                failed.append(f"derivation-missing:{rel}")
                continue
            actual = path.stat().st_size
            live_sizes.append(actual)
            if floor and actual < floor:
                failed.append(f"member-below-floor:{rel}:{actual}<{floor}")
        # Snapshot bytes in the contract may drift under sibling writes; the
        # floor remains valid iff every still-present member clears it.
        if live_sizes and floor and min(live_sizes) < floor:
            failed.append(f"live-min-below-floor:{cls}")

    rule = str(doc.get("completeness_rule") or "") + str(doc.get("description") or "")
    if "ARTIFACT-MANIFEST.json" not in rule:
        failed.append("rule-omits-manifest")
    if "not complete" not in rule.lower() and "unregistered" not in rule.lower():
        failed.append("rule-omits-unregistered-failure")

    # Structure: a 1-byte receipt must be schema-invalid (floor is a real threshold).
    tiny = {
        "artifact_id": "ARC-0084:primary",
        "producing_unit": "ARC-0084",
        "path": "out/payload.json",
        "artifact_class": "receipt",
        "content_hash": {"alg": "sha256", "hex": "a" * 64},
        "byte_size": 1,
        "schema_reference": "https://json-schema.org/draft/2020-12/schema",
        "sentinel": "SUCCESS:ARC-0084-FIXTURE",
        "evidence_anchors": [
            {"path": "ARTIFACT-MANIFEST.json", "claim": "tiny receipt must fail the floor"}
        ],
        "retention_class": "session",
        "manifest_registration": {
            "manifest_path": "ARTIFACT-MANIFEST.json",
            "path": "out/payload.json",
            "sha256": "a" * 64,
            "bytes": 1,
            "present": True,
            "producing_unit": "ARC-0084",
        },
    }
    tiny_errs = envelope_errors(tiny, doc)
    if not tiny_errs:
        failed.append("one-byte-receipt-accepted")

    missing = dict(tiny)
    missing["byte_size"] = 4096
    del missing["artifact_id"]
    miss_errs = envelope_errors(missing, doc)
    if not miss_errs:
        failed.append("missing-artifact_id-accepted")

    ok = not failed
    return {
        "reviewer_id": "ARC-0084-independent-contract",
        "verdict": "PASS" if ok else "FAIL",
        "independent": True,
        "did_not_author_schema_build": True,
        "failed": failed,
        "mandated_required_ok": all(n in required for n in MANDATED),
        "floors": floors,
        "one_byte_receipt_rejected": bool(tiny_errs),
        "missing_id_rejected": bool(miss_errs),
        "meta_schema_ok": not schema_errs,
        "method": (
            "Re-read command-center/phase4/contracts/ARC-0084.json from disk. "
            "Checked mandated required[] names, re-stat derivation members, "
            "rejected a 1-byte receipt against the frozen schema, and confirmed "
            "the completeness rule names on-disk ARTIFACT-MANIFEST.json."
        ),
    }


def main() -> int:
    rec = review()
    print(json.dumps(rec, indent=2, sort_keys=True))
    if rec.get("verdict") != "PASS":
        print("FAILED:ARC-0084-reviewer")
        return 1
    print("SUCCESS:ARC-0084-reviewer independent contract review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
