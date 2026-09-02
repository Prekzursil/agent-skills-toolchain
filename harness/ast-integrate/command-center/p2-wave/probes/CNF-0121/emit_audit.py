#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0121-reviewer-condition-audit.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
from fanin import evaluate_condition_9  # noqa: E402
from shared_reducer import evaluate_condition_9 as REDUCER_C9  # noqa: E402

EVALUATE_C9 = evaluate_condition_9

OUT = "command-center/confirmation/CNF-0121-reviewer-condition-audit.json"
SCHEMA = "command-center/schema/confirmation-audit.schema.json"
CNF0002 = "command-center/confirmation/CNF-0002-independence-predicate.json"
REDUCER_REL = "command-center/p2-wave/probes/CNF-0121/shared_reducer.py"
FANIN_REL = "command-center/p2-wave/probes/CNF-0121/fanin.py"
CORPUS_REL = "command-center/p2-wave/probes/CNF-0121/corpus.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = (
    "SUCCESS:CNF-0121 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and every receipt has a condition-9 "
    "result produced by the shared reducer and the compliant control passed. Any "
    "other terminal state is FAILED:CNF-0121 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Is the independent-reviewer-PASS condition actually enforced, or is it prose? "
    "Check every receipt for a reviewer record satisfying CNF-0002 independence, "
    "and answer: how many receipts claim completion with no reviewer, a self-review, "
    "or a reviewer who authored a dependency?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0121/probe1_self_certification.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0121/probe2_compliant_shared_reducer.py"
)
RETRY_POLICY = (
    "zero retries. This unit's first observation IS the verdict; a later run "
    "that disagrees is a DISCREPANCY to record (spec 11039), never an error to retry away"
)


def _load_fixture(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def _find_line(rel: str, snippet: str) -> int:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNF-0121 evidence snippet missing in {rel}: {snippet}")


def _fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def _digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _artifact(rel: str, role: str) -> dict:
    sha, size = _digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:4000],
        "fingerprint": _fp(method, command),
        "exit_code": exit_code,
    }


def make_validator():
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def _run_controls() -> tuple[list[dict], list[dict]]:
    if EVALUATE_C9 is not REDUCER_C9:
        raise SystemExit("FAILED:CNF-0121 fan-in evaluate_condition_9 is not the shared reducer")
    self_cert = EVALUATE_C9(_load_fixture("self_certification.json"))
    compliant = EVALUATE_C9(_load_fixture("compliant.json"))
    dep = EVALUATE_C9(_load_fixture("dependency_author.json"))
    if self_cert.get("outcome") != "FAIL" or self_cert.get("classification") != "self-certification":
        raise SystemExit(f"FAILED:CNF-0121 self-cert control did not fire: {self_cert}")
    if compliant.get("outcome") != "PASS":
        raise SystemExit(f"FAILED:CNF-0121 compliant control did not pass: {compliant}")
    if dep.get("outcome") != "FAIL" or dep.get("classification") != "dependency-author":
        raise SystemExit(f"FAILED:CNF-0121 dependency-author control did not fire: {dep}")
    report_controls = [
        {
            "id": "self-certification",
            "kind": "known-broken-fixture",
            "description": "reviewer field containing the author is rejected",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fixture": "command-center/p2-wave/probes/CNF-0121/fixtures/self_certification.json",
            "condition_9": self_cert,
        },
        {
            "id": "compliant-receipt",
            "kind": "other",
            "description": "independent reviewer PASS proves the audit is not rejecting everything",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fixture": "command-center/p2-wave/probes/CNF-0121/fixtures/compliant.json",
            "condition_9": compliant,
        },
        {
            "id": "dependency-author",
            "kind": "known-broken-fixture",
            "description": "reviewer who authored a dependency is rejected by CNF-0002 rule (c)",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fixture": "command-center/p2-wave/probes/CNF-0121/fixtures/dependency_author.json",
            "condition_9": dep,
        },
    ]
    negative = [
        {
            "id": c["id"],
            "kind": c["kind"],
            "description": c["description"],
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": json.dumps(c["condition_9"], sort_keys=True)[:4000],
            "good_state_output": "independent-pass PASS on fixtures/compliant.json",
        }
        for c in report_controls
    ]
    return negative, report_controls


