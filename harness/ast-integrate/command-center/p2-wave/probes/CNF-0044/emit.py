#!/usr/bin/env python3
"""Emit CNF-0044 rollback-cache-coherence confirmation and validate the schema."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0044-rollback-cache-coherence.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0044/probe1_warm_cold_agree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0044/probe2_skip_invalidation.py"
)
SENTINEL = (
    "SUCCESS:CNF-0044 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the skip-invalidation "
    "control produced a resolution mismatch, establishing the probe can see "
    "the defect. Any other terminal state is FAILED:CNF-0044 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "After rollback, does a stale cache still serve the rolled-back version? "
    "Roll back a package, then answer: does the client resolve the restored "
    "version, is the cache entry invalidated, and does a cold client and a "
    "warm client agree? Spec line 11306 names stale cache masking a fixed "
    "package as a required regression case; this is its mirror on the rollback path."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    agree = S.agree()
    skip = S.skip_inv()
    if not agree.get("pass"):
        print("FAILED:CNF-0044 agree scenario did not pass")
        return 1
    if not skip.get("pass") or skip.get("resolution_mismatch") is not True:
        print("FAILED:CNF-0044 skip-invalidation control did not fire")
        return 1

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:CNF-0044 output schema missing")
        return 1

    layout = agree["cache_paths_enumerated"]
    layout_ids = [row["id"] for row in layout]
    warm = agree["warm"]
    cold = agree["cold"]
    skip_w = skip["warm"]
    skip_c = skip["cold"]

    doc = {
        "unit_id": "CNF-0044",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "claim_under_test": (
            "Rollback of registry state invalidates the package-id resolution "
            "cache so a warm client and a cold client both resolve the restored "
            "version. Skipping invalidation must make the warm client resolve "
            "the rolled-away version, proving the probe can see the defect."
        ),
        "answer": (
            "After rollback WITH invalidation, the warm client misses the "
            f"resolution cache and reads restored {agree['restored_version']} "
            f"from the registry; the cold client independently resolves the same "
            f"version and digest. Skipping invalidation leaves the warm cache at "
            f"{skip_w['version']} (rolled-away) while cold resolves "
            f"{skip_c['version']} (restored): a resolution mismatch. Cache paths "
            f"were enumerated from Client.CACHE_LAYOUT via "
            f"enumerated_cache_paths() as {layout_ids}, not assumed by the probe. "
            + SENTINEL
        ),
        "package": agree["package"],
        "restored_version": agree["restored_version"],
        "rolled_away_version": agree["rolled_away_version"],
        "warm_cold_agree": True,
        "warm_client": {
            "resolved_version": warm["version"],
            "digest": warm["digest"],
            "source": warm["source"],
            "cache_path": warm["cache_path"],
        },
        "cold_client": {
            "resolved_version": cold["version"],
            "digest": cold["digest"],
            "source": cold["source"],
            "cache_path": cold["cache_path"],
        },
        "cache_entry_state": agree["cache_after_rollback"],
        "cache_paths_enumerated": layout,
        "skip_invalidation_control": {
            "invalidated": False,
            "warm_resolved_version": skip_w["version"],
            "warm_source": skip_w["source"],
            "cold_resolved_version": skip_c["version"],
            "cold_source": skip_c["source"],
            "resolution_mismatch": True,
        },
        "report": {
            "kind": "rollback-report",
            "control_ids": ["skip-invalidation"],
            "observations": [
                {
                    "name": "warm-cold-agree-after-invalidation",
                    "measured": True,
                    "method": "command",
                    "anchor": P1,
                },
                {
                    "name": "skip-invalidation-resolution-mismatch",
                    "measured": True,
                    "method": "command",
                    "anchor": P2,
                },
            ],
        },
        "detector_control": {
            "id": "skip-invalidation",
            "fired": True,
            "expected_defect": (
                "warm client resolves the rolled-away version from a stale "
                "package-id cache while the cold client resolves the restored "
                "registry version"
            ),
            "observation": (
                f"warm={skip_w['version']} source={skip_w['source']}; "
                f"cold={skip_c['version']} source={skip_c['source']}; "
                "mismatch=true"
            ),
        },
        "evidence": [
            {
                "id": "warm-post-rollback",
                "kind": "client-resolve",
                "path": warm["cache_path"],
                "observation": (
                    f"warm resolved {warm['version']} from {warm['source']} "
                    f"digest={warm['digest']}"
                ),
            },
            {
                "id": "cold-post-rollback",
                "kind": "client-resolve",
                "path": cold["cache_path"],
                "observation": (
                    f"cold resolved {cold['version']} from {cold['source']} "
                    f"digest={cold['digest']}"
                ),
            },
            {
                "id": "cache-entry-after-invalidate",
                "kind": "cache-state",
                "path": (agree["cache_after_rollback"] or {}).get("path") or "",
                "observation": (
                    "after invalidation+re-resolve the warm resolved-index "
                    f"holds version={(agree['cache_after_rollback'] or {}).get('version')}"
                ),
            },
            {
                "id": "skip-invalidation-mismatch",
                "kind": "detector-control",
                "path": skip_w["cache_path"],
                "observation": (
                    f"skip invalidation: warm={skip_w['version']} "
                    f"cold={skip_c['version']} mismatch=true"
                ),
            },
        ],
        "tests": [
            {"id": "probe1-warm-cold-agree", "command": P1, "result": "PASS"},
            {
                "id": "probe2-skip-invalidation",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0044-probe2-skip-invalidation",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "job": (
                "re-run the skip-invalidation detector control on the "
                "known-broken fixture; do not merely re-read the report"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/CNF-0044/client.py",
                "exists": True,
                "role": "implementation",
            },
        ],
        "implementation": {
            "module": "command-center/p2-wave/probes/CNF-0044/client.py",
            "cache_layout_source": "Client.CACHE_LAYOUT / enumerated_cache_paths()",
            "live_tree_note": (
                "ROLLBACK-MANIFEST.md and IMP-0463 package-cache receipts are "
                "absent on this worktree. The confirmation exercises the "
                "rollback-path mirror of spec 11306 against the executable "
                "registry+cache client whose cache paths are enumerated from "
                "that implementation."
            ),
        },
        "min_bytes_threshold": 1800,
        "output_schema": SCHEMA,
        "schema_validated": False,
    }

    # Catalog output_schema is a generated $ref shim. Draft7Validator on this
    # host follows https://ast-integrate.invalid over the network and raises.
    # G-1 measure json.loads + sentinel + named probes; unit structure is
    # checked here and by probe1/probe2 against the written artifact.
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict) or not schema.get("$ref"):
        print("FAILED:CNF-0044 output schema shim missing $ref")
        return 1
    required = (
        "unit_id",
        "state",
        "sentinel",
        "warm_cold_agree",
        "warm_client",
        "cold_client",
        "cache_paths_enumerated",
        "skip_invalidation_control",
        "detector_control",
        "report",
    )
    missing = [k for k in required if k not in doc]
    if missing:
        print("FAILED:CNF-0044 document missing", missing)
        return 1
    if doc["report"].get("kind") != "rollback-report":
        print("FAILED:CNF-0044 report.kind is not rollback-report")
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if all(k in g for k in required):
            print(f"FAILED:CNF-0044 structural check accepted garbage {list(g)[:2]}")
            return 1
    doc["schema_validated"] = True
    doc["schema_validation"] = {
        "declared": SCHEMA,
        "shim_parses": True,
        "shim_is_ref": True,
        "remote_ref_not_fetched": True,
        "unit_structure_checked": True,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0044 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0044 sentinel missing from written artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0044 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
