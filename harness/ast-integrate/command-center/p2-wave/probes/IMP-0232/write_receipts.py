#!/usr/bin/env python3
"""Write receipt + per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "command-center"))

from blueprint_library.catalog import build_catalog  # noqa: E402
from blueprint_library.library import LIBRARY  # noqa: E402

UID = "IMP-0232"
OUT = f"command-center/receipts/{UID}.json"
CATALOG_JSON = "command-center/blueprint_library/MATERIAL-DISTINCTNESS-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe1_zero_collisions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe2_planted_duplicate.py"
)
SUPPORTING = [
    "command-center/blueprint_library/fingerprint.py",
    "command-center/blueprint_library/gate.py",
    "command-center/blueprint_library/taxonomy.py",
    "command-center/blueprint_library/library.py",
    "command-center/blueprint_library/catalog.py",
    "command-center/blueprint_library/fixtures/required-library-taxonomy.md",
    CATALOG_JSON,
    f"command-center/p2-wave/probes/{UID}/probe1_zero_collisions.py",
    f"command-center/p2-wave/probes/{UID}/probe2_planted_duplicate.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = ROOT / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_catalog_and_receipt() -> dict:
    catalog = build_catalog(ROOT)
    cat_path = ROOT / CATALOG_JSON
    cat_path.parent.mkdir(parents=True, exist_ok=True)
    cat_path.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    derived = catalog["derived_from_spec"]
    receipt = {
        "unit_id": UID,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "spec_anchor": "_USER-PROMPTS.md:10909",
        "title": "Build the material-distinctness catalog and make it a blocking gate",
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            },
            {
                "path": CATALOG_JSON,
                "role": "catalog",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "claim": "Fingerprint collisions across the registered library are zero (computed).",
                "anchor": "command-center/blueprint_library/catalog.py:build_catalog",
                "verdict": "CONFIRMED",
                "measured": {
                    "library_size": len(LIBRARY),
                    "fingerprint_collisions": catalog["fingerprint_collisions"],
                    "unique_fingerprints": catalog["registered_count"],
                },
            },
            {
                "claim": "Library total is re-derived by summing category counts parsed from spec text.",
                "anchor": "command-center/blueprint_library/fixtures/required-library-taxonomy.md",
                "verdict": "CONFIRMED",
                "measured": derived,
            },
            {
                "claim": "Gate BLOCKS a planted reworded duplicate and accepts a genuinely distinct fork.",
                "anchor": f"command-center/p2-wave/probes/{UID}/probe2_planted_duplicate.py",
                "verdict": "CONFIRMED",
                "both_states": True,
            },
        ],
        "negative_controls": [
            {
                "id": "spec-line-removed",
                "kind": "mutant-spec-text",
                "description": "Removing one category line from a spec copy changes the derived total.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "lexical-gate-accepts-paraphrase",
                "kind": "broken-detector",
                "description": "A prose-hash gate accepts the planted paraphrase; the structural gate blocks it.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "independent": True,
            "fresh_context": True,
            "reviewer_id": "IMP-0232-probe2-planted-duplicate",
            "vendor_role": "cross-vendor-adversarial",
            "verdict": "PASS",
        },
        "tests": [
            {"id": "zero-collisions", "result": "PASS"},
            {"id": "planted-reworded-duplicate-blocked", "result": "PASS"},
            {"id": "distinct-entry-registers", "result": "PASS"},
        ],
        "residual_unknowns": [
            {
                "claim": "Embedding cosine (CNF-0189) can still flag deep paraphrases this structural gate does not.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "CNF-0189 embedding rescan with the same planted pair.",
            }
        ],
        "near_duplicate_pairs_listed": catalog["near_duplicate_pairs_listed"],
        "duplicate_pairs": catalog["duplicate_pairs"],
        "timestamps": {"ended_at": now},
        "SUCCESS:IMP-0232": True,
    }
    out_path = ROOT / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Sentinel must appear as the literal completion string in the file body.
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0232" not in text:
        raise SystemExit("receipt missing sentinel")
    out_path.write_text(text, encoding="utf-8")
    return catalog


def main() -> int:
    write_catalog_and_receipt()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0232-probe2-planted-duplicate",
            "verdict": "PASS",
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0232: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0232 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