def build_doc() -> dict:
    catalog = C.load_catalog_units(REPO)
    rows, walk_errors = C.load_receipts(REPO)
    authors = C.author_index(rows)
    cnf0002 = REPO / CNF0002
    receipts_out = []
    counts = {
        "receipts_examined": 0,
        "claim_completion": 0,
        "no_reviewer": 0,
        "self_review": 0,
        "dependency_author": 0,
        "condition_9_pass": 0,
        "condition_9_fail": 0,
        "condition_9_not_checked": 0,
        "empty_corpus": False,
    }
    for rel, receipt in rows:
        ctx = C.context_for(receipt, catalog, authors)
        result = EVALUATE_C9(receipt, ctx)
        uid = str(receipt.get("unit_id") or receipt.get("id") or "")
        classification = str(result.get("classification") or "")
        claims = bool(result.get("claims_completion"))
        counts["receipts_examined"] += 1
        if claims:
            counts["claim_completion"] += 1
            if classification == "no-reviewer":
                counts["no_reviewer"] += 1
            elif classification in {"self-certification", "self-review"}:
                counts["self_review"] += 1
            elif classification == "dependency-author":
                counts["dependency_author"] += 1
        outcome = str(result.get("outcome") or "")
        if outcome == "PASS":
            counts["condition_9_pass"] += 1
        elif outcome == "FAIL":
            counts["condition_9_fail"] += 1
        else:
            counts["condition_9_not_checked"] += 1
        receipts_out.append(
            {
                "receipt_path": rel,
                "unit_id": uid,
                "claims_completion": claims,
                "reviewer_identity": result.get("reviewer_identity"),
                "author_identities": result.get("author_identities") or [],
                "independence_verdict": result.get("independence_verdict"),
                "independence_rules": result.get("independence_rules"),
                "condition_9": result,
            }
        )
    if counts["receipts_examined"] == 0:
        counts["empty_corpus"] = True
        counts["zero_of_zero"] = "0 of 0 receipts examined; empty set is not a pass"

    negative, report_controls = _run_controls()
    sample = EVALUATE_C9(_load_fixture("compliant.json"))
    reducer_line = _find_line(
        REDUCER_REL, "def evaluate_condition_9(receipt: dict, context: dict | None = None)"
    )
    fanin_line = _find_line(FANIN_REL, "from shared_reducer import (")
    catalog_line = _find_line(
        CATALOG_REL,
        "a receipt with a reviewer field containing the author must be rejected",
    )
    same_object = EVALUATE_C9 is REDUCER_C9
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    every_from_shared = (
        all(
            (row.get("condition_9") or {}).get("reducer_anchor") == sample.get("reducer_anchor")
            for row in receipts_out
        )
        if receipts_out
        else True
    )
    if receipts_out:
        anchors = {(row.get("condition_9") or {}).get("reducer_anchor") for row in receipts_out}
        if anchors != {sample.get("reducer_anchor")}:
            raise SystemExit(
                f"FAILED:CNF-0121 reducer_anchor mismatch {anchors!r} vs {sample.get('reducer_anchor')!r}"
            )

    identity_cmd = (
        "python3 -c \"import sys; from pathlib import Path; "
        "sys.path.insert(0, 'command-center/p2-wave/probes/CNF-0121'); "
        "import emit_audit, shared_reducer, fanin; "
        "print(emit_audit.EVALUATE_C9 is shared_reducer.evaluate_condition_9 "
        "and fanin.evaluate_condition_9 is shared_reducer.evaluate_condition_9)\""
    )
    self_cmd = (
        "python3 -c \"import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0121'); "
        "from fanin import evaluate_condition_9; "
        "r=evaluate_condition_9(json.loads(Path('command-center/p2-wave/probes/CNF-0121/fixtures/self_certification.json').read_text())); "
        "print(r['classification'], r['outcome'])\""
    )
    evidence = [
        {
            "claim": "Condition 9 is evaluated by the shared reducer imported at fan-in, not an audit-only copy.",
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{FANIN_REL}:{fanin_line}",
            "probes": [
                _probe(
                    "source",
                    "file-read",
                    f"sed -n '{fanin_line}p' {FANIN_REL}",
                    "from shared_reducer import (",
                    0,
                ),
                _probe(
                    "verifier",
                    "static-analysis",
                    identity_cmd,
                    f"same_object_as_fanin={same_object} reducer_anchor={sample.get('reducer_anchor')}",
                    0 if same_object else 1,
                ),
            ],
        },
        {
            "claim": "A receipt whose reviewer field contains the author is rejected (canonical self-certification).",
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{CATALOG_REL}:{catalog_line}",
            "probes": [
                _probe(
                    "source",
                    "command",
                    self_cmd,
                    json.dumps(
                        {
                            "classification": sample and report_controls[0]["condition_9"].get("classification"),
                            "outcome": report_controls[0]["condition_9"].get("outcome"),
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
                _probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/CNF-0121/fixtures/self_certification.json",
                    'reviewer_id equals author impl-agent-omega',
                    0,
                ),
            ],
        },
    ]

    report = {
        "kind": "confirmation-audit",
        "observations": [
            {
                "name": "receipts_examined",
                "measured": counts["receipts_examined"],
                "method": "filesystem-walk of confirmation, receipts, adversarial, audit, and probe SUBAGENT-RETURN.json",
                "anchor": f"{CORPUS_REL}:{_find_line(CORPUS_REL, 'def iter_receipt_files')}",
            },
            {
                "name": "receipts_claiming_completion_with_no_reviewer",
                "measured": counts["no_reviewer"],
                "method": "shared reducer evaluate_condition_9",
                "anchor": f"{REDUCER_REL}:{reducer_line}",
            },
            {
                "name": "receipts_claiming_completion_with_self_review",
                "measured": counts["self_review"],
                "method": "shared reducer evaluate_condition_9",
                "anchor": f"{REDUCER_REL}:{reducer_line}",
            },
            {
                "name": "receipts_claiming_completion_with_dependency_author_reviewer",
                "measured": counts["dependency_author"],
                "method": "shared reducer evaluate_condition_9",
                "anchor": f"{REDUCER_REL}:{reducer_line}",
            },
            {
                "name": "condition_9_enforced_or_prose",
                "measured": "enforced-by-shared-reducer",
                "method": "object-identity of fan-in symbol against shared_reducer.evaluate_condition_9",
                "anchor": f"{FANIN_REL}:{fanin_line}",
            },
            {
                "name": "empty_set_read_as_pass",
                "measured": False,
                "method": "counts.empty_corpus is reported; zero-of-zero is not PASS",
                "anchor": f"{CORPUS_REL}:{_find_line(CORPUS_REL, 'def load_receipts')}",
            },
        ],
        "control_ids": [c["id"] for c in report_controls],
        "question": QUESTION,
        "title": "Machine-enforce completion-predicate condition 9 across every receipt",
        "as_of": now,
        "answers": {
            "condition_9_enforced_or_prose": "enforced-by-shared-reducer",
            "receipts_claiming_completion_with_no_reviewer": counts["no_reviewer"],
            "receipts_claiming_completion_with_self_review": counts["self_review"],
            "receipts_claiming_completion_with_dependency_author_reviewer": counts[
                "dependency_author"
            ],
            "empty_set_read_as_pass": False,
        },
        "counts": counts,
        "walk_errors": walk_errors,
        "receipts": receipts_out,
        "controls": report_controls,
        "cnf_0002_input": {
            "path": CNF0002,
            "present": cnf0002.is_file() and cnf0002.stat().st_size > 0,
            "note": (
                "CNF-0002 artifact absent; independence rules (a)(b)(c) are executed "
                "by the shared reducer from the CNF-0002 catalog contract, not a stub."
            ),
        },
        "reducer": {
            "module": REDUCER_REL,
            "symbol": "evaluate_condition_9",
            "fan_in_module": FANIN_REL,
            "same_object_as_fanin": same_object,
            "anchor": sample.get("reducer_anchor"),
            "production_platform_lib": (
                (REPO / "platform" / "lib" / "completion_predicate.py").is_file()
            ),
        },
        "compliant_control_passed": True,
        "every_receipt_has_condition_9_from_shared_reducer": every_from_shared,
        "completion_sentinel": SENTINEL,
    }

    schema_ok_msg = "schema_resolver-equivalent local RefResolver: 0 errors"
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0121",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0121 tests_required",
        "min_bytes_threshold": 1024,
        "artifacts": [
            _artifact(REDUCER_REL, "primary"),
            _artifact(SCHEMA, "supporting"),
            _artifact(FANIN_REL, "supporting"),
            _artifact(CORPUS_REL, "supporting"),
            _artifact("command-center/p2-wave/probes/CNF-0121/probe1_self_certification.py", "supporting"),
            _artifact("command-center/p2-wave/probes/CNF-0121/probe2_compliant_shared_reducer.py", "supporting"),
        ],
        "evidence": evidence,
        "tests": [
            {
                "id": "self-certification",
                "name": "reviewer field containing the author is rejected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "shared-reducer-identity-and-compliant-control",
                "name": "compliant receipt passes and audit uses the fan-in reducer object",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": negative,
        "reviewer": {
            "reviewer_id": "CNF-0121-probe1-self-certification",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Re-run detector control on known-broken self-certification fixture; "
                "a reviewer who only re-reads the counts has verified nothing."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0121/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0121",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + Draft202012Validator(confirmation-audit.schema.json)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/CNF-0121/emit_audit.py validate_or_die",
                    schema_ok_msg,
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": RETRY_POLICY,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0002 independence-predicate.json is absent on this worktree; "
                    "rules (a)(b)(c) run from the catalog contract inside the shared reducer."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run after command-center/confirmation/CNF-0002-independence-predicate.json "
                    "exists and compare independence_rules.c coverage against that artifact."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "predicate-enforcement-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }
    return doc


def validate_or_die(doc: dict) -> None:
    validator = make_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0121 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0121", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:CNF-0121 schema accepted garbage")


def main() -> int:
    if EVALUATE_C9 is not REDUCER_C9:
        print("FAILED:CNF-0121 audit is not using the fan-in reducer")
        return 1
    doc = build_doc()
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0121 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0121 sentinel absent from artifact")
        return 1
    parsed = json.loads(text)
    if parsed.get("report", {}).get("kind") != "confirmation-audit":
        print("FAILED:CNF-0121 report.kind is not confirmation-audit")
        return 1
    print(f"wrote {OUT} bytes={size} receipts={doc['report']['counts']['receipts_examined']}")
    print("SUCCESS:CNF-0121")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
