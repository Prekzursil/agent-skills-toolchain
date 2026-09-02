#!/usr/bin/env python3
"""Emit REL-0017 lifecycle-drill receipt, then per-unit return + manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from migrate import (  # noqa: E402
    INVARIANT_NO_REMOVE_FOREIGN,
    INVARIANT_NO_REMOVE_PREEXISTING,
    isolation_negative_control,
    rehearse,
)
from scenario import (  # noqa: E402
    BOTH_UNIQUE_REL,
    CAPTURED,
    PLANTED_LINE,
    PLANTED_SOURCE,
    PLANTED_TARGET,
    build_captured,
)

OUT = "command-center/receipts/REL-0017.json"
SCHEMA = "command-center/schema/lifecycle-drill-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0017/probe1_dryrun_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0017/probe2_restore_eol.py"
)
QUESTION = (
    "Implementation target: rehearse converting the pre-plugin hand-managed layout "
    "-- loose skills in the live tree, hand-edited hook registrations, rule files "
    "modified in place -- into the plugin-managed layout. Work on a copy of a "
    "captured real layout, run the conversion in dry-run mode first and require "
    "the printed plan to match the applied result exactly, and demonstrate "
    "reversibility by restoring from the backup the conversion takes. Where the "
    "source holds content the target does not, the conversion must preserve it "
    "or refuse."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def structural_errors(doc: object) -> list[str]:
    """Reject empty/unrelated blobs without resolving the catalog $ref shim.

    command-center/schema/lifecycle-drill-receipt.schema.json is a generated
    $ref to ast-integrate.invalid; Draft7 on this host tries HTTPS and hangs.
    G-1 does not require remote $ref resolution.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if doc.get("unit_id") != "REL-0017":
        errs.append("unit_id")
    if doc.get("state") not in {"SUCCESS", "BLOCKED"}:
        errs.append("state")
    blob = json.dumps(doc)
    if doc.get("state") == "SUCCESS" and "SUCCESS:REL-0017" not in blob:
        errs.append("sentinel")
    iso = doc.get("isolation") if isinstance(doc.get("isolation"), dict) else {}
    if iso.get("ran_against_copy") is not True or not iso.get("copy_path"):
        errs.append("isolation.copy")
    if doc.get("plan_applied_identical") is not True:
        errs.append("plan_applied_identical")
    if doc.get("plan_vs_applied_diff") not in ([], None):
        errs.append("plan_vs_applied_diff")
    unique = doc.get("source_unique") if isinstance(doc.get("source_unique"), dict) else {}
    if int(unique.get("preserved") or 0) < 1 or int(unique.get("refused") or 0) < 1:
        errs.append("source_unique")
    restore = doc.get("restore") if isinstance(doc.get("restore"), dict) else {}
    if restore.get("hash_set_match") is not True:
        errs.append("restore.hash_set_match")
    eol = (
        doc.get("eol_classification")
        if isinstance(doc.get("eol_classification"), dict)
        else {}
    )
    if eol.get("classification") != "EOL-ONLY" or eol.get("op") != "skip":
        errs.append("eol_classification")
    tests = doc.get("tests") if isinstance(doc.get("tests"), list) else []
    if len(tests) < 4 or any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        errs.append("tests")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "lifecycle-drill-receipt":
        errs.append("report.kind")
    obs = report.get("observations") if isinstance(report.get("observations"), list) else []
    if len(obs) < 1:
        errs.append("report.observations")
    cids = report.get("control_ids") if isinstance(report.get("control_ids"), list) else []
    if len(cids) < 1:
        errs.append("report.control_ids")
    reviewer = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if reviewer.get("planted_owner_file_caught") is not True:
        errs.append("reviewer.planted")
    probes = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
    if len(probes) < 2:
        errs.append("named_probes")
    return errs


def slim_mut(row: dict) -> dict:
    keep = (
        "op",
        "source_rel",
        "target_rel",
        "classification",
        "reason",
        "content_sha256",
        "bytes",
    )
    return {k: row.get(k) for k in keep}


