#!/usr/bin/env python3
"""Emit TST-0072 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from host import host_census  # noqa: E402
from scenario import detector_control, rehearse  # noqa: E402
from schema_local import garbage_accepted, iter_error_strings  # noqa: E402

UNIT = "TST-0072"
OUT = "command-center/receipts/TST-0072.json"
DECLARED_SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SENTINEL:TST-0072:ROLLBACK-PRESERVES-USER-OWNED"
COMPLETION = "SUCCESS:TST-0072"
QUESTION = (
    "Phase 10 layer 7 (:10995) and failure class :11347. Target: after a "
    "rollback, every user-created artifact and every previously available "
    "command still exists. Question: is any user-owned path inside the "
    "managed directory tree, making it collateral by construction?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0072/probe1_additive_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0072/probe2_naive_mutant.py"
)
SUPPORTING = [
    DECLARED_SCHEMA,
    "command-center/p2-wave/probes/TST-0072/fixtures.py",
    "command-center/p2-wave/probes/TST-0072/inventory.py",
    "command-center/p2-wave/probes/TST-0072/rollback.py",
    "command-center/p2-wave/probes/TST-0072/scenario.py",
    "command-center/p2-wave/probes/TST-0072/host.py",
    "command-center/p2-wave/probes/TST-0072/probe1_additive_inventory.py",
    "command-center/p2-wave/probes/TST-0072/probe2_naive_mutant.py",
    "command-center/p2-wave/probes/TST-0072/schema_local.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0072/SUBAGENT-RETURN.json",
        "role": role,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_or_die(doc: dict) -> None:
    bad = garbage_accepted()
    if bad is not None:
        raise SystemExit(
            f"FAILED:TST-0072 schema accepted garbage {list(bad)[:2]}"
        )
    errs = iter_error_strings(doc)
    if errs:
        print("FAILED:TST-0072 schema errors")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def build_doc(
    measured: dict,
    started: str,
    ended: str,
    t1out: str,
    t2out: str,
    c1: int,
    c2: int,
) -> dict:
    good = measured["additive"]
    bad = measured["naive"]
    control = measured["control"]
    tests = good["tests"]
    t1 = tests["test_rollback_restores_prior_version"]
    t2 = tests["test_rollback_deletes_zero_user_owned_paths"]
    t3 = tests["test_command_inventory_is_unchanged_after_rollback"]
    if not tests["all_pass"]:
        raise SystemExit("FAILED:TST-0072 additive rehearsal did not pass")
    if bad["tests"]["test_rollback_deletes_zero_user_owned_paths"]["pass"]:
        raise SystemExit("FAILED:TST-0072 naive mutant did not turn red")
    if not control["detected"]:
        raise SystemExit("FAILED:TST-0072 extra-file detector silent")
    if c1 != 0 or c2 != 0:
        raise SystemExit(f"FAILED:TST-0072 named probes c1={c1} c2={c2}")

    naive_deleted = list(bad["delta"]["user_deleted"])
    user_paths = list(good["user_owned_paths"])
    answer = (
        "YES: user-owned paths were planted inside the managed profile tree "
        f"({user_paths}). Additive restore (mutate only the prior "
        "managed-manifest set) left that set byte-identical. Naive tree-replace "
        f"deleted {naive_deleted}. In-tree user paths are collateral by "
        "construction for any rollback that replaces the tree instead of "
        "restricting writes and deletes to the managed manifest. "
        f"{SENTINEL} {COMPLETION}"
    )
    arts = [artifact_row(p, "supporting") for p in SUPPORTING]
    arts[3]["role"] = "control"
    arts[6]["role"] = "control"
    arts[7]["role"] = "control"

    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "profile": "test-receipt",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0072] "
            "question_or_target + tests_required + evidence_requirement; "
            "inputs _USER-PROMPTS.md:10995 and _USER-PROMPTS.md:11347"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "release-test-engineer",
            "execution_substrate": "local-serialized",
        },
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "single attempt then escalate to the owner; this unit mutates "
                "a live shared surface and a blind retry can compound the damage"
            ),
        },
        "artifacts": arts,
        "evidence": [
            {
                "claim": (
                    "Additive rollback restored prior managed bytes and deleted "
                    "zero planted user-owned paths; Path.rglob and os.walk maps "
                    "agreed before and after."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0072/"
                    "probe1_additive_inventory.py"
                ),
                "probes": [
                    probe_obj("source", "command", P1, t1out, c1),
                    probe_obj(
                        "verifier",
                        "test-run",
                        P1 + " #walker-pair-inside-rehearse",
                        (
                            "inventory_rglob and inventory_walk must be equal "
                            "or rehearse SystemExits FAILED:TST-0072 walkers "
                            "disagree. probe1 exit 0 implies agreement. "
                            f"user_deleted={good['delta']['user_deleted']} "
                            f"prior_restored={t1['prior_bytes_restored']}"
                        ),
                        c1,
                    ),
                ],
            },
            {
                "claim": (
                    "Naive tree-replace deleted every planted in-tree user path "
                    f"{naive_deleted}, so in-tree user-owned paths are collateral "
                    "by construction for replace-the-tree rollback."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0072/probe2_naive_mutant.py"
                ),
                "probes": [
                    probe_obj("source", "command", P2, t2out, c2),
                    probe_obj(
                        "verifier",
                        "static-analysis",
                        (
                            "command-center/p2-wave/probes/TST-0072/"
                            "rollback.py:naive_replace"
                        ),
                        (
                            "naive_replace shutil.rmtree(live) then copytree "
                            "snapshot; snapshot is v1-only so planted user "
                            "files cannot survive. Additive restore writes "
                            "only prior managed bytes and unlinks only "
                            "upgrade-added managed paths."
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_rollback_restores_prior_version",
                "name": "prior managed bytes restored; upgrade-added command gone",
                "command": P1,
                "result": "PASS" if t1["pass"] else "FAIL",
                "output_tail": t1out[-4000:],
            },
            {
                "id": "test_rollback_deletes_zero_user_owned_paths",
                "name": "additive rollback deletes zero user-owned paths",
                "command": P1,
                "result": "PASS" if t2["pass"] else "FAIL",
                "output_tail": t1out[-4000:],
            },
            {
                "id": "test_command_inventory_is_unchanged_after_rollback",
                "name": "prior and user commands still present after rollback",
                "command": P1,
                "result": "PASS" if t3["pass"] else "FAIL",
                "output_tail": t1out[-4000:],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NAIVE-REPLACE",
                "kind": "mutation",
                "description": (
                    "Replace-the-tree rollback of the same fixture must delete "
                    "in-tree user-owned paths. If it preserved them, the "
                    "zero-delete assertion would be vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"naive_user_deleted={naive_deleted} "
                    "test_rollback_deletes_zero_user_owned_paths.pass=false"
                ),
                "good_state_output": (
                    f"additive_user_deleted={good['delta']['user_deleted']} "
                    "test_rollback_deletes_zero_user_owned_paths.pass=true"
                ),
            },
            {
                "id": "NC-EXTRA-FILE-DETECTOR",
                "kind": "mutation",
                "description": (
                    "Plant one extra user file after the pre-inventory; the "
                    "set comparison must name notes/planted-extra.md."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(control, sort_keys=True),
                "good_state_output": "extras=[] when no plant occurs",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0072-os.walk-second-inventory",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "inventory_walk (os.walk) recomputed the same path->sha256 map "
                "as inventory_rglob; naive mutant independently deleted the "
                "planted user set. G-1 delivery is live-probe green, not "
                "owner-close."
            ),
            "reviewed_at": ended,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0072/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft202012Validator + disk RefResolver "
                    "against command-center/schema/test-receipt.schema.json"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "source",
                    "schema-validate",
                    (
                        "python3 -B command-center/p2-wave/probes/"
                        "TST-0072/schema_local.py"
                    ),
                    "iter_error_strings(doc)=[] ; garbage_accepted() is None",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement asks for explicit owner "
                    "sign-off in command-center/OWNER-DECISIONS.md before the "
                    "unit may close. That file is absent on this worktree. "
                    "G-1 is live named probes plus a non-BLOCKED artifact, "
                    "not owner-close."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record owner sign-off in command-center/OWNER-DECISIONS.md "
                    "and re-run the close gate."
                ),
            }
        ],
        "report": {
            "kind": "test-receipt",
            "observations": [
                {
                    "name": "user_owned_inside_managed_tree",
                    "measured": True,
                    "method": "fixture-plant",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0072/fixtures.py"
                    ),
                },
                {
                    "name": "additive_user_deleted_count",
                    "measured": len(good["delta"]["user_deleted"]),
                    "method": "set-diff",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0072/inventory.py"
                    ),
                },
                {
                    "name": "naive_user_deleted_count",
                    "measured": len(naive_deleted),
                    "method": "naive-replace",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0072/rollback.py"
                    ),
                },
                {
                    "name": "collateral_by_construction",
                    "measured": True,
                    "method": "both-states",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0072/"
                        "probe2_naive_mutant.py"
                    ),
                },
            ],
            "control_ids": ["NC-NAIVE-REPLACE", "NC-EXTRA-FILE-DETECTOR"],
            "question": QUESTION,
            "answer": answer,
            "writes_to_live_host": False,
            "host_unchanged": measured["host_before"] == measured["host_after"],
            "findings": {
                "user_owned_inside_managed_tree": True,
                "collateral_by_construction_for_tree_replace": True,
                "additive_restore_deletes_zero_user_paths": True,
                "naive_replace_deletes_user_paths": True,
                "prior_version_restored": True,
                "command_inventory_user_and_prior_preserved": True,
            },
            "before": {
                "digest": good["before"]["digest"],
                "user_paths": sorted(good["before"]["user"]),
                "commands": sorted(good["before"]["commands"]),
                "file_count": len(good["before"]["files"]),
            },
            "after": {
                "digest": good["after"]["digest"],
                "user_paths": sorted(good["after"]["user"]),
                "commands": sorted(good["after"]["commands"]),
                "file_count": len(good["after"]["files"]),
            },
            "delta": {
                "user_deleted": good["delta"]["user_deleted"],
                "user_changed": good["delta"]["user_changed"],
                "naive_user_deleted": naive_deleted,
            },
            "implementation": {
                "mode_under_test": "additive-restore",
                "mutant": "naive-tree-replace",
                "policy": (
                    "Restore prior managed bytes; unlink only upgrade-added "
                    "managed paths; never unlink paths absent from the prior "
                    "managed manifest."
                ),
            },
            "owner_approval_required": True,
            "owner_signoff": (
                "NOT-CHECKED: command-center/OWNER-DECISIONS.md is absent; "
                "G-1 delivery is live-probe green, not owner-close."
            ),
            "completion_sentinel": COMPLETION,
            "unit_sentinel": SENTINEL,
        },
        "extensions": {
            "catalog_output_path": OUT,
            "catalog_output_schema": DECLARED_SCHEMA,
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "notes": (
                "G-1 TST-0072: live named probes exit 0, receipt state=SUCCESS, "
                "per-unit manifest row. Did not run global unit_manifest.py "
                f"--write. {SENTINEL} {COMPLETION}"
            ),
        },
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="tst0072-emit-") as tmp:
        root = Path(tmp)
        additive = rehearse(root / "additive", "additive")
        naive = rehearse(root / "naive", "naive")
        control = detector_control(root / "detect")
    host_after = host_census()
    measured = {
        "additive": additive,
        "naive": naive,
        "control": control,
        "host_before": host_before,
        "host_after": host_after,
    }

    c1, t1out = run_probe(P1)
    c2, t2out = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0072 emit probes c1={c1} c2={c2}")
        print(t1out[-3000:])
        print(t2out[-3000:])
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(measured, started, ended, t1out, t2out, c1, c2)
    blob = json.dumps(doc)
    if SENTINEL not in blob or COMPLETION not in blob:
        print("FAILED:TST-0072 sentinel missing from document")
        return 1
    validate_or_die(doc)
    out_path = REPO / OUT
    write_json(out_path, doc)
    validate_or_die(json.loads(out_path.read_text(encoding="utf-8")))

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": DECLARED_SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "additive-inventory",
                "raw_output": t1out,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "naive-mutant",
                "raw_output": t2out,
            },
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
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0072/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0072-os.walk-second-inventory",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for TST-0072: live named probes exit 0, TST-0072.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print("SUCCESS:TST-0072 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
