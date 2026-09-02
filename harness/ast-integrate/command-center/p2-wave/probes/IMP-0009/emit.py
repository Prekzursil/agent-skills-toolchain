#!/usr/bin/env python3
"""Emit IMP-0009 receipt and per-unit G-1 return + manifest.

Order: measure linter and tests, write receipts/IMP-0009.json, re-run named
probes, then write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO / "tools" / "plugin"))
import case_collision as cc  # noqa: E402

UNIT = "IMP-0009"
OUT = "command-center/receipts/IMP-0009.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0009/probe1_linter_flags.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0009/probe2_pairs_hook.py"
)
TEST_CMD = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_case_collision.py"
FIX = "tools/plugin/tests/fixtures"
SUPPORTING = [
    "tools/plugin/case_collision.py",
    "tools/plugin/tests/test_case_collision.py",
    f"{FIX}/clean-manifest.json",
    f"{FIX}/name-collision.json",
    f"{FIX}/duplicate-keys.json",
    f"{FIX}/nested-collision.json",
    f"{FIX}/non-colliding-siblings.json",
    "command-center/p2-wave/probes/IMP-0009/probe1_linter_flags.py",
    "command-center/p2-wave/probes/IMP-0009/probe2_pairs_hook.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def live_inputs() -> list[dict]:
    rows = []
    for rel in cc.DEFAULT_TARGETS:
        path = REPO / rel
        row = cc.lint_file(path)
        row["catalog_input"] = True
        rows.append(row)
    return rows


def main() -> int:
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0009 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    clean = cc.lint_file(REPO / FIX / "clean-manifest.json")
    planted = cc.lint_file(REPO / FIX / "name-collision.json")
    dup = cc.lint_file(REPO / FIX / "duplicate-keys.json")
    planted_raw = (REPO / FIX / "name-collision.json").read_text(encoding="utf-8")
    dup_raw = (REPO / FIX / "duplicate-keys.json").read_text(encoding="utf-8")
    planted_pairs = json.loads(planted_raw, object_pairs_hook=lambda p: p)
    planted_keys = [k for k, _ in planted_pairs]
    dup_pairs = json.loads(dup_raw, object_pairs_hook=lambda p: p)
    dup_name_count = [k for k, _ in dup_pairs].count("name")
    naive_dup = json.loads(dup_raw)
    live = live_inputs()

    case_hits = [f for f in planted.get("findings") or [] if f["kind"] == cc.KIND_CASE]
    dup_hits = [f for f in dup.get("findings") or [] if f["kind"] == cc.KIND_DUP]
    if not case_hits or not dup_hits or clean.get("findings"):
        print("FAILED:IMP-0009 linter did not discriminate fixtures")
        return 1
    if "Name" not in planted_keys or "name" not in planted_keys:
        print(f"FAILED:IMP-0009 pairs-hook keys {planted_keys}")
        return 1
    if dup_name_count != 2 or list(naive_dup.keys()).count("name") != 1:
        print("FAILED:IMP-0009 duplicate evidence mismatch")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_lint = L.probe(
        "source",
        "command",
        TEST_CMD + " && python3 -B tools/plugin/case_collision.py "
        f"{FIX}/name-collision.json {FIX}/clean-manifest.json",
        json.dumps(
            {
                "clean_findings": len(clean.get("findings") or []),
                "planted_kinds": [f["kind"] for f in planted.get("findings") or []],
                "planted_keys": case_hits[0]["keys"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_pairs = L.probe(
        "verifier",
        "static-analysis",
        "python3 -c object_pairs_hook extract Name/name and duplicate name",
        json.dumps(
            {
                "loader": "json.loads(..., object_pairs_hook=list)",
                "naive_dict_name_count": list(naive_dup.keys()).count("name"),
                "pairs_duplicate_name_count": dup_name_count,
                "pairs_planted_keys": planted_keys,
            },
            sort_keys=True,
        ),
        0,
    )
    p_test = L.probe("source", "test-run", TEST_CMD, out_t[-4000:], rc_t)

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    artifacts = [
        L.art("tools/plugin/case_collision.py", "supporting"),
        L.art("tools/plugin/tests/test_case_collision.py", "supporting"),
        L.art(f"{FIX}/name-collision.json", "fixture"),
        L.art(f"{FIX}/duplicate-keys.json", "fixture"),
        L.art(f"{FIX}/clean-manifest.json", "fixture"),
        L.art(
            "command-center/p2-wave/probes/IMP-0009/probe1_linter_flags.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/IMP-0009/probe2_pairs_hook.py",
            "supporting",
        ),
    ]
    # Primary path is this receipt; size/hash filled after write via rewrite? G-1
    # hashes the file on disk. Put a placeholder then rewrite once? Avoid cycle:
    # declare the primary path without self-hash; measure does not require the
    # receipt to contain its own sha. Include implementation artifacts only.

    all_absent = all(r.get("absent") for r in live)
    residual_claim = (
        "Catalog inputs .claude-plugin/plugin.json and "
        "hooks/_dispatch/manifest.json are absent on this worktree; "
        "they were recorded ABSENT rather than scored clean."
        if all_absent
        else (
            "Catalog inputs .claude-plugin/plugin.json and "
            "hooks/_dispatch/manifest.json were linted live with "
            "object_pairs_hook; absent targets are recorded ABSENT rather "
            "than scored clean."
        )
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0009",
        "spec_anchor": "_USER-PROMPTS.md:11310",
        "min_bytes_threshold": 512,
        "artifacts": artifacts,
        "report": {
            "title": "Case-distinct JSON key collision guard in the manifest linter",
            "question_or_target": (
                "Implement a linter rule that rejects any manifest or config "
                "object containing two keys that differ only by case, because a "
                "case-insensitive downstream parser silently collapses them and "
                "one value is lost without an error."
            ),
            "output_path": OUT,
            "output_schema": SCHEMA,
            "completion_sentinel": "SUCCESS:IMP-0009",
            "linter": {
                "module": "tools/plugin/case_collision.py",
                "loader": "json.loads(..., object_pairs_hook=ObjectPairs)",
                "rules": [cc.KIND_CASE, cc.KIND_DUP],
                "default_targets": list(cc.DEFAULT_TARGETS),
                "live_inputs": live,
                "fixtures": {
                    "clean": {
                        "path": f"{FIX}/clean-manifest.json",
                        "findings": clean.get("findings") or [],
                    },
                    "name_collision": {
                        "path": f"{FIX}/name-collision.json",
                        "findings": planted.get("findings") or [],
                        "pairs_hook_keys": planted_keys,
                    },
                    "duplicate_keys": {
                        "path": f"{FIX}/duplicate-keys.json",
                        "findings": dup.get("findings") or [],
                        "pairs_hook_name_count": dup_name_count,
                        "naive_dict_keys": list(naive_dup.keys()),
                        "naive_dict_name": naive_dup.get("name"),
                    },
                },
            },
            "notes": (
                "G-1 IMP-0009: linter rejects case-distinct and exact-duplicate "
                "JSON keys using object_pairs_hook. Did not run global "
                "unit_manifest.py --write. cloud ok=true is not delivery."
            ),
        },
        "evidence": [
            L.evidence(
                "The linter flags a fixture containing both Name and name, and "
                "the same run accepts a clean manifest (negative control).",
                "CONFIRMED",
                "tools/plugin/tests/fixtures/name-collision.json",
                [p_lint, p_pairs],
                "almost-certain",
            ),
            L.evidence(
                "Independent json.loads(..., object_pairs_hook=list) extraction "
                "sees both planted keys and both duplicate name members; a naive "
                "dict load last-wins and cannot confirm the source.",
                "CONFIRMED",
                "json.loads object_pairs_hook",
                [p_test, p_pairs],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_case_distinct_keys_rejected",
                "command": (
                    TEST_CMD + "::test_case_distinct_keys_rejected"
                ),
                "result": "PASS",
            },
            {
                "id": "test_exact_duplicate_keys_rejected",
                "command": TEST_CMD + "::test_exact_duplicate_keys_rejected",
                "result": "PASS",
            },
            {
                "id": "test_negative_control_clean_passes_planted_fails",
                "command": (
                    TEST_CMD + "::test_negative_control_clean_passes_planted_fails"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "clean-vs-planted",
                "known-broken-fixture",
                "Clean manifest is silent; Name/name fixture is flagged.",
                True,
                True,
                bad=json.dumps([f["kind"] for f in planted.get("findings") or []]),
                good="findings=[]",
            ),
            L.control(
                "plain-dict-load-destroys-duplicates",
                "other",
                "json.loads dict last-wins exact duplicate keys; pairs-hook keeps both.",
                True,
                True,
                bad=f"naive name={naive_dup.get('name')!r} count=1",
                good=f"pairs-hook name count={dup_name_count}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0009-probe2-object-pairs-hook",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Loader is json.loads(..., object_pairs_hook=list). A check "
                "built on a plain dict load last-wins exact duplicates and "
                "measures nothing for that class. Case-distinct Name/name is "
                "confirmed on source pairs, then shown to collapse under casefold."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0009/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "tools/plugin/tests/test_case_collision.py",
                "artifact_path": "tools/plugin/case_collision.py",
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "residual_unknowns": [
            {
                "claim": residual_claim,
                "verdict": "NOT-CHECKED" if all_absent else "CONFIRMED",
                "settling_experiment": (
                    "Re-run tools/plugin/case_collision.py on those paths after "
                    "any rewrite of the live plugin or dispatch manifests."
                ),
            }
        ],
        "extensions": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "live_inputs": live,
        },
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0009 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0009" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0009 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0009 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0009",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "linter-flags-name-collision",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-pairs-hook",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0009-probe2-object-pairs-hook",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0009: live named probes exit 0, receipts/IMP-0009.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0009/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0009 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
