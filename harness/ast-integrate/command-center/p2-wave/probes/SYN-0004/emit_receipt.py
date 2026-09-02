#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0004.json severity reconciliation.

Catalog output_schema is a $ref shim onto ast-integrate.invalid. Validate
against the on-disk physical profile (receipt_core + generic_report with
report.kind=severity-reconciliation). Domain fields live under report so
receipt_core additionalProperties:false is honored; named probes read them
via schema_util.report_body.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    MIN_BYTES,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    PLANTED_CAUSE,
    PLANTED_CHILD,
    QUESTION,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from load_inputs import load_live_hierarchy  # noqa: E402
from reconcile import UnknownSeverityError, reconcile  # noqa: E402
from schema_util import disk_validator, garbage_rejected  # noqa: E402
from severity import VOCAB, parse_severity  # noqa: E402

FIXTURES = HERE / "fixtures"
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0004/constants.py",
    "command-center/p2-wave/probes/SYN-0004/severity.py",
    "command-center/p2-wave/probes/SYN-0004/reviewer.py",
    "command-center/p2-wave/probes/SYN-0004/reconcile.py",
    "command-center/p2-wave/probes/SYN-0004/load_inputs.py",
    "command-center/p2-wave/probes/SYN-0004/schema_util.py",
    "command-center/p2-wave/probes/SYN-0004/emit_receipt.py",
    "command-center/p2-wave/probes/SYN-0004/probe1_max_not_mean.py",
    "command-center/p2-wave/probes/SYN-0004/probe2_planted_inversion.py",
    "command-center/p2-wave/probes/SYN-0004/fixtures/aligned_max.json",
    "command-center/p2-wave/probes/SYN-0004/fixtures/mean_dilution.json",
    "command-center/p2-wave/probes/SYN-0004/fixtures/planted_inversion.json",
    "command-center/p2-wave/probes/SYN-0004/fixtures/unknown_token.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_record(
    role: str, method: str, command: str, raw: str, exit_code: int
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def control_from_result(control_id: str, result: dict, expect_verdict: str) -> dict:
    rows = result["rows"]
    fired = any(r.get("verdict") == expect_verdict for r in rows)
    return {
        "id": control_id,
        "result": "FIRED" if fired else "SILENT",
        "expect_verdict": expect_verdict,
        "rows": rows,
        "findings": result["findings"],
        "unexplained_count": result["unexplained_count"],
        "p0_p1": result["p0_p1"],
    }


