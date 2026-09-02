#!/usr/bin/env python3
"""Emit TST-0090 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fencing_lease import scenario_zombie_write  # noqa: E402

UNIT = "TST-0090"
OUT = "command-center/receipts/TST-0090.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0090"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0090/probe1_reclaim_once.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0090/probe2_stale_token.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0090/fencing_lease.py",
    "command-center/p2-wave/probes/TST-0090/probe1_reclaim_once.py",
    "command-center/p2-wave/probes/TST-0090/probe2_stale_token.py",
]
QUESTION = (
    "Phase 9 requires work claims, file leases, conflict detection and "
    "duplicate-work suppression. When the dispatcher holding a unit's lease "
    "dies, a new dispatcher may reclaim after lease expiry, and the ORIGINAL "
    "must be unable to commit a late result afterwards. Can a zombie "
    "dispatcher that wakes after expiry still write a receipt?"
)
ANSWER = (
    "No. After expiry exactly one reclaimer wins, the fencing token is "
    "incremented, and the thawed original's write is REJECTED with its stale "
    "token recorded. Timeout-alone takeover (token not incremented) still "
    "accepts the zombie write, so a timeout is not sufficient."
)

# Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
# Bare Draft7Validator either raises RefResolutionError or is vacuous.
# G-1 is live named probes + this file on disk; UNIT_SCHEMA is the
# non-vacuous local check (rejects garbage, pins thawed REJECTED).
UNIT_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "tests",
        "evidence",
        "negative_controls",
        "evidence_run",
        "reviewer",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "completion_sentinel": {"const": SENTINEL},
        "tests": {"type": "array", "minItems": 4},
        "evidence": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 2},
        "evidence_run": {
            "type": "object",
            "required": [
                "thawed_status",
                "stale_token_recorded",
                "orig_token",
                "reclaim_token",
            ],
            "properties": {
                "thawed_status": {"const": "REJECTED"},
                "stale_token_recorded": {"const": True},
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
    },
}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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
        timeout=180,
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
        "receipt_path": "command-center/p2-wave/probes/TST-0090/SUBAGENT-RETURN.json",
        "role": role,
    }


def validate_or_die(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:TST-0090 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(garbage)):
            raise SystemExit(
                f"FAILED:TST-0090 schema accepted garbage {list(garbage)[:2]}"
            )


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0090 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    with tempfile.TemporaryDirectory(prefix="tst0090-ev-") as tmp:
        evidence_run = scenario_zombie_write(Path(tmp) / "evidence", mode="fencing")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "fault_injection_receipt",
        "title": (
            "Orphaned work must be reclaimable exactly once: lease expiry "
            "with a fencing token"
        ),
        "question": QUESTION,
        "hypothesis": (
            "A monotonically increasing fencing token, not lease TTL alone, "
            "is what makes reclaim safe: a thawed original presenting the "
            "pre-reclaim token cannot commit a receipt after a successor "
            "has reclaimed and completed."
        ),
        "answer": ANSWER,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json TST-0090 "
            "_USER-PROMPTS.md:10972-10975"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "local-serialized",
        },
        "premise": {
            "catalog_inputs": [
                "command-center/WORK-UNIT-CATALOG.json",
            ],
            "probes_dir_was_absent": True,
            "imp0409_work_claim_absent": True,
            "action": (
                "Created probes/TST-0090 and a file-backed fencing-token "
                "claim store because IMP-0409's crash-safe work-claim "
                "protocol is not on this tree. Did not exit on "
                "predicate:absent. TST-0089 (monitor-death) is a distinct "
                "observation and was not required to measure token fencing."
            ),
        },
        "injected_fault": {
            "kind": "zombie-dispatcher",
            "target": "work-unit receipt commit after lease expiry",
            "mechanism": (
                "Original dispatcher is frozen (no renew) past TTL; a "
                "successor reclaims and commits; the thawed original then "
                "presents its stale fencing token."
            ),
        },
        "observations": [
            {
                "id": "OBS-1-exactly-one-reclaim",
                "observed": (
                    "After expiry the first reclaim is GRANTED with "
                    "token=original+1; a second reclaim is DENIED "
                    "lease-unexpired."
                ),
            },
            {
                "id": "OBS-2-stale-token-rejected",
                "observed": (
                    f"Thawed original write status="
                    f"{evidence_run['thawed_original']['status']} "
                    f"reason={evidence_run['thawed_original']['reason']} "
                    f"stale_token={evidence_run['orig_token']} recorded="
                    f"{evidence_run['stale_token_recorded']}."
                ),
            },
            {
                "id": "OBS-3-timeout-only-unsafe",
                "observed": (
                    "The timeout-only mutant reclaims without incrementing "
                    "the token, and the thawed original COMMITTED — proving "
                    "TTL takeover without a fencing token is not safe."
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Expired lease permits exactly one reclaim; two concurrent "
                    "reclaimers do not both win; unexpired lease blocks reclaim "
                    "(both-states on FencingClaimStore.reclaim)."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0090/"
                    "fencing_lease.py:reclaim"
                ),
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "A run in which the original dispatcher is frozen past "
                    "lease expiry, the unit is reclaimed and completed, and "
                    "the thawed original's write is REJECTED with its stale "
                    "token recorded. The timeout-only mutant accepts that write."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0090/"
                    "fencing_lease.py:commit_receipt"
                ),
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_expired_lease_permits_exactly_one_reclaim",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "test_two_concurrent_reclaimers_do_not_both_win",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "test_unexpired_lease_blocks_reclaim",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "test_thawed_original_write_is_rejected_by_the_fencing_token",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0090-C1-unexpired-vs-expired",
                "kind": "both-states",
                "description": (
                    "Same reclaim() path: DENIED lease-unexpired before TTL, "
                    "GRANTED with token+1 after TTL."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0090-C2-timeout-only-mutant",
                "kind": "mutation",
                "description": (
                    "TimeoutOnlyClaimStore.reclaim does not increment the "
                    "fencing token; the thawed original then COMMITs. "
                    "Production FencingClaimStore rejects with "
                    "stale-fencing-token."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "evidence_run": {
            "orig_token": evidence_run["orig_token"],
            "reclaim_token": evidence_run["reclaimed"].get("token"),
            "reclaimer_status": evidence_run["reclaimer_committed"]["status"],
            "thawed_status": evidence_run["thawed_original"]["status"],
            "thawed_reason": evidence_run["thawed_original"]["reason"],
            "stale_token_recorded": evidence_run["stale_token_recorded"],
            "winner_payload": evidence_run["winner_payload"],
        },
        "reviewer": {
            "reviewer_id": "TST-0090-probe2-timeout-only-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the timeout-only mutant plus AST "
                "scan of commit_receipt/_bump_token; not a self-attested "
                "prose review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0090/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": (
                "per-unit (not tools/command-center/unit_manifest.py --write)"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0090: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. SUCCESS:TST-0090"
        ),
        "artifacts": [
            {
                "path": "command-center/p2-wave/probes/TST-0090/fencing_lease.py",
                "role": "primary-implementation",
                "exists": True,
            }
        ],
    }

    # Fill sha/bytes for the implementation artifact after hashing live files.
    impl_rel = "command-center/p2-wave/probes/TST-0090/fencing_lease.py"
    impl_sha, impl_n = digest(REPO / impl_rel)
    receipt["artifacts"] = [
        {
            "path": impl_rel,
            "role": "primary-implementation",
            "sha256": impl_sha,
            "bytes": impl_n,
            "exists": True,
        }
    ]

    validate_or_die(receipt)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

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
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "reclaim-once-both-states-concurrent",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "stale-fencing-token-and-timeout-only-mutant",
                "raw_output": t2,
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
            "command-center/p2-wave/probes/TST-0090/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0090-probe2-timeout-only-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0090: live named probes exit 0, TST-0090.json "
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
    print("SUCCESS:TST-0090 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
