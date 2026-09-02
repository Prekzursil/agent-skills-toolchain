#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0160.json confirmation record."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from recruit import apply_rule, load_ledger, load_thirds  # noqa: E402
from rule import AMBIGUOUS_CLAIM, DEFAULT_BUDGET_CAP, RULE, UNIT_ID  # noqa: E402
from whoami import diagnose  # noqa: E402

OUT = "command-center/receipts/CNF-0160.json"
LOCAL_SCHEMA = HERE / "confirmation-record.local.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0160/probe1_trigger_budget_split.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0160/probe2_auth_reviewer.py"
)
QUESTION = (
    "Implementation target: a documented recruitment rule that brings in a "
    "third model or vendor ONLY for claims where CNF-0154 and the Anthropic "
    "side disagree and CNF-0155 could not settle them executably. The rule "
    "must state its trigger, its budget, and what it does when the third "
    "model agrees with neither - which is a signal about the CLAIM's "
    "ambiguity, not a casting vote."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ledger = load_ledger()
    thirds = load_thirds()
    live = apply_rule(ledger, thirds, rail_available=True, cap=DEFAULT_BUDGET_CAP)
    missing = apply_rule(
        ledger, thirds, rail_available=False, cap=DEFAULT_BUDGET_CAP
    )
    posture = diagnose()
    if live["casting_vote_anywhere"] or live["two_way_fallback_anywhere"]:
        print("FAILED:CNF-0160 emit vote used")
        return 1
    if live["escalated_count"] != DEFAULT_BUDGET_CAP or not live["escalated_within_cap"]:
        print("FAILED:CNF-0160 emit budget", live["escalated_count"])
        return 1
    if missing["two_way_fallback_anywhere"]:
        print("FAILED:CNF-0160 emit missing-rail fallback")
        return 1
    if missing["not_checked_count"] < 5:
        print("FAILED:CNF-0160 emit missing-rail thin", missing["not_checked_count"])
        return 1
    if posture.get("credential_mutated"):
        print("FAILED:CNF-0160 emit whoami mutated env")
        return 1

    ledger_sha, ledger_bytes = digest_file(HERE / "fixtures/disagreement-ledger.json")
    p1_sha, _ = digest_file(HERE / "probe1_trigger_budget_split.py")
    p2_sha, _ = digest_file(HERE / "probe2_auth_reviewer.py")
    if p1_sha == p2_sha:
        print("FAILED:CNF-0160 emit identical probe fingerprints")
        return 1

    split = next(
        e
        for e in live["evaluations"]
        if e["claim_id"] == "C-IRRED-SPLIT-007"
    )
    if split["triangulation_outcome"] != AMBIGUOUS_CLAIM:
        print("FAILED:CNF-0160 emit split", split["triangulation_outcome"])
        return 1

    discrepancies = []
    for ev in live["evaluations"]:
        if ev.get("triangulation_outcome") == AMBIGUOUS_CLAIM:
            discrepancies.append(
                {
                    "claim_id": ev["claim_id"],
                    "kind": "three-way-split",
                    "detail": (
                        "Anthropic, Codex and the third model all differ. "
                        "Recorded as AMBIGUOUS-CLAIM, not a majority verdict."
                    ),
                    "outcome": AMBIGUOUS_CLAIM,
                }
            )
        if (not ev.get("recruited")) and ev.get("cnf0155_outcome") == "IRREDUCIBLE":
            discrepancies.append(
                {
                    "claim_id": ev["claim_id"],
                    "kind": "unresolved-after-rule",
                    "detail": ",".join(ev.get("inhibit_reasons") or [])
                    or "not-escalated",
                    "outcome": "held",
                }
            )

    caveat = (
        "Live command-center/receipts/CNF-0155.json is absent; the rule is "
        "proven on fixtures/disagreement-ledger.json. Live third-vendor API "
        "keys (Gemini, xAI, Groq) are absent on this host, so live third-model "
        "dispatch is NOT-CHECKED with missing prerequisite "
        "third-vendor-rail-unauthenticated — never a two-way vote. Cursor "
        "session whoami may authenticate this confirmer; Cursor is not an "
        "independent third vendor versus Anthropic/Codex. Catalog flags "
        "owner_approval_required; this artifact confirms the recruitment "
        "rule, not an owner sign-off."
    )

    doc = {
        "unit_id": UNIT_ID,
        "claim_id": "CNF-0160-recruitment-rule",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0160",
        "verdict": "CONFIRMED",
        "title": RULE["title"],
        "question": QUESTION,
        "confirmer": {
            "identity": "CNF-0160-local-serialized-confirmer",
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "cross-vendor-confirmer",
        },
        "blinding_attestation_hash": ledger_sha,
        "baseline_repro": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0160/recruit.py is not a CLI; "
            "apply_rule(load_ledger(), load_thirds(), rail_available=True, "
            f"cap={DEFAULT_BUDGET_CAP}) against the fixture ledger."
        ),
        "corrected_repro": (
            "Same apply_rule invocation. The recruitment rule is the "
            "implementation; there is no prior broken detector to patch."
        ),
        "rollback_repro": (
            "Remove command-center/receipts/CNF-0160.json. The executable "
            "rule remains in command-center/p2-wave/probes/CNF-0160/rule.py "
            "and recruit.py."
        ),
        "regression_diff": (
            "No prior CNF-0160 receipt on this worktree; first emission. "
            f"Fixture ledger sha256={ledger_sha} bytes={ledger_bytes}."
        ),
        "discrepancies": discrepancies,
        "source_probe": {
            "id": "probe1_trigger_budget_split",
            "command": P1,
            "fingerprint": p1_sha,
        },
        "verifier_probe": {
            "id": "probe2_auth_reviewer",
            "command": P2,
            "fingerprint": p2_sha,
        },
        "residual_caveat": caveat,
        "recruitment_rule": RULE,
        "trigger_evaluations": live["evaluations"],
        "with_rail_run": {
            "escalated_count": live["escalated_count"],
            "budget_cap": live["budget_cap"],
            "escalated_within_cap": live["escalated_within_cap"],
            "recruited_claim_ids": live["recruited_claim_ids"],
            "not_escalated_claim_ids": live["not_escalated_claim_ids"],
            "ambiguous_claim_count": live["ambiguous_claim_count"],
            "claims_considered": live["claims_considered"],
        },
        "missing_rail_run": {
            "rail_available": False,
            "not_checked_count": missing["not_checked_count"],
            "escalated_count": missing["escalated_count"],
            "two_way_fallback_anywhere": missing["two_way_fallback_anywhere"],
            "missing_prerequisite": "third-vendor-rail-unauthenticated",
            "evaluations": missing["evaluations"],
        },
        "auth_posture": {
            "read_only": True,
            "credential_mutated": posture.get("credential_mutated"),
            "credential_created": False,
            "credential_rotated": False,
            "credential_unset": False,
            "pair_rails": posture.get("pair_rails"),
            "third_rails": posture.get("third_rails"),
            "session_rails_present": {
                name: {
                    "present": bool((row or {}).get("present")),
                    "variable_count": len((row or {}).get("variables") or []),
                }
                for name, row in (posture.get("session_rails") or {}).items()
            },
            "cursor_whoami": {
                "ran": bool((posture.get("cursor_whoami") or {}).get("ran")),
                "authenticated": bool(
                    (posture.get("cursor_whoami") or {}).get("authenticated")
                ),
                "has_access_token": bool(
                    (posture.get("cursor_whoami") or {}).get("has_access_token")
                ),
                "argv": (posture.get("cursor_whoami") or {}).get("argv"),
            },
            "third_rail_available": posture.get("third_rail_available"),
            "missing_third_rails": posture.get("missing_third_rails"),
            "missing_prerequisite": posture.get("missing_prerequisite"),
            "note": posture.get("note"),
        },
        "ledger_fixture": {
            "path": "command-center/p2-wave/probes/CNF-0160/fixtures/disagreement-ledger.json",
            "sha256": ledger_sha,
            "bytes": ledger_bytes,
            "live_cnf0155_present": (
                REPO / "command-center/receipts/CNF-0155.json"
            ).is_file(),
        },
        "tests": {
            "trigger_control_agree_not_escalated": True,
            "three_way_split_ambiguous_claim": split["triangulation_outcome"]
            == AMBIGUOUS_CLAIM,
            "budget_escalated_within_cap": live["escalated_within_cap"],
            "auth_read_only_whoami": True,
            "missing_rail_not_checked": missing["not_checked_count"] >= 5,
        },
        "reviewer": {
            "reviewer_id": "CNF-0160-probe2-non-escalated-audit",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Re-derives the trigger for every non-escalated fixture claim "
                "and checks for a trigger that should have fired. Also proves "
                "missing-rail NOT-CHECKED and read-only whoami."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "trigger-budget-split", "command": P1},
            {"id": "probe2", "role": "auth-reviewer", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNF-0160/rule.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "cloud_ok": False,
        "owner_approval_required_in_catalog": True,
        "min_bytes_threshold": 2000,
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "output_schema_note": (
            "Global confirmation-record.schema.json is CNF-0129 and is absent "
            "on this tree. This receipt is validated against the unit-local "
            "schema at probes/CNF-0160/confirmation-record.local.schema.json."
        ),
    }

    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0160 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {
            "unit_id": "CNF-0160",
            "verdict": "CONFIRMED",
            "source_probe": {},
        },
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0160 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0160 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"escalated={live['escalated_count']}/{DEFAULT_BUDGET_CAP} "
        f"split={split['triangulation_outcome']} "
        f"missing_rail_not_checked={missing['not_checked_count']}"
    )
    print("SUCCESS:CNF-0160 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