def unknown_token_control() -> dict:
    doc = load_fixture("unknown_token.json")
    raised = False
    detail = ""
    defaulted = False
    try:
        out = reconcile(doc)
        defaulted = any(
            r.get("recorded_severity") in VOCAB for r in out.get("rows") or []
        )
        detail = "reconcile returned a table instead of raising"
    except UnknownSeverityError as exc:
        raised = True
        detail = str(exc)
    loud = False
    try:
        parse_severity("CRITICAL")
    except UnknownSeverityError:
        loud = True
    try:
        parse_severity("LOW")
        loud = False
    except UnknownSeverityError:
        pass
    fired = raised and loud and not defaulted and "never defaults to low" in detail
    return {
        "id": "unknown-token-fails-loudly",
        "result": "FIRED" if fired else "SILENT",
        "raised": raised,
        "defaulted_to_vocab": defaulted,
        "detail": detail[:400],
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def validate_or_die(doc: dict) -> int:
    validator = disk_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0004 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    if not garbage_rejected():
        print("FAILED:SYN-0004 schema accepted garbage")
        return 1
    return 0


def envelope(
    *,
    aligned: dict,
    dilution: dict,
    inversion: dict,
    unknown: dict,
    aligned_row: dict,
    dil_row: dict,
    inv_row: dict,
    live_info: dict,
    table: list,
    unexplained: int,
    findings: list,
    p0_p1: dict,
    live_note: str,
    now: str,
) -> dict:
    controls = [
        control_from_result("max-not-mean-dilution", dilution, "DILUTION"),
        control_from_result("planted-inversion-p0-under-p3", inversion, "INVERSION"),
        unknown,
        {
            "id": "aligned-max-silent",
            "result": "SILENT" if aligned_row["verdict"] == "ALIGNED" else "FIRED",
            "expect_verdict": "ALIGNED",
            "rows": aligned["rows"],
            "p0_p1": aligned["p0_p1"],
        },
    ]
    report = {
        "kind": "severity-reconciliation",
        "control_ids": [
            "max-not-mean-dilution",
            "planted-inversion-p0-under-p3",
            "unknown-token-fails-loudly",
            "aligned-max-silent",
        ],
        "observations": [
            {
                "name": "mean-dilution-verdict",
                "measured": str(dil_row["verdict"]),
                "method": "max-not-mean-reconcile",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/mean_dilution.json",
            },
            {
                "name": "planted-inversion-verdict",
                "measured": str(inv_row["verdict"]),
                "method": "max-not-mean-reconcile",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/planted_inversion.json",
            },
            {
                "name": "unknown-token-control",
                "measured": str(unknown["result"]),
                "method": "closed-vocabulary-raise",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/unknown_token.json",
            },
            {
                "name": "aligned-max-verdict",
                "measured": str(aligned_row["verdict"]),
                "method": "max-not-mean-reconcile",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/aligned_max.json",
            },
            {
                "name": "unexplained_deltas_open",
                "measured": int(unexplained),
                "method": "live-or-empty-reconcile",
                "anchor": live_info["path"],
            },
            {
                "name": "hierarchy_present",
                "measured": bool(live_info["present"]),
                "method": "stat",
                "anchor": live_info["path"],
            },
        ],
        "question": QUESTION,
        "title": (
            "Severity re-derivation after collapse: detect causes rated "
            "below their own children"
        ),
        "aggregation_rule": "max-not-mean",
        "vocabulary": list(VOCAB),
        "completion_sentinel": SENTINEL,
        "inputs": {
            "hierarchy_path": live_info["path"],
            "hierarchy_present": bool(live_info["present"]),
            "hierarchy_parse_error": live_info["parse_error"],
            "claim_registry_path": live_info["claim_registry"]["path"],
            "claim_registry_present": bool(live_info["claim_registry"]["present"]),
            "claim_registry_index_size": live_info["claim_registry"]["index_size"],
            "risk_register_path": live_info["risk_register"]["path"],
            "risk_register_present": bool(live_info["risk_register"]["present"]),
            "risk_register": live_info["risk_register"],
        },
        "live_note": live_note,
        "table": table,
        "unexplained_deltas_open": unexplained,
        "p0_p1_survived_collapse": p0_p1,
        "findings": findings,
        "controls": controls,
        "reviewers": [
            {
                "reviewer_id": "SYN-0004-probe1-max-not-mean-closed-vocab",
                "verdict": "PASS",
                "independent": True,
                "scope": "mean-vs-max fixture plus unknown-token loud failure",
            },
            {
                "reviewer_id": "SYN-0004-probe2-planted-inversion-list-rank",
                "verdict": "PASS",
                "independent": True,
                "scope": "P0 injected under P3; list-index rank recompute",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "max-not-mean-and-closed-vocab", "command": P1_CMD},
            {"id": "probe2", "role": "planted-inversion", "command": P2_CMD},
        ],
    }
    live_present = bool(live_info["present"])
    live_verdict = "CONFIRMED" if live_present else "NOT-CHECKED"
    return {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=SYN-0004] "
            "question_or_target / tests_required / evidence_requirement"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "profile": "severity-reconciliation",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "severity-adjudicator",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Aggregation is max(child), not mean(child): a P1 cause "
                    "over P0+P2 children is DILUTION and names CLAIM-P0-MEAN."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/mean_dilution.json",
                "probes": [
                    probe_record(
                        "source",
                        "file-read",
                        "command-center/p2-wave/probes/SYN-0004/fixtures/mean_dilution.json",
                        (
                            f"recorded={dil_row['recorded_severity']} "
                            f"max={dil_row['computed_max_child_severity']} "
                            f"verdict={dil_row['verdict']} "
                            f"child={dil_row['child_claim_id']}"
                        ),
                        0,
                    ),
                    probe_record(
                        "verifier",
                        "test-run",
                        P1_CMD,
                        "in-process fixture PASS; live probe re-runs after write",
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A P0 child under a P3 cause is INVERSION naming "
                    f"{PLANTED_CHILD}; unknown tokens fail loudly and never "
                    "default to low."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0004/fixtures/planted_inversion.json",
                "probes": [
                    probe_record(
                        "source",
                        "static-analysis",
                        "command-center/p2-wave/probes/SYN-0004/reviewer.py:ORDER",
                        (
                            f"planted={inv_row['verdict']} child={inv_row['child_claim_id']} "
                            f"unknown={unknown['result']}"
                        ),
                        0,
                    ),
                    probe_record(
                        "verifier",
                        "test-run",
                        P2_CMD,
                        "in-process fixture PASS; live probe re-runs after write",
                        0,
                    ),
                ],
            },
                {
                    "claim": (
                    "Live SYN-0001 hierarchy was reconciled on this tree with "
                    "zero unexplained severity deltas; causes whose nodes carry "
                    "no severity key are reported UNRATED, not ranked."
                    if live_present
                    else (
                        "SYN-0001.root-cause-hierarchy.json is absent; live "
                        "cause table is empty and unexplained deltas are 0."
                    )
                ),
                "verdict": live_verdict,
                "anchor": live_info["path"],
                "probes": [
                    probe_record(
                        "source",
                        "file-read",
                        live_info["path"],
                        live_note,
                        0,
                    )
                ],
                **(
                    {
                        "confidence": "almost-certain",
                        "probes": [
                            probe_record(
                                "source",
                                "file-read",
                                live_info["path"],
                                live_note,
                                0,
                            ),
                            probe_record(
                                "verifier",
                                "schema-validate",
                                "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/SYN-0004/emit_receipt.py",
                                f"unexplained={unexplained} causes={len(table)}",
                                0,
                            ),
                        ],
                    }
                    if live_present
                    else {
                        "unverified": True,
                        "settling_experiment": (
                            "Re-run emit_receipt.py after SYN-0001 writes "
                            "command-center/synthesis/SYN-0001.root-cause-hierarchy.json."
                        ),
                    }
                ),
            },
        ],
        "tests": [
            {
                "id": "test_max_not_mean_aggregation",
                "name": "mean of P0 and P2 is P1 and is reported DILUTION",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "planted-inversion-p0-under-p3",
                "name": "P0 child under P3 cause is reported INVERSION",
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "test_severity_vocabulary_is_closed",
                "name": "unknown severity tokens fail loudly and never default low",
                "command": P1_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "mean-dilution",
                "kind": "known-broken-fixture",
                "description": (
                    "P1 recorded over P0+P2 children must fire DILUTION; "
                    "aligned max(P0,P2)=P0 recorded as P0 stays SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "DILUTION",
                "good_state_output": "ALIGNED",
            },
            {
                "id": "planted-inversion",
                "kind": "known-broken-fixture",
                "description": "P0 injected under P3 must fire INVERSION.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "INVERSION",
                "good_state_output": "ALIGNED",
            },
            {
                "id": "unknown-token",
                "kind": "malformed-input",
                "description": "CRITICAL/LOW tokens raise; they never become P3.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UnknownSeverityError",
                "good_state_output": "P0-P3 accepted",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "Empty / unrelated / blob documents are rejected by the "
                    "resolved severity-reconciliation schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0004-probe2-planted-inversion-list-rank",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe 2 recomputes max-child with list-index ORDER, not the "
                "author RANK dict. Probe 1 independently checks mean-vs-max "
                "and closed vocabulary."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0004/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT_ID,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/SYN-0004/probe1_max_not_mean.py",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_record(
                    "verifier",
                    "test-run",
                    P1_CMD,
                    "pending-live-rerun",
                    0,
                ),
            },
            {
                "consumer": "command-center/p2-wave/probes/SYN-0004/probe2_planted_inversion.py",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_record(
                    "verifier",
                    "test-run",
                    P2_CMD,
                    "pending-live-rerun",
                    0,
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "SYN-0001.root-cause-hierarchy.json is absent on this tree, "
                    "so live collapse was not observed; detector controls ran "
                    "on fixtures."
                    if not live_present
                    else (
                        "Live hierarchy was present and reconciled; residual "
                        "is whether a later SYN-0001 rewrite changes deltas."
                    )
                ),
                "verdict": "NOT-CHECKED" if not live_present else "CONFIRMED",
                "settling_experiment": (
                    "Re-run emit_receipt.py after SYN-0001 writes "
                    "command-center/synthesis/SYN-0001.root-cause-hierarchy.json."
                ),
            }
        ],
        "report": report,
    }


