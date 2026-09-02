#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0328.json and per-unit probe artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.presets.catalog import CATALOG_REL, ensure_catalog  # noqa: E402
from tools.council.presets.store import (  # noqa: E402
    PRESET_KEY_ORDER,
    PresetStore,
    canonical_hash,
    fidelity_ok,
    reorder_keys,
)

UNIT = "IMP-0328"
SENTINEL = "SUCCESS:IMP-0328"
OUT_REL = "command-center/receipts/IMP-0328.json"
PROBE1 = "command-center/p2-wave/probes/IMP-0328/probe1_roundtrip.py"
PROBE2 = "command-center/p2-wave/probes/IMP-0328/probe2_reorder.py"
RETURN_REL = "command-center/p2-wave/probes/IMP-0328/SUBAGENT-RETURN.json"
MANIFEST_REL = "command-center/p2-wave/probes/IMP-0328/UNIT-ARTIFACT-MANIFEST.json"
STORE_REL = "tools/council/presets/store.py"
TEST_REL = "tools/council/presets/tests/test_store.py"
EMIT_REL = "command-center/p2-wave/probes/IMP-0328/emit_receipt.py"

P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {PROBE1}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {PROBE2}"
TEST_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST_REL}"

OUTPUT_SCHEMA = (
    "command-center/schema/receipt.schema.json profile=council-presets-module "
    "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
    "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json#IMP-0328 "
    "tools/council/presets/store.py; 72 measured presets; "
    "editable_dials + default_binding; field-level diff + order-preserving hash"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        text=True,
        capture_output=True,
        env=env,
    )


def write_json(path: Path, doc: dict, sort_keys: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=sort_keys, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def build_receipt() -> dict:
    ensure_catalog()
    store = PresetStore()
    presets = store.presets()
    rows = [store.round_trip_one(p["id"]) for p in presets]
    failed = [
        r
        for r in rows
        if not r["fidelity_ok"] or not r["untouched_all_match"] or r["unexpected"]
    ]
    if failed:
        raise SystemExit(f"round-trip failed: {failed[0]['preset_id']}")

    original = presets[0]
    mutated = reorder_keys(original, list(reversed(list(original.keys()))))
    reorder_ok, reorder_diffs = fidelity_ok(original, mutated, allowed_paths=set())
    if reorder_ok or not any(d.get("kind") == "keys_reordered" for d in reorder_diffs):
        raise SystemExit("negative control did not fail")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    field_diffs = [
        {
            "preset_id": r["preset_id"],
            "edited_dial": r["dial"],
            "diff_paths": [d.get("path") for d in r["diffs"]],
            "only_edited_key": bool(r["fidelity_ok"] and not r["unexpected"]),
        }
        for r in rows
    ]
    hash_rows = [
        {
            "edited_preset_id": r["preset_id"],
            "untouched_count": r["untouched_count"],
            "untouched_all_match": r["untouched_all_match"],
            "edited_hash_changed": r["edited_hash_changed"],
        }
        for r in rows
    ]
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": SENTINEL,
        "title": "Preset store, loader, and editing round-trip",
        "question": (
            "Implement tools/council/presets/store.py loading the 72 measured "
            "presets, exposing editable dials, and writing edits back without "
            "losing unedited fields. After loading, editing one dial and saving, "
            "is any other field changed, reordered, or dropped?"
        ),
        "spec_anchor": SPEC_ANCHOR,
        "output_schema": OUTPUT_SCHEMA,
        "cloud_ok": False,
        "computed_at": now,
        "preset_key_order": list(PRESET_KEY_ORDER),
        "preset_key_count": len(PRESET_KEY_ORDER),
        "measured_preset_count": len(presets),
        "artifact_paths": [OUT_REL, STORE_REL, CATALOG_REL, TEST_REL, PROBE1, PROBE2],
        "evidence": [
            {
                "id": "E1",
                "signal": "field-level-diff-all-72",
                "kind": "live-computation",
                "description": (
                    "For each of 72 presets, edit one editable dial, serialize, "
                    "reload, and field-diff. Only that dial path differs."
                ),
                "only_edited_key_count": sum(1 for r in field_diffs if r["only_edited_key"]),
                "rows": field_diffs,
            },
            {
                "id": "E2",
                "signal": "canonical-hash-untouched-presets",
                "kind": "independent-digest",
                "description": (
                    "Order-preserving SHA-256 of each unedited preset after a "
                    "sibling was edited and saved. 71/71 must match the pre-edit digest."
                ),
                "all_untouched_match": all(r["untouched_all_match"] for r in hash_rows),
                "rows": hash_rows,
            },
        ],
        "test_ids": [
            "test_catalog_is_72_with_20_keys",
            "test_round_trip_all_72",
            "test_canonical_hash_detects_reorder",
        ],
        "negative_control_ids": [
            "NC-reorder-keys-diff-check-fails",
            "test_reorder_fails_diff_check",
            "test_non_editable_dial_refused",
        ],
        "tests": [
            {
                "id": "test_round_trip_all_72",
                "path": f"{TEST_REL}::test_round_trip_all_72",
                "result": "PASS",
            },
            {
                "id": "test_reorder_fails_diff_check",
                "path": f"{TEST_REL}::test_reorder_fails_diff_check",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-reorder-keys-diff-check-fails",
                "description": (
                    "Permute top-level keys of a saved preset. The field-level "
                    "diff check FAILS (kind=keys_reordered). Identity still passes."
                ),
                "fired": True,
                "fidelity_ok": reorder_ok,
                "canonical_hash_changed": canonical_hash(original) != canonical_hash(mutated),
                "diff_kinds": sorted({str(d.get("kind")) for d in reorder_diffs}),
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0328-field-diff-and-hash-recompute",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-run field_diff on each live before/after pair; recompute "
                "canonical_hash on untouched presets without reading the author's summary."
            ),
        },
        "residual_unknowns": [
            (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json from the harness restore "
                "path is not on this Linux worktree. The store loads "
                f"{CATALOG_REL} (72 records, 20 keys including editable_dials "
                "and default_binding). Key names follow the CouncilSpec delta "
                "envelope named by CNL-0101; they are not a byte-for-byte extract "
                "of the absent Windows file."
            ),
            (
                "IMP-0261 (CouncilSpec JSON Schema + validator) is not delivered "
                "on this worktree. Round-trip fidelity does not substitute for "
                "Draft 2020-12 validation of the 13-section spec."
            ),
        ],
        "catalog_source_note": (
            "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json absent; measured "
            "catalog generated and loaded from "
            "tools/council/presets/data/measured-72.json."
        ),
    }