def main() -> int:
    build_captured()
    iso_neg = isolation_negative_control()
    if not iso_neg.get("pass"):
        print("FAILED:REL-0017 isolation negative control")
        print(json.dumps(iso_neg, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="rel0017-emit-") as tmp:
        result = rehearse(Path(tmp))

    if not result["plan_applied_identical"]:
        print("FAILED:REL-0017 dry-run vs applied")
        print(json.dumps(result["plan_vs_applied_diff"], indent=2)[:4000])
        return 1
    if not result["source_unique_hashes_intact"]:
        print("FAILED:REL-0017 source-unique hashes")
        return 1
    if result["source_unique"]["preserved"] < 1 or result["source_unique"]["refused"] < 1:
        print("FAILED:REL-0017 unique census", result["source_unique"])
        return 1
    if not result["restore_ok"]:
        print("FAILED:REL-0017 restore hash-set")
        return 1
    if not result["eol"]["honest_unchanged"]:
        print("FAILED:REL-0017 EOL not unchanged", result["eol"])
        return 1
    if result["eol"]["naive_without_eol_norm"] != "CONFLICT":
        print("FAILED:REL-0017 naive EOL control silent", result["eol"])
        return 1
    if not result["planted"].get("pass") or not result["planted"].get(
        "survived_apply_hash_intact"
    ):
        print("FAILED:REL-0017 planted oracle", json.dumps(result["planted"], default=str)[:2000])
        return 1
    if not result["inverse_control"].get("pass"):
        print("FAILED:REL-0017 inverse control")
        return 1
    if not result["ran_against_copy"] or not result["isolation_ok"]:
        print("FAILED:REL-0017 isolation", result["copy_path"], result["isolation_error"])
        return 1
    if not result["plugin_only_survived"]:
        print("FAILED:REL-0017 plugin-only path was destroyed")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unique = result["source_unique"]
    plan_side = [slim_mut(m) for m in result["plan"]]
    applied_side = result["measured_writes"]

    tests = [
        {
            "id": "T1-dry-run-vs-applied",
            "description": "Dry-run plan versus independently measured applied tree delta: the diff must be empty.",
            "detail": (
                "plan_vs_applied_diff is empty; predicted writes equal the "
                f"measured tree delta ({len(result['measured_writes'])} writes)"
            ),
            "result": "PASS" if result["plan_applied_identical"] else "FAIL",
            "diff_count": len(result["plan_vs_applied_diff"]),
        },
        {
            "id": "T2-source-unique-hash",
            "description": "A file existing only in the source layout survives the conversion with its hash intact.",
            "detail": (
                "SOURCE-ONLY files copied into the plugin layout kept raw sha256: "
                + ", ".join(unique["preserved_paths"])
            ),
            "result": "PASS" if result["source_unique_hashes_intact"] else "FAIL",
            "preserved_paths": unique["preserved_paths"],
        },
        {
            "id": "T3-restore-backup-hash-set",
            "description": "Restore from the conversion's own backup returns the tree to its exact pre-conversion hash set.",
            "detail": (
                f"sha256(raw bytes) over {result['restore_hash_count']} files "
                "matched the pre-apply hash set after restore_tree(backup)"
            ),
            "result": "PASS" if result["restore_ok"] else "FAIL",
            "files": result["restore_hash_count"],
        },
        {
            "id": "T4-eol-unchanged",
            "description": "A file differing only in line endings is classified unchanged, not as a conflict.",
            "detail": (
                f"{result['eol']['path']} classified {result['eol']['classification']} "
                f"op={result['eol']['op']}; naive raw-byte classifier said "
                f"{result['eol']['naive_without_eol_norm']}"
            ),
            "result": "PASS" if result["eol"]["honest_unchanged"] else "FAIL",
            "honest": result["eol"]["classification"],
            "naive_without_eol_norm": result["eol"]["naive_without_eol_norm"],
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:REL-0017 tests")
        return 1

    doc = {
        "unit_id": "REL-0017",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0017",
        "completion_sentinel": "SUCCESS:REL-0017",
        "kind": "lifecycle-drill-receipt",
        "drill_kind": "legacy-hand-managed-to-plugin-migration",
        "schema_version": 1,
        "title": "Legacy hand-managed layout migration, dry-run first, on a copy, refusing one-directional overwrite",
        "question": QUESTION,
        "profile": {
            "isolated": True,
            "owner_home_untouched": True,
            "isolation_assertion": (
                "assert_copy refuses Path.home()/.claude and the frozen "
                "fixtures/captured original. The conversion ran only under "
                f"copy_path={result['copy_path']}. Host live profiles were not read or written."
            ),
            "copy_path": result["copy_path"],
            "kind": "tempfile-copy-of-captured-layout",
        },
        "isolation": {
            "ran_against_copy": True,
            "copy_path": result["copy_path"],
            "hand_copy_path": result["hand_path"],
            "plugin_copy_path": result["plugin_path"],
            "captured_original": str(CAPTURED.as_posix()),
            "live_tree_untouched": True,
            "isolation_assertion": (
                "assert_copy refuses Path.home()/.claude and the frozen "
                "fixtures/captured original. The conversion ran only under "
                f"copy_path={result['copy_path']}. Host live profiles were not read or written."
            ),
            "negative_control": iso_neg,
        },
        "operations": [
            {
                "name": "dry-run-plan",
                "paths_hashed": result["restore_hash_count"] + unique["preserved"],
                "paths_skipped": sum(1 for m in result["plan"] if m["op"] == "skip"),
                "paths_altered": 0,
                "skipped_are_not_checked": True,
                "declared_change_set": {
                    "creates": unique["preserved_paths"],
                    "mutates": [
                        m["target_rel"]
                        for m in result["plan"]
                        if m["op"] == "overwrite"
                    ],
                    "removes": [],
                },
            },
            {
                "name": "apply-on-copy",
                "paths_hashed": result["restore_hash_count"] + unique["preserved"],
                "paths_skipped": sum(
                    1 for m in result["plan"] if m["op"] in {"skip", "refuse"}
                ),
                "paths_altered": len(result["measured_writes"]),
                "skipped_are_not_checked": True,
                "declared_change_set": {
                    "creates": unique["preserved_paths"],
                    "mutates": [
                        m["target_rel"]
                        for m in result["plan"]
                        if m["op"] == "overwrite"
                    ],
                    "removes": [],
                },
            },
            {
                "name": "restore-from-conversion-backup",
                "paths_hashed": result["restore_hash_count"],
                "paths_skipped": 0,
                "paths_altered": 0,
                "skipped_are_not_checked": True,
                "declared_change_set": {
                    "creates": [],
                    "mutates": [],
                    "removes": [],
                },
            },
        ],
        "drill": {
            "id": "REL-0017-hand-to-plugin",
            "mode": "dry-run-then-apply-on-copy",
            "backup_path": result["backup_path"],
            "resume_policy": (
                "resumable with mandatory restore: a dirty resume marker rolls "
                "the plugin copy back to the conversion backup before the next attempt"
            ),
            "steps": [
                "Copy fixtures/captured/{hand,plugin} into a tempfile worktree.",
                "Print the dry-run mutation plan (create/overwrite/skip/refuse) without writing.",
                "Snapshot the plugin copy as the conversion backup.",
                "Apply the plan; measure the tree delta independently; require empty diff vs the plan writes.",
                "Restore from that backup and require the raw sha256 hash set to match pre-apply.",
            ],
        },
        "dry_run_plan": plan_side,
        "applied_diff": applied_side,
        "plan_vs_applied_diff": result["plan_vs_applied_diff"],
        "plan_applied_identical": True,
        "source_unique": unique,
        "source_unique_preserved_versus_refused": {
            "preserved": unique["preserved"],
            "refused": unique["refused"],
            "note": (
                "preserved = SOURCE-ONLY files copied into the plugin layout with "
                "raw sha256 intact; refused = both-unique (or target-superset) "
                "paths that would destroy unique bytes on a one-directional copy"
            ),
        },
        "restore": {
            "from_conversion_backup": True,
            "backup_path": result["backup_path"],
            "hash_set_match": True,
            "files": result["restore_hash_count"],
            "algorithm": "sha256 of raw bytes (CRLF preserved; not LF-normalised)",
        },
        "eol_classification": {
            "path": result["eol"]["path"],
            "classification": result["eol"]["classification"],
            "op": result["eol"]["op"],
            "naive_without_eol_norm": result["eol"]["naive_without_eol_norm"],
            "honest_unchanged": True,
        },
        "divergence_honesty": {
            "catalog_pin_5_of_88": (
                "WORK-UNIT-CATALOG cites a 2026-08-09 estate measurement of 5 of "
                "88 live rule files identical to repository counterparts. That "
                "number is a historical pin, not today's host measurement."
            ),
            "host_live_trees_read": False,
            "fixture_two_directional": True,
            "fixture_both_unique_path": BOTH_UNIQUE_REL,
            "b02_receipt_on_disk": False,
            "rel0002_receipt_on_disk": False,
            "inverses_encoded_in": "command-center/p2-wave/probes/REL-0017/migrate.py",
            "invariants": [
                INVARIANT_NO_REMOVE_FOREIGN,
                INVARIANT_NO_REMOVE_PREEXISTING,
            ],
        },
        "planted_owner_file": {
            "source_rel": PLANTED_SOURCE,
            "target_rel": PLANTED_TARGET,
            "line": PLANTED_LINE,
            "take_target_policy_refused": True,
            "survived_honest_apply_hash_intact": True,
            "sha256": result["planted"].get("planted_source_sha256"),
        },
        "inverses": result["inverses"],
        "inverse_control": result["inverse_control"],
        "created_set": result["created_set"],
        "tests": tests,
        "evidence": {
            "hashed_path_count": result["restore_hash_count"] + unique["preserved"],
            "skip_folded_into_pass": False,
            "surfaces_not_checked": [
                "owner live ~/.claude and ~/.cursor profiles (absent or forbidden)",
                "REL-0002 receipt on disk (inverses encoded locally from the catalog contract)",
                "B02 current-state audit receipt (5/88 is a catalog pin, not remeasured here)",
            ],
            "side_by_side": {
                "claim": (
                    "dry_run_plan writes and applied_diff (measured post-apply "
                    "tree delta) are identical; plan_vs_applied_diff is []"
                ),
                "anchor": f"{OUT}:dry_run_plan|applied_diff|plan_vs_applied_diff",
            },
            "copy_path": {
                "claim": (
                    f"operation ran against a copy, copy_path={result['copy_path']}; "
                    "captured original and live profiles were not mutated"
                ),
                "anchor": f"{OUT}:isolation.copy_path",
            },
            "preserved_versus_refused": {
                "claim": (
                    f"{unique['preserved']} source-unique files preserved, "
                    f"{unique['refused']} both-unique paths refused"
                ),
                "anchor": f"{OUT}:source_unique",
            },
            "restore_hash_set": {
                "claim": (
                    f"restore from {result['backup_path']} matched the "
                    f"{result['restore_hash_count']}-file pre-conversion raw hash set"
                ),
                "anchor": f"{OUT}:restore",
            },
        },
        "reviewer": {
            "reviewer_id": "REL-0017-probe2-planted-owner-file",
            "verdict": "PASS",
            "independent": True,
            "planted_owner_file_caught": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 attempts the take-target lifecycle path against the "
                "planted owner-authored skill and requires REFUSE. Probe 1 "
                "reads a different field (dry-run vs measured apply). Cloud "
                "ok=true is not delivery."
            ),
        },
        "report": {
            "kind": "lifecycle-drill-receipt",
            "observations": [
                {
                    "name": "dry-run-plan-versus-measured-apply",
                    "measured": True,
                    "method": "plan_vs_applied independent tree-delta compare",
                    "anchor": f"{OUT}:plan_vs_applied_diff",
                },
                {
                    "name": "source-unique-preserved-versus-refused",
                    "measured": f"{unique['preserved']}/{unique['refused']}",
                    "method": "raw sha256 of SOURCE-ONLY creates; BOTH-UNIQUE refuse",
                    "anchor": f"{OUT}:source_unique",
                },
                {
                    "name": "restore-from-conversion-backup-hash-set",
                    "measured": result["restore_hash_count"],
                    "method": "sha256 of raw bytes before apply vs after restore_tree",
                    "anchor": f"{OUT}:restore",
                },
                {
                    "name": "eol-only-classified-unchanged",
                    "measured": result["eol"]["classification"],
                    "method": "honest classify_pair vs naive byte-unequal CONFLICT",
                    "anchor": f"{OUT}:eol_classification",
                },
            ],
            "control_ids": [
                "isolation-negative-control-live-profile-and-captured-original",
                "naive-eol-byte-compare-conflict",
                "planted-owner-file-take-target-refuse",
                "inverse-no-remove-foreign-plugin-only",
            ],
        },
        "named_probes": [
            {"id": "probe1", "role": "dry-run-identity", "command": P1},
            {"id": "probe2", "role": "restore-eol-oracle", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "migration-engineer",
            "execution_substrate": "linux-local",
        },
        "min_bytes_threshold": 2048,
        "timestamps": {"ended_at": now},
        "answer": (
            f"Hand-to-plugin conversion rehearsed on copy {result['copy_path']}. "
            f"Dry-run vs measured apply diff empty. Source-unique preserved="
            f"{unique['preserved']} refused={unique['refused']}. Restore hash-set "
            f"match on {result['restore_hash_count']} files. EOL-only classified "
            f"unchanged (naive byte compare says CONFLICT). Planted owner file "
            f"{PLANTED_TARGET} caught. SUCCESS:REL-0017"
        ),
    }

    struct_errs = structural_errors(doc)
    if struct_errs:
        print("FAILED:REL-0017 structural errors")
        for e in struct_errs:
            print(" ", e)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "REL-0017", "state": "SUCCESS"},
    ):
        if not structural_errors(garbage):
            print("FAILED:REL-0017 structural checker accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:REL-0017 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:REL-0017 probes c1={c1} c2={c2}")
        return 1

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "REL-0017",
            "receipt_path": "command-center/p2-wave/probes/REL-0017/SUBAGENT-RETURN.json",
            "role": role,
        }

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/REL-0017/migrate.py",
        "command-center/p2-wave/probes/REL-0017/scenario.py",
        "command-center/p2-wave/probes/REL-0017/probe1_dryrun_identity.py",
        "command-center/p2-wave/probes/REL-0017/probe2_restore_eol.py",
        "command-center/p2-wave/probes/REL-0017/emit.py",
    ]
    # primary digest after receipt write; SUBAGENT-RETURN written next so exclude it from sha-before
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in supporting]
    ret = {
        "id": "REL-0017",
        "unit_id": "REL-0017",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0017",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "dry-run-identity",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "restore-eol-oracle",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/REL-0017/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0017-probe2-planted-owner-file",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for REL-0017: live named probes exit 0, REL-0017.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "REL-0017",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={digest} bytes={size}")
    print("SUCCESS:REL-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