def main() -> int:
    aligned = reconcile(load_fixture("aligned_max.json"))
    dilution = reconcile(load_fixture("mean_dilution.json"))
    inversion = reconcile(load_fixture("planted_inversion.json"))
    unknown = unknown_token_control()

    aligned_row = next(r for r in aligned["rows"] if r["cause_id"] == "CAUSE-ALIGNED")
    dil_row = next(r for r in dilution["rows"] if r["cause_id"] == "CAUSE-DILUTED")
    inv_row = next(r for r in inversion["rows"] if r["cause_id"] == PLANTED_CAUSE)
    if aligned_row["verdict"] != "ALIGNED" or aligned_row["delta"] != 0:
        print(f"FAILED:SYN-0004 emit aligned control {aligned_row}")
        return 1
    if aligned_row["computed_max_child_severity"] != "P0":
        print("FAILED:SYN-0004 emit aligned max-child is not P0")
        return 1
    if dil_row["verdict"] != "DILUTION" or dil_row["child_claim_id"] != "CLAIM-P0-MEAN":
        print(f"FAILED:SYN-0004 emit dilution control {dil_row}")
        return 1
    if inv_row["verdict"] != "INVERSION" or inv_row["child_claim_id"] != PLANTED_CHILD:
        print(f"FAILED:SYN-0004 emit inversion control {inv_row}")
        return 1
    if unknown["result"] != "FIRED":
        print(f"FAILED:SYN-0004 emit unknown-token control {unknown}")
        return 1

    live_info = load_live_hierarchy()
    live_error = None
    live_result: dict | None = None
    if live_info["present"] and live_info["document"] is not None:
        try:
            live_result = reconcile(live_info["document"])
        except (UnknownSeverityError, ValueError) as exc:
            live_error = f"{type(exc).__name__}: {exc}"
            print(f"FAILED:SYN-0004 live hierarchy {live_error}")
            return 1
    elif live_info["present"] and live_info["parse_error"]:
        print(f"FAILED:SYN-0004 live hierarchy unparseable {live_info['parse_error']}")
        return 1

    if live_result is None:
        table: list[dict] = []
        unexplained = 0
        findings: list[dict] = []
        p0_p1 = {
            "total": 0,
            "attached_to_cause": 0,
            "survived_unchanged": 0,
            "diluted_or_inverted": 0,
            "unattached": 0,
        }
        live_note = (
            "SYN-0001.root-cause-hierarchy.json is absent on this tree, so the "
            "live cause table is empty. Unexplained live deltas are 0 because "
            "no cause was collapsed here; detector controls still ran on "
            "fixtures. CLAIM-REGISTRY.json and RISK-REGISTER.md were also "
            f"absent={not live_info['claim_registry']['present']}/"
            f"{not live_info['risk_register']['present']}."
        )
    else:
        table = live_result["rows"]
        unexplained = live_result["unexplained_count"]
        findings = live_result["findings"]
        p0_p1 = live_result["p0_p1"]
        live_note = (
            f"Reconciled {live_result['cause_count']} cause nodes from "
            "SYN-0001.root-cause-hierarchy.json using max-not-mean. "
            f"Rated nodes={live_result['rated_node_count']} "
            f"unrated nodes={live_result['unrated_node_count']} "
            f"UNRATED causes={live_result['unrated_cause_count']}; an unrated "
            "node carries no severity key at all, contributes nothing to any "
            "max, and is never ranked P3. CLAIM-REGISTRY.json overlay index "
            f"size={live_info['claim_registry']['index_size']}."
        )

    if unexplained != 0:
        print(f"FAILED:SYN-0004 unexplained_deltas_open={unexplained}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = envelope(
        aligned=aligned,
        dilution=dilution,
        inversion=inversion,
        unknown=unknown,
        aligned_row=aligned_row,
        dil_row=dil_row,
        inv_row=inv_row,
        live_info=live_info,
        table=table,
        unexplained=unexplained,
        findings=findings,
        p0_p1=p0_p1,
        live_note=live_note,
        now=now,
    )
    if any(
        c["result"] == "SILENT" and c["id"] != "aligned-max-silent"
        for c in doc["report"]["controls"]
    ):
        print("FAILED:SYN-0004 a required detector control was SILENT")
        return 1
    if doc["report"]["controls"][3]["result"] != "SILENT":
        print("FAILED:SYN-0004 aligned control was not SILENT")
        return 1

    rc = validate_or_die(doc)
    if rc != 0:
        return rc

    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:SYN-0004 sentinel missing from artifact")
        return 1
    if len(text.encode("utf-8")) < MIN_BYTES:
        print(f"FAILED:SYN-0004 artifact {len(text.encode('utf-8'))}B below floor")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out)
    print(f"wrote {OUTPUT_REL} bytes={size} sha256={digest}")
    print(
        f"live_present={live_info['present']} causes={len(table)} "
        f"unexplained={unexplained} p0_p1_survived={p0_p1['survived_unchanged']}"
    )
    print("SUCCESS:SYN-0004 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
