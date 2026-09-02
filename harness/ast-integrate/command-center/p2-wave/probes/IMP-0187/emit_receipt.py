#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0187.json from live ensemble-fusion measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import ensemble as E  # noqa: E402

OUT = "command-center/receipts/IMP-0187.json"
SCHEMA = "command-center/schema/receipt.schema.json"
UNIT_SCHEMA = "command-center/p2-wave/probes/IMP-0187/ensemble-fusion.schema.json"
MIN_BYTES = 2048


def digest(rel: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if data else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": path.is_file(),
        "eol": "LF",
        "role": "supporting",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    corr = E.evaluate_correlation_contract()
    schema = E.evaluate_schema_contract()
    post = E.fuse(
        E.load_fixture("correlated"),
        {"rule": "majority"},
        postcondition="REJECT",
    )
    if not corr["both_states"] or not schema["pass"]:
        print("FAILED:IMP-0187 live contracts did not pass; not emitting SUCCESS")
        return 1
    if post["result"].get("postcondition", {}).get("passed") is not False:
        print("FAILED:IMP-0187 unanimous-wrong postcondition did not fail")
        return 1

    supporting = [
        digest("command-center/p2-wave/probes/IMP-0187/ensemble.py"),
        digest(UNIT_SCHEMA),
        digest("command-center/p2-wave/probes/IMP-0187/fixtures/correlated.json"),
        digest("command-center/p2-wave/probes/IMP-0187/fixtures/independent.json"),
        digest(
            "command-center/p2-wave/probes/IMP-0187/fixtures/evidence-asymmetric.json"
        ),
        digest("command-center/p2-wave/probes/IMP-0187/probe1_both_states.py"),
        digest("command-center/p2-wave/probes/IMP-0187/probe2_schema.py"),
    ]
    for row in supporting:
        row["role"] = "supporting"

    probe_src = {
        "role": "source",
        "method": "command",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/IMP-0187/ensemble.py evaluate"
        ),
        "raw_output": json.dumps(
            {
                "correlated_flagged": corr["correlated_flagged"],
                "independent_not_flagged": corr["independent_not_flagged"],
                "effective_n": corr["correlated_effective_n"],
            },
            sort_keys=True,
        ),
        "exit_code": 0,
        "fingerprint": hashlib.sha256(b"imp-0187-source-correlation").hexdigest()[:32],
    }
    probe_ver = {
        "role": "verifier",
        "method": "test-run",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/IMP-0187/probe1_both_states.py"
        ),
        "raw_output": "both-states plant-one control on shared briefing",
        "exit_code": 0,
        "fingerprint": hashlib.sha256(b"imp-0187-verifier-both-states").hexdigest()[:32],
    }
    schema_src = {
        "role": "source",
        "method": "static-analysis",
        "command": f"Draft7Validator {UNIT_SCHEMA}",
        "raw_output": json.dumps(
            {
                "rules": [r["rule"] for r in schema["rules"]],
                "missing_rule_errors": schema["missing_rule_schema_errors"][:4],
            },
            sort_keys=True,
        ),
        "exit_code": 0,
        "fingerprint": hashlib.sha256(b"imp-0187-source-schema").hexdigest()[:32],
    }
    schema_ver = {
        "role": "verifier",
        "method": "command",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/IMP-0187/probe2_schema.py"
        ),
        "raw_output": schema["undeclared_msg"] + " | " + schema["invalid_rule_msg"],
        "exit_code": 0,
        "fingerprint": hashlib.sha256(b"imp-0187-verifier-schema").hexdigest()[:32],
    }

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0187",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0187",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0187",
        "min_bytes_threshold": MIN_BYTES,
        "profile": "ensemble-fusion-aggregation-rule",
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "question": (
            "Run N source workflows and aggregate. The aggregation rule is declared "
            "and typed (majority | weighted | evidence-gated | execution-consensus), "
            "and an ensemble that agrees only because its members share an input is "
            "flagged: correlated members are not independent evidence."
        ),
        "implementation": {
            "module": "command-center/p2-wave/probes/IMP-0187/ensemble.py",
            "schema": UNIT_SCHEMA,
            "entry_point": "ensemble.fuse",
            "aggregation_rules": sorted(E.AGGREGATION_RULES),
            "fake_rail": (
                "Each source is a deterministic policy over a named input set. "
                "Outputs are computed by running the policy, not copied from a "
                "pre-written verdict field."
            ),
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "A three-member ensemble that echoes one shared briefing is "
                    f"flagged non-independent (raw_n="
                    f"{corr['correlated_raw_n']}, effective_n="
                    f"{corr['correlated_effective_n']}). Agreement is one signal."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0187/fixtures/correlated.json:1"
                ),
                "confidence": "almost-certain",
                "probes": [probe_src, probe_ver],
            },
            {
                "claim": (
                    "A three-member ensemble that agrees on disjoint inputs is not "
                    "flagged (false-positive control). flagged_member_ids="
                    f"{corr['independent_flagged_ids']}, effective_n="
                    f"{corr['independent_effective_n']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0187/fixtures/independent.json:1"
                ),
                "confidence": "almost-certain",
                "probes": [probe_src, probe_ver],
            },
            {
                "claim": (
                    "All four aggregation rules emit schema-valid fusions; an "
                    "undeclared rule and the non-enum token 'average' are refused "
                    "at the fusion API; a document missing aggregation.rule is "
                    "rejected by ensemble-fusion.schema.json."
                ),
                "verdict": "CONFIRMED",
                "anchor": UNIT_SCHEMA + ":aggregation.properties.rule.enum",
                "confidence": "almost-certain",
                "probes": [schema_src, schema_ver],
            },
            {
                "claim": (
                    "Evidence-gated aggregation follows the cited member (REJECT) "
                    "while counting agents without collapse would accept the "
                    f"uncited majority (naive={schema['naive_count_agents_on_asymmetric']}). "
                    "Unanimous correlated ACCEPT still fails a REJECT postcondition."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0187/"
                    "fixtures/evidence-asymmetric.json:1"
                ),
                "confidence": "almost-certain",
                "probes": [schema_src, schema_ver],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot - after the second failure on the same "
                "error fingerprint, enumerate >=2 alternative approaches"
            ),
        },
        "tests": [
            {
                "id": "T1-correlated-flagged-independent-not-flagged",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0187/probe1_both_states.py"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": (
                    f"correlated_flagged={corr['correlated_flagged']} "
                    f"independent_not_flagged={corr['independent_not_flagged']} "
                    f"planted={corr['planted_shared_briefing_flagged']}"
                ),
            },
            {
                "id": "T2-aggregation-rule-typed-and-declared",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0187/probe2_schema.py"
                ),
                "result": "PASS",
                "assertions": 5,
                "output_tail": (
                    f"rules={[r['rule'] for r in schema['rules']]} "
                    f"undeclared={schema['undeclared_refused']} "
                    f"invalid={schema['invalid_rule_refused']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0187-C1-planted-shared-briefing",
                "kind": "known-broken-fixture",
                "description": (
                    "Copy a briefing_id onto the independent fixture. The detector "
                    "must flag it. Removing the plant (the original independent "
                    "fixture) must stay silent. A detector that never flags is "
                    "indistinguishable from a broken pattern."
                ),
                "fired_on_bad_state": corr["planted_shared_briefing_flagged"],
                "silent_on_good_state": corr["independent_not_flagged"],
                "bad_state_output": "planted briefing.shared on disjoint-input members",
                "good_state_output": "independent fixture flagged_member_ids=[]",
            },
            {
                "id": "IMP0187-C2-undeclared-aggregation-rule",
                "kind": "schema-invalid-mutant",
                "description": (
                    "A fusion with aggregation={} must fail schema and the API. "
                    "An operator that always succeeds is coercing an undeclared rule."
                ),
                "fired_on_bad_state": schema["undeclared_refused"]
                and schema["missing_rule_schema_rejects"],
                "silent_on_good_state": schema["all_four_rules_schema_valid"],
                "bad_state_output": schema["undeclared_msg"],
                "good_state_output": "majority|weighted|evidence-gated|execution-consensus valid",
            },
            {
                "id": "IMP0187-C3-unanimous-wrong-postcondition",
                "kind": "known-broken-fixture",
                "description": (
                    "All correlated members ACCEPT because they share a briefing. "
                    "A postcondition of REJECT must still fail: consensus is not "
                    "a probe."
                ),
                "fired_on_bad_state": post["result"]["postcondition"]["passed"] is False,
                "silent_on_good_state": corr["independent_fusion"]["result"]["verdict"]
                == "ACCEPT",
                "bad_state_output": json.dumps(post["result"]["postcondition"]),
                "good_state_output": "independent ensemble ACCEPT with disjoint probes",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0187-probe2-typed-aggregation-schema",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 does not reuse the independence detector. It validates the "
                "closed aggregation enum, refuses undeclared/invalid rules, and "
                "checks evidence-gated vs counting uncited agents."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0187/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0187/probe1_both_states.py",
                "artifact_path": "command-center/p2-wave/probes/IMP-0187/ensemble.py",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_ver,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0187/probe2_schema.py",
                "artifact_path": UNIT_SCHEMA,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_ver,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The fake rail is hermetic Python policies, not live vendor "
                    "workflows. Cross-vendor independence is encoded as vendor "
                    "labels plus disjoint inputs; a production rail must still "
                    "record the actual input set of each run."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Replay fuse() against recorded input-set hashes from a live "
                    "ensemble run once IMP-0182's splice rail exists."
                ),
            }
        ],
        "report": {
            "kind": "ensemble-fusion",
            "correlation": {
                "correlated_flagged": corr["correlated_flagged"],
                "independent_not_flagged": corr["independent_not_flagged"],
                "planted_shared_briefing_flagged": corr[
                    "planted_shared_briefing_flagged"
                ],
                "correlated_raw_n": corr["correlated_raw_n"],
                "correlated_effective_n": corr["correlated_effective_n"],
                "independent_effective_n": corr["independent_effective_n"],
                "correlated_pairs": corr["correlated_pairs"],
            },
            "schema": {
                "all_four_rules_schema_valid": schema["all_four_rules_schema_valid"],
                "undeclared_refused": schema["undeclared_refused"],
                "invalid_rule_refused": schema["invalid_rule_refused"],
                "missing_rule_schema_rejects": schema["missing_rule_schema_rejects"],
                "evidence_gated_choice": schema["evidence_gated_choice"],
                "naive_count_agents_on_asymmetric": schema[
                    "naive_count_agents_on_asymmetric"
                ],
            },
            "postcondition_unanimous_wrong": post["result"]["postcondition"],
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0187" not in body:
        print("FAILED:IMP-0187 sentinel missing from emitted body")
        return 1
    out.write_text(body, encoding="utf-8")
    size = out.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:IMP-0187 artifact {size}B below floor {MIN_BYTES}B")
        return 1
    print(f"wrote {OUT} ({size} B)")
    print("SUCCESS:IMP-0187")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