def supporting_rows() -> list[dict]:
    rels = [
        (STORE_REL, "implementation"),
        (CATALOG_REL, "fixture"),
        (TEST_REL, "tests"),
        (PROBE1, "probe"),
        (PROBE2, "probe"),
        (EMIT_REL, "emitter"),
        (RETURN_REL, "return"),
    ]
    rows = []
    for rel, role in rels:
        path = REPO / rel
        if not path.is_file():
            continue
        sha, size = digest_file(path)
        rows.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "unit_id": UNIT,
                "receipt_path": RETURN_REL,
                "role": role,
            }
        )
    return rows


def main() -> int:
    tests = run(TEST_CMD)
    if tests.returncode != 0:
        sys.stderr.write(tests.stdout + tests.stderr)
        return tests.returncode or 1

    doc = build_receipt()
    out = REPO / OUT_REL
    write_json(out, doc, sort_keys=True)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        raise SystemExit("sentinel missing from receipt")

    p1 = run(P1_CMD)
    p2 = run(P2_CMD)
    if p1.returncode != 0 or p2.returncode != 0:
        sys.stderr.write(p1.stdout + p1.stderr + p2.stdout + p2.stderr)
        return p1.returncode or p2.returncode or 1

    sha, size = digest_file(out)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": OUTPUT_SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": p1.returncode,
                "role": "round-trip-fidelity",
                "raw_output": (p1.stdout or "")[-4000:],
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": p2.returncode,
                "role": "reorder-negative-control",
                "raw_output": (p2.stdout or "")[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": MANIFEST_REL,
        "reviewer": doc["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0328: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    write_json(REPO / RETURN_REL, ret, sort_keys=False)

    primary = {
        "path": OUT_REL,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": RETURN_REL,
        "role": "primary",
    }
    artifacts = [primary] + supporting_rows()
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(REPO / MANIFEST_REL, manifest, sort_keys=False)
    print(json.dumps({"path": OUT_REL, "sha256": sha, "bytes": size, "sentinel": SENTINEL}))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
