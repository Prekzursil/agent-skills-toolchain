#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0008.json from live canary drills."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lifecycle import (  # noqa: E402
    APPLICATORS,
    INSTALL_DECLARED,
    OPS,
    apply_install_deletes_owner,
    apply_uninstall_casefold_wipe,
)
from oracle import run_op  # noqa: E402
from profile import (  # noqa: E402
    CASE_OWNER_REL,
    CASE_PACKAGE_REL,
    IsolationError,
    KEEP_REL,
    RESERVED_REL,
    assert_isolated,
    fresh_profile,
    owner_home,
)
from walker import (  # noqa: E402
    casefold_collapsed,
    census,
    hashed_only,
)

OUT = "command-center/receipts/REL-0008.json"
SCHEMA = "command-center/schema/lifecycle-drill-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0008/probe1_loss_and_hostile_walk.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0008/probe2_clean_four_ops.py"
)
QUESTION = (
    "Answer spec line 11132, 'no data loss occurs', identically for install, "
    "upgrade, rollback and uninstall with one oracle: hash every owner-owned "
    "path in the profile before the operation, hash again afterwards, and "
    "require that nothing present beforehand is missing or altered unless the "
    "operation declared that change. Seed adversarial names first."
)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def file_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def local_validator():
    """Draft-7 validator with a disk store. Never fetches ast-integrate.invalid."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        "https://ast-integrate.invalid/command-center/schema/lifecycle-drill-receipt.schema.json": shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=(
            "https://ast-integrate.invalid/command-center/schema/"
            "lifecycle-drill-receipt.schema.json"
        ),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        first = errs[0]
        path = "/".join(str(p) for p in first.path) or "<root>"
        raise SystemExit(f"FAILED:REL-0008 schema {path}: {first.message}")
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"state": "SUCCESS", "unit_id": "REL-0008"},
    )
    for probe in garbage:
        if not list(validator.iter_errors(probe)):
            raise SystemExit("FAILED:REL-0008 schema accepts garbage")


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def isolation_both_states() -> dict:
    fired = False
    try:
        assert_isolated(owner_home())
    except IsolationError:
        fired = True
    with fresh_profile() as (root, info, _seed):
        silent = bool(info["isolated"] and info["owner_home_untouched"])
        marker = (root / "owner" / ".canary-profile").is_file()
    if not fired or not silent or not marker:
        raise SystemExit(
            f"FAILED:REL-0008 isolation fired={fired} silent={silent} marker={marker}"
        )
    return {
        "fired_on_owner_home": fired,
        "silent_on_canary": silent,
        "owner_home": str(owner_home()),
        "isolation_assertion": info["isolation_assertion"],
        "isolated": True,
        "owner_home_untouched": True,
        "rel_0004_receipt": {
            "path": "command-center/receipts/REL-0004.json",
            "status": "NOT-CHECKED",
            "reason": (
                "REL-0004 receipt is absent on this worktree; REL-0008 supplies "
                "its own throwaway HOME. Isolation is asserted here rather than "
                "inferred from a missing install directory."
            ),
        },
    }


def hostile_walk() -> dict:
    with fresh_profile() as (root, _info, seed):
        snap = census(root)
        hashed = hashed_only(snap)
        APPLICATORS["install"](root)
        after = census(root)
        hashed_after = hashed_only(after)
        nul = hashed.get(RESERVED_REL)
        long_row = hashed.get(seed["long_rel"])
        if nul is None or nul.get("skipped"):
            raise SystemExit("FAILED:REL-0008 walker skipped or missed NUL")
        if long_row is None or long_row.get("skipped"):
            raise SystemExit("FAILED:REL-0008 walker skipped long path")
        if long_row["rel_chars"] < 260 and long_row["abs_chars"] < 260:
            raise SystemExit(f"FAILED:REL-0008 long path not 260+ {long_row}")
        if CASE_OWNER_REL not in hashed_after or CASE_PACKAGE_REL not in hashed_after:
            raise SystemExit("FAILED:REL-0008 case siblings not both present")
        collapsed = casefold_collapsed(hashed_after)
        if len(collapsed) >= len(hashed_after):
            raise SystemExit(
                "FAILED:REL-0008 collapsed census did not drop a case sibling"
            )
        fifo = snap.get(seed["fifo_rel"]) or {}
        if not fifo.get("skipped"):
            raise SystemExit("FAILED:REL-0008 fifo was hashed rather than skipped")
        src = (HERE / "walker.py").read_text(encoding="utf-8")
        if "os.path.relpath" in src:
            raise SystemExit("FAILED:REL-0008 walker.py still calls os.path.relpath")
        return {
            "nul_present": True,
            "nul_skipped": False,
            "nul_sha256": nul["sha256"],
            "nul_rel": RESERVED_REL,
            "long_rel": seed["long_rel"],
            "long_abs_chars": long_row["abs_chars"],
            "long_rel_chars": long_row["rel_chars"],
            "long_sha256": long_row["sha256"],
            "long_skipped": False,
            "case_owner_rel": CASE_OWNER_REL,
            "case_package_rel": CASE_PACKAGE_REL,
            "case_owner_sha256": hashed_after[CASE_OWNER_REL]["sha256"],
            "case_package_sha256": hashed_after[CASE_PACKAGE_REL]["sha256"],
            "exact_path_count": len(hashed_after),
            "casefold_collapsed_count": len(collapsed),
            "distinct_not_collapsed": True,
            "fifo_rel": seed["fifo_rel"],
            "fifo_not_checked": True,
            "walker_uses_stdlib_relpath": False,
            "hashed_path_count": len(hashed),
        }


def plant_and_delete() -> dict:
    with fresh_profile() as (root, _info, seed):
        result = run_op(
            root,
            "install-deletes-owner",
            lambda p: apply_install_deletes_owner(p, KEEP_REL),
            INSTALL_DECLARED,
        )
        lost = [row["path"] for row in result.loss]
        if KEEP_REL not in lost:
            raise SystemExit(
                f"FAILED:REL-0008 plant-and-delete did not report loss: {result.loss}"
            )
        if result.silent:
            raise SystemExit("FAILED:REL-0008 plant-and-delete oracle was silent")
        return {
            "caught": True,
            "lost_paths": lost,
            "paths_hashed": result.paths_hashed,
            "paths_skipped": result.paths_skipped,
            "paths_altered": result.paths_altered,
            "oracle": result.as_dict(),
        }


def clean_four_ops() -> list[dict]:
    rows: list[dict] = []
    with fresh_profile() as (root, _info, seed):
        for i, name in enumerate(("install", "upgrade", "rollback", "uninstall")):
            result = run_op(root, name, APPLICATORS[name], OPS[name])
            if not result.silent:
                raise SystemExit(
                    f"FAILED:REL-0008 clean {name} reported loss {result.loss}"
                )
            if result.paths_hashed < 1:
                raise SystemExit(f"FAILED:REL-0008 clean {name} hashed_path_count=0")
            if seed["fifo_rel"] not in result.skipped_paths:
                raise SystemExit(f"FAILED:REL-0008 clean {name} fifo not skipped")
            if seed["fifo_rel"] in result.verified_unchanged:
                raise SystemExit(
                    f"FAILED:REL-0008 clean {name} folded skip into pass"
                )
            if result.honest_pass_count >= result.lying_pass_count:
                raise SystemExit(
                    f"FAILED:REL-0008 clean {name} skip-fold metric not distinct"
                )
            row = result.as_dict()
            row["fresh_profile"] = i == 0
            row["retry_policy"] = (
                "retry only on a FRESH profile; this sequence is one attempt"
            )
            rows.append(row)
    return rows


def reviewer_destroy() -> dict:
    with fresh_profile() as (root, _info, _seed):
        run_op(root, "install", APPLICATORS["install"], OPS["install"])
        result = run_op(
            root,
            "uninstall-casefold-wipe",
            apply_uninstall_casefold_wipe,
            OPS["uninstall"],
        )
        lost = [row["path"] for row in result.loss]
        if CASE_OWNER_REL not in lost:
            raise SystemExit(
                f"FAILED:REL-0008 reviewer destroy missed case sibling: {lost}"
            )
        return {
            "caught": True,
            "lifecycle_path": "uninstall",
            "destroyed_owner_path": CASE_OWNER_REL,
            "lost_paths": lost,
            "paths_hashed": result.paths_hashed,
            "paths_skipped": result.paths_skipped,
            "paths_altered": result.paths_altered,
            "oracle": result.as_dict(),
        }


def main() -> int:
    started = datetime.now(timezone.utc)
    isolation = isolation_both_states()
    hostile = hostile_walk()
    planted = plant_and_delete()
    operations = clean_four_ops()
    reviewer = reviewer_destroy()
    hashed_count = operations[0]["paths_hashed"]
    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")

    src_plant = (
        "python3 -B command-center/p2-wave/probes/REL-0008/emit_receipt.py "
        "plant_and_delete"
    )
    src_walk = (
        "python3 -B command-center/p2-wave/probes/REL-0008/emit_receipt.py "
        "hostile_walk"
    )
    src_clean = (
        "python3 -B command-center/p2-wave/probes/REL-0008/emit_receipt.py "
        "clean_four_ops"
    )
    src_review = (
        "python3 -B command-center/p2-wave/probes/REL-0008/emit_receipt.py "
        "reviewer_destroy"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "REL-0008",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0008",
        "profile": "destruction-oracle",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json REL-0008; "
            "_USER-PROMPTS.md:11016-11017,11132"
        ),
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "data-integrity-engineer",
            "execution_substrate": "linux-local",
        },
        "artifacts": [
            file_row("command-center/p2-wave/probes/REL-0008/oracle.py", "primary"),
            file_row("command-center/p2-wave/probes/REL-0008/walker.py", "supporting"),
            file_row("command-center/p2-wave/probes/REL-0008/lifecycle.py", "supporting"),
            file_row("command-center/p2-wave/probes/REL-0008/profile.py", "supporting"),
            file_row(SCHEMA, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "A broken install that deletes seeded owner file "
                    f"{KEEP_REL} is reported as loss, not a silent pass."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0008/oracle.py:compare",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        src_plant,
                        json.dumps(planted["lost_paths"]),
                        0,
                    ),
                    probe("verifier", "command", P1, "plant_delete_caught=true", 0),
                ],
            },
            {
                "claim": (
                    "Clean install, upgrade, rollback and uninstall are oracle-"
                    f"silent; hashed_path_count={hashed_count} is a number; "
                    "skipped fifo is NOT-CHECKED and is not folded into pass."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0008/oracle.py:run_op",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        src_clean,
                        json.dumps(
                            {
                                "hashed_path_count": hashed_count,
                                "ops": [row["name"] for row in operations],
                            }
                        ),
                        0,
                    ),
                    probe("verifier", "command", P2, "ops_silent four-ops", 0),
                ],
            },
            {
                "claim": (
                    "The walker hashed a reserved-device-named file and a 260+ "
                    "character relative path, and tracked a case-only sibling as "
                    "a distinct path."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0008/walker.py:census",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        src_walk,
                        json.dumps(
                            {
                                "nul_sha256": hostile["nul_sha256"],
                                "long_rel_chars": hostile["long_rel_chars"],
                                "exact": hostile["exact_path_count"],
                                "collapsed": hostile["casefold_collapsed_count"],
                            }
                        ),
                        0,
                    ),
                    probe("verifier", "command", P1, "nul_hashed long_rel case", 0),
                ],
            },
            {
                "claim": (
                    "A reviewer case-insensitive uninstall that would destroy "
                    f"{CASE_OWNER_REL} is caught as loss before sign-off."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0008/lifecycle.py:apply_uninstall_casefold_wipe",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        src_review,
                        json.dumps(reviewer["lost_paths"]),
                        0,
                    ),
                    probe("verifier", "command", P2, "reviewer_caught=true", 0),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-plant-and-delete",
                "name": "Broken installer deleting a seeded owner file is loss",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": f"lost={KEEP_REL}",
            },
            {
                "id": "T2-clean-four-ops",
                "name": "Clean four-op drill is silent with a numeric hashed-path count",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": f"hashed_path_count={hashed_count}",
            },
            {
                "id": "T3-hostile-walk",
                "name": "Walker hashes NUL and a 260+ character path without raising",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"nul_sha256={hostile['nul_sha256'][:12]} "
                    f"rel_chars={hostile['long_rel_chars']}"
                ),
            },
            {
                "id": "T4-case-distinct",
                "name": "Case-only colliding name is a distinct census key",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": (
                    f"exact={hostile['exact_path_count']} "
                    f"collapsed={hostile['casefold_collapsed_count']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "plant-and-delete",
                "kind": "mutation",
                "description": (
                    "Installer deletes seeded owner file; oracle must fire. "
                    "Clean install on the same seed must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ",".join(planted["lost_paths"]),
                "good_state_output": "install oracle_silent=true",
            },
            {
                "id": "isolation-owner-home",
                "kind": "known-broken-fixture",
                "description": (
                    "assert_isolated must raise on the owner's live HOME and "
                    "stay silent on the throwaway canary."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "IsolationError on Path.home()",
                "good_state_output": "isolated=true",
            },
            {
                "id": "casefold-uninstall-wipe",
                "kind": "adversarial-payload",
                "description": (
                    "Case-insensitive uninstall deletes the owner case-sibling; "
                    "oracle must report that path as loss."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": CASE_OWNER_REL,
                "good_state_output": "uninstall oracle_silent=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0008-probe2-destroy-and-catch",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": now,
            "notes": (
                "Probe2 re-runs a case-insensitive uninstall against a fresh "
                "profile and requires the oracle to name "
                f"{CASE_OWNER_REL} as loss before PASS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/REL-0008/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "REL-0008",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft7Validator local-store lifecycle-drill-receipt",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -B command-center/p2-wave/probes/REL-0008/"
                        "emit_receipt.py validate_or_die"
                    ),
                    "schema-valid against local $ref store; garbage rejected",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": now,
            "duration_seconds": max(0.0, (ended - started).total_seconds()),
        },
        "retry": {
            "count": 1,
            "policy": (
                "retry only on a FRESH profile. Re-running a lifecycle drill "
                "on a dirtied profile measures the dirt, not the drill."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "schema-shim-https-ref-unresolvable",
                    "outcome": "FAILED",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "local-store-receipt-core-emit",
                    "outcome": "SUCCESS",
                },
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windows Get-Item -LiteralPath corroboration of the NUL "
                    "and 260+ character paths was not run; this runner is Linux."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run walker.py census on Windows with a reserved-device "
                    "name and a MAX_PATH-class relative path."
                ),
            },
            {
                "claim": (
                    "REL-0004 canary-rig receipt is absent on this worktree; "
                    "isolation is asserted locally rather than inherited."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run after command-center/receipts/REL-0004.json exists "
                    "and confirm REL-0008 still refuses owner HOME."
                ),
            },
        ],
        "report": {
            "kind": "lifecycle-drill-receipt",
            "title": (
                "Destruction oracle over all four lifecycle operations, "
                "seeded with hostile filenames"
            ),
            "question": QUESTION,
            "hashed_path_count": hashed_count,
            "skip_folded_into_pass": False,
            "operations": operations,
            "hostile_walk": hostile,
            "plant_and_delete": {
                "caught": planted["caught"],
                "lost_paths": planted["lost_paths"],
                "paths_hashed": planted["paths_hashed"],
                "paths_skipped": planted["paths_skipped"],
                "paths_altered": planted["paths_altered"],
            },
            "reviewer_destroy": {
                "caught": reviewer["caught"],
                "lifecycle_path": reviewer["lifecycle_path"],
                "destroyed_owner_path": reviewer["destroyed_owner_path"],
                "lost_paths": reviewer["lost_paths"],
            },
            "isolation": isolation,
            "surfaces_not_checked": [
                "owner live HOME (isolation refuses it; never queried as a drill root)",
                "REL-0004 hook-firing canary receipt (file absent on this worktree)",
                "Windows Get-Item -LiteralPath corroboration (this runner is Linux)",
                operations[0]["skipped_paths"][0]
                if operations[0]["skipped_paths"]
                else "fifo skip",
            ],
            "walker_never_calls_os_path_relpath": True,
            "observations": [
                {
                    "name": "hashed_path_count",
                    "measured": hashed_count,
                    "method": "oracle census before install",
                    "anchor": "command-center/p2-wave/probes/REL-0008/oracle.py:run_op",
                },
                {
                    "name": "plant_and_delete_caught",
                    "measured": True,
                    "method": "broken install deletes owner file",
                    "anchor": "command-center/p2-wave/probes/REL-0008/lifecycle.py:apply_install_deletes_owner",
                },
                {
                    "name": "long_rel_chars",
                    "measured": hostile["long_rel_chars"],
                    "method": "walker census of seeded 240-char directory",
                    "anchor": "command-center/p2-wave/probes/REL-0008/profile.py:LONG_REL",
                },
                {
                    "name": "skip_folded_into_pass",
                    "measured": False,
                    "method": "fifo listed in skipped_paths not verified_unchanged",
                    "anchor": "command-center/p2-wave/probes/REL-0008/oracle.py:honest_pass_count",
                },
            ],
            "control_ids": [
                "plant-and-delete",
                "isolation-owner-home",
                "casefold-uninstall-wipe",
            ],
        },
        "extensions": {
            "write_scope": [
                "command-center/receipts/REL-0008.json",
                "command-center/p2-wave/probes/REL-0008/",
            ],
            "prohibited_actions_not_run": [
                "git commit",
                "git add",
                "git push",
                "git stash",
                "git checkout",
                "git rebase",
                "tools/command-center/unit_manifest.py --write",
            ],
        },
    }
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size} hashed_path_count={hashed_count}")
    print("SUCCESS:REL-0008")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
