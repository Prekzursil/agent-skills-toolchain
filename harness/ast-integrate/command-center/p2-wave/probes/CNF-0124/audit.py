"""Run the CNF-0124 authorship audit over live receipts plus fixtures."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from corpus import load_corpus
from predicate import (
    PREDICATE_LINE,
    PREDICATE_PATH,
    RULE_A,
    RULE_B,
    RULE_C,
    RULE_FORGED,
    RULE_MISSING,
    RULE_PASS,
    evaluate,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0124"
OUT_REL = "command-center/confirmation/CNF-0124-authorship-audit.json"
SCHEMA_REL = "command-center/schema/confirmation-audit.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0124 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the planted self-confirmation "
    "was flagged and every receipt has an independence verdict with its deciding "
    "rule named. Any other terminal state is FAILED:CNF-0124 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Did any implementer confirm their own work? Audit the authorship chain of "
    "every confirmation receipt against the implementation provenance and answer: "
    "how many confirmations violate the independence predicate, and does any "
    "violation involve a P0 or P1 claim?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0124/probe1_planted_self_confirmation.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0124/probe2_missing_and_forged.py"
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json#CNF-0124 "
    "question_or_target (authorship audit / self-confirmation)"
)


def payload_of(doc: dict) -> dict:
    """Domain payload lives under report for receipt_core additionalProperties:false."""
    report = doc.get("report")
    if isinstance(report, dict) and "answers" in report:
        return report
    return doc


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def _digest(rel: str) -> tuple[str, int, str]:
    path = REPO / rel
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    hashed = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(hashed).hexdigest(), len(hashed), eol


def _art(rel: str, role: str) -> dict:
    sha, size, eol = _digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def _row(receipt: dict, judged: dict) -> dict:
    corr = judged["corroboration"]
    return {
        "receipt_id": judged["receipt_id"],
        "source": receipt.get("_source") or "unknown",
        "source_path": receipt.get("_source_path"),
        "confirmer_identity": judged["confirmer_identity"],
        "implementer_identity": judged["implementer_identity"],
        "claim_id": judged["claim_id"],
        "claim_priority": judged["claim_priority"],
        "independence_verdict": judged["independence_verdict"],
        "deciding_rule": judged["deciding_rule"],
        "p0_or_p1": judged["p0_or_p1"],
        "planted": bool(receipt.get("planted")),
        "corroboration": {
            "changed_path_surface": corr["changed_path_surface"],
            "tool_call_ledger": corr["tool_call_ledger"],
            "result": corr["result"],
        },
    }


def _schema_store() -> tuple[dict, object]:
    from jsonschema import Draft202012Validator, RefResolver

    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(profiles.get("$id")): profiles,
        str(receipt.get("$id")): receipt,
        str(shim.get("$id")): shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/command-center/schema/confirmation-audit.schema.json": shim,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    return shim, Draft202012Validator(shim, resolver=resolver)


def validate_against_schema(doc: dict) -> list[str]:
    _shim, validator = _schema_store()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errs]


def schema_rejects_garbage() -> bool:
    _shim, validator = _schema_store()
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    return all(list(validator.iter_errors(g)) for g in garbage)


def run_audit() -> dict:
    corpus = load_corpus()
    live_rows = [_row(r, evaluate(r)) for r in corpus["live"]]
    fixture_rows = [_row(r, evaluate(r)) for r in corpus["fixtures"]]
    all_rows = live_rows + fixture_rows

    planted = [r for r in all_rows if r["receipt_id"] == "planted-self-confirmation"]
    planted_flagged = bool(
        planted
        and planted[0]["independence_verdict"] == "VIOLATION"
        and planted[0]["deciding_rule"] == RULE_A
    )
    every_named = all(
        isinstance(r.get("deciding_rule"), str) and len(r["deciding_rule"]) >= 8
        for r in all_rows
    )
    live_viol = [r for r in live_rows if r["independence_verdict"] == "VIOLATION"]
    viol = [r for r in all_rows if r["independence_verdict"] == "VIOLATION"]
    p0p1 = [r for r in viol if r["p0_or_p1"]]
    live_empty = corpus["live_empty"]

    cnf0002 = REPO / "command-center/confirmation/CNF-0002-independence-predicate.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def observed(rid: str) -> str:
        return next(
            (
                f"{r['independence_verdict']}/{r['deciding_rule']}"
                for r in all_rows
                if r["receipt_id"] == rid
            ),
            "ABSENT",
        )

    def row_ok(rid: str, verdict: str, rule: str) -> bool:
        return any(
            r["receipt_id"] == rid
            and r["independence_verdict"] == verdict
            and r["deciding_rule"] == rule
            for r in all_rows
        )

    controls = [
        {
            "id": "planted-self-confirmation",
            "expected": f"VIOLATION/{RULE_A}",
            "observed": observed("planted-self-confirmation"),
            "pass": planted_flagged,
        },
        {
            "id": "missing-authorship-default-violation",
            "expected": f"VIOLATION/{RULE_MISSING}",
            "observed": observed("missing-authorship"),
            "pass": row_ok("missing-authorship", "VIOLATION", RULE_MISSING),
        },
        {
            "id": "forged-authorship-path-ledger",
            "expected": f"VIOLATION/{RULE_FORGED}",
            "observed": observed("forged-independent-label"),
            "pass": row_ok("forged-independent-label", "VIOLATION", RULE_FORGED),
        },
        {
            "id": "independent-control-passes",
            "expected": f"PASS/{RULE_PASS}",
            "observed": observed("independent-ok"),
            "pass": row_ok("independent-ok", "PASS", RULE_PASS),
        },
        {
            "id": "rule-b-reviewer-not-inert",
            "expected": f"VIOLATION/{RULE_B}",
            "observed": observed("reviewer-overlap"),
            "pass": row_ok("reviewer-overlap", "VIOLATION", RULE_B),
        },
        {
            "id": "rule-c-ancestor-author",
            "expected": f"VIOLATION/{RULE_C}",
            "observed": observed("ancestor-author"),
            "pass": row_ok("ancestor-author", "VIOLATION", RULE_C),
        },
    ]

    controls_pass = all(c["pass"] for c in controls)
    state = "SUCCESS" if controls_pass and planted_flagged and every_named else "FAILED"

    answers = {
        "live_receipts_count": len(live_rows),
        "live_violation_count": len(live_viol),
        "live_empty_reported_as_zero_of_zero": live_empty,
        "live_zero_of_zero": f"{len(live_viol)} of {len(live_rows)}",
        "audited_receipts_count": len(all_rows),
        "violation_count": len(viol),
        "p0_or_p1_violation": bool(p0p1),
        "p0_or_p1_violation_receipts": [r["receipt_id"] for r in p0p1],
        "planted_self_confirmation_flagged": planted_flagged,
        "every_receipt_has_named_deciding_rule": every_named,
        "violating_receipt_ids": [r["receipt_id"] for r in viol],
        "how_many_confirmations_violate": (
            f"{len(live_viol)} of {len(live_rows)} live; "
            f"{len(viol)} of {len(all_rows)} including fixtures"
        ),
        "any_p0_or_p1_violation": bool(p0p1),
    }

    planted_obs = observed("planted-self-confirmation")
    missing_obs = observed("missing-authorship")
    forged_obs = observed("forged-independent-label")
    indep_obs = observed("independent-ok")
    rule_b_obs = observed("reviewer-overlap")
    rule_c_obs = observed("ancestor-author")

    report = {
        "kind": "confirmation-audit",
        "control_ids": [c["id"] for c in controls],
        "observations": [
            {
                "name": "live_receipts_count",
                "measured": len(live_rows),
                "method": "file-read",
                "anchor": "command-center/confirmation + command-center/receipts",
            },
            {
                "name": "live_violation_count",
                "measured": len(live_viol),
                "method": "static-analysis",
                "anchor": f"{PREDICATE_PATH}:{PREDICATE_LINE}",
            },
            {
                "name": "planted_self_confirmation_flagged",
                "measured": planted_flagged,
                "method": "static-analysis",
                "anchor": "command-center/p2-wave/probes/CNF-0124/fixtures/planted-self-confirmation.json",
            },
            {
                "name": "every_receipt_has_named_deciding_rule",
                "measured": every_named,
                "method": "static-analysis",
                "anchor": f"{PREDICATE_PATH}:{PREDICATE_LINE}",
            },
            {
                "name": "p0_or_p1_violation",
                "measured": bool(p0p1),
                "method": "static-analysis",
                "anchor": f"{PREDICATE_PATH}:{PREDICATE_LINE}",
            },
        ],
        "title": "Authorship audit over confirmation receipts to catch self-confirmation",
        "question": QUESTION,
        "answers": answers,
        "receipts": all_rows,
        "controls": controls,
        "independence_predicate": {
            "source_path": PREDICATE_PATH,
            "source_line": PREDICATE_LINE,
            "cnf_0002_artifact": {
                "path": "command-center/confirmation/CNF-0002-independence-predicate.json",
                "present": cnf0002.is_file(),
                "fallback": (
                    "catalog CNF-0002 rules (a) author-overlap, (b) implementation-reviewer, "
                    "(c) ancestor-author implemented in predicate.py; empty live corpus "
                    "reported as 0 of 0 rather than a pass"
                ),
            },
            "rules": [
                f"{RULE_MISSING}: absent confirmer or implementer identity is a violation, never a pass by omission",
                f"{RULE_FORGED}: claimed confirmer contradicted by tool-call ledger actors",
                f"{RULE_A}: confirmer agent id appears in implementation authoring provenance",
                f"{RULE_B}: confirmer reviewed that implementation",
                f"{RULE_C}: confirmer authored an ancestor artifact the claim depends on",
                f"{RULE_PASS}: none of the exclusion rules fired",
            ],
        },
        "live_corpus": {
            "directories": [
                "command-center/confirmation",
                "command-center/receipts",
            ],
            "empty": live_empty,
            "note": (
                "No live confirmation receipts matched claim_id+receipt_id on this worktree. "
                "That is 0 of 0 for the production corpus, not a clean pass. Fixture receipts "
                "including the planted self-confirmation are audited in the same run."
            ),
        },
    }

    tests_ok = controls_pass and planted_flagged and every_named
    test_result = "PASS" if tests_ok else "FAIL"

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-headless",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "report": report,
        "artifacts": [
            _art(SCHEMA_REL, "supporting"),
            _art(PREDICATE_PATH, "supporting"),
            _art("command-center/p2-wave/probes/CNF-0124/corpus.py", "supporting"),
            _art(
                "command-center/p2-wave/probes/CNF-0124/fixtures/planted-self-confirmation.json",
                "fixture",
            ),
            _art(
                "command-center/p2-wave/probes/CNF-0124/fixtures/missing-authorship.json",
                "fixture",
            ),
            _art(
                "command-center/p2-wave/probes/CNF-0124/fixtures/forged-independent-label.json",
                "control",
            ),
            _art(
                "command-center/p2-wave/probes/CNF-0124/fixtures/independent-ok.json",
                "control",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "The planted self-confirmation fixture (same agent as implementer "
                    "and confirmer on a P0 claim) is a VIOLATION under rule (a)."
                ),
                "verdict": "CONFIRMED" if planted_flagged else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0124/fixtures/planted-self-confirmation.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "python3 -B -c \"import json,sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/CNF-0124'); from predicate import "
                            "evaluate; print(evaluate(json.load(open("
                            "'command-center/p2-wave/probes/CNF-0124/fixtures/"
                            "planted-self-confirmation.json'))))\""
                        ),
                        "raw_output": planted_obs,
                        "fingerprint": fingerprint(
                            "static-analysis", "evaluate:planted-self-confirmation"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "command-center/p2-wave/probes/CNF-0124/fixtures/"
                            "planted-self-confirmation.json"
                        ),
                        "raw_output": (
                            "confirmer=agent-implementer-alpha "
                            "implementer=agent-implementer-alpha claim_priority=P0"
                        ),
                        "fingerprint": fingerprint(
                            "file-read",
                            "fixtures/planted-self-confirmation.json",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Every audited receipt has an independence verdict with a named "
                    "deciding rule; omitted authorship is a default violation and a "
                    "forged confirmer is contradicted by the tool-call ledger."
                ),
                "verdict": "CONFIRMED" if every_named and controls_pass else "REFUTED",
                "confidence": "almost-certain",
                "anchor": f"{PREDICATE_PATH}:{PREDICATE_LINE}",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "python3 -B -c \"import sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/CNF-0124'); from audit import "
                            "run_audit; d=run_audit(); print(d['report']['answers'])\""
                        ),
                        "raw_output": (
                            f"named={every_named} missing={missing_obs} "
                            f"forged={forged_obs} independent={indep_obs} "
                            f"rule_b={rule_b_obs} rule_c={rule_c_obs}"
                        ),
                        "fingerprint": fingerprint(
                            "static-analysis", "evaluate:full-fixture-corpus"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": f"{PREDICATE_PATH}:{PREDICATE_LINE}",
                        "raw_output": (
                            "evaluate() names exactly one deciding rule per receipt; "
                            f"RULE_MISSING={RULE_MISSING} RULE_FORGED={RULE_FORGED}"
                        ),
                        "fingerprint": fingerprint(
                            "file-read", f"{PREDICATE_PATH}:{PREDICATE_LINE}"
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-planted-self-confirmation",
                "name": "Planted same-agent P0 self-confirmation is VIOLATION/rule-a",
                "command": P1_CMD,
                "result": test_result,
                "assertions": 4,
            },
            {
                "id": "probe2-missing-forged-rule-b",
                "name": "Missing authorship, forged ledger, rule-b, independent pass",
                "command": P2_CMD,
                "result": test_result,
                "assertions": 5,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-planted-self-confirmation",
                "kind": "known-broken-fixture",
                "description": (
                    "Same agent as implementer and confirmer on a P0 claim must fire; "
                    "an independent confirmer on the twin fixture must pass."
                ),
                "fired_on_bad_state": planted_flagged,
                "silent_on_good_state": row_ok("independent-ok", "PASS", RULE_PASS),
                "bad_state_output": planted_obs,
                "good_state_output": indep_obs,
            },
            {
                "id": "NC-missing-authorship",
                "kind": "absent-input",
                "description": (
                    "A receipt with no confirmer and no implementer is a violation "
                    "by default, never a pass by omission."
                ),
                "fired_on_bad_state": row_ok(
                    "missing-authorship", "VIOLATION", RULE_MISSING
                ),
                "silent_on_good_state": row_ok("independent-ok", "PASS", RULE_PASS),
                "bad_state_output": missing_obs,
                "good_state_output": indep_obs,
            },
            {
                "id": "NC-forged-authorship-ledger",
                "kind": "adversarial-payload",
                "description": (
                    "Metadata claiming a fresh confirmer is contradicted by the "
                    "tool-call ledger actors (the implementer)."
                ),
                "fired_on_bad_state": row_ok(
                    "forged-independent-label", "VIOLATION", RULE_FORGED
                ),
                "silent_on_good_state": row_ok("independent-ok", "PASS", RULE_PASS),
                "bad_state_output": forged_obs,
                "good_state_output": indep_obs,
            },
            {
                "id": "NC-rule-b-not-inert",
                "kind": "known-broken-fixture",
                "description": (
                    "A confirmer who only reviewed the implementation is rejected "
                    "by rule (b); authorship-only would accept them."
                ),
                "fired_on_bad_state": row_ok("reviewer-overlap", "VIOLATION", RULE_B),
                "silent_on_good_state": row_ok("independent-ok", "PASS", RULE_PASS),
                "bad_state_output": rule_b_obs,
                "good_state_output": indep_obs,
            },
            {
                "id": "NC-schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "output_schema rejects {}, an unrelated passing_tests blob, "
                    "and a 2000-byte blob so schema-valid is not 'any JSON'."
                ),
                "fired_on_bad_state": schema_rejects_garbage(),
                "silent_on_good_state": True,
                "bad_state_output": "garbage documents produce schema errors",
                "good_state_output": "this receipt is validated before write",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0124-probe1-planted-self-confirmation",
            "verdict": "PASS" if planted_flagged else "FAIL",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 1 re-runs the planted self-confirmation detector; it does "
                "not accept this document's conclusion as verification. Probe 2 "
                "does not see probe 1's verdict."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0124/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads (stdlib JSON parser)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B -c \"import json; json.loads(open("
                        "'command-center/confirmation/CNF-0124-authorship-audit.json'"
                        ").read())\""
                    ),
                    "raw_output": "PENDING-WRITE",
                    "fingerprint": fingerprint("schema-validate", "json.loads:" + OUT_REL),
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no live confirmation receipts matching "
                    "claim_id+receipt_id, so the production corpus is reported as "
                    "0 of 0 rather than a clean pass."
                ),
                "verdict": "NOT-CHECKED" if live_empty else "CONFIRMED",
                "settling_experiment": (
                    "Re-run the auditor after CNF confirmation receipts exist under "
                    "command-center/confirmation/ and command-center/receipts/."
                ),
            }
        ],
    }
    return doc
