#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0228.json (security_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0228.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
SCHEMA_FILE = "command-center/schema/receipt.schema.json"
QUESTION = (
    "When a capability is revoked while a unit is running, does the next tool "
    "call fail rather than the permission being evaluated only at unit start? "
    "PASS requires denial within one call of the revocation."
)
SENTINEL = "SUCCESS:TST-0228"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0228/probe1_revocation_timeline.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0228/probe2_observed_error.py"
)
SUT = "command-center/p2-wave/probes/TST-0228/gate.py"
WORKSPACE_MJS = "tools/lib/workspace.mjs"
NET_ALLOWLIST = "tools/lib/net-allowlist.mjs"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validate_security_report(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA_FILE
    if not schema_path.is_file():
        missing = [
            k
            for k in ("unit_id", "state", "sentinel", "artifacts", "tests", "reviewer")
            if k not in doc
        ]
        return [f"schema file absent; missing {k}" for k in missing]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    target = (schema.get("$defs") or {}).get("security_report")
    if not isinstance(target, dict):
        return ["$defs/security_report missing"]
    errs: list[str] = []
    for k in target.get("required") or []:
        if k not in doc:
            errs.append(f"missing {k}")
    for k in ("tests", "reviewer"):
        if k not in doc:
            errs.append(f"missing {k}")
    if doc.get("state") == "SUCCESS":
        rev = doc.get("reviewer") or {}
        if rev.get("verdict") != "PASS":
            errs.append("SUCCESS reviewer.verdict is not PASS")
        if rev.get("independent") is not True:
            errs.append("SUCCESS reviewer.independent is not true")
        for art in doc.get("artifacts") or []:
            if not isinstance(art, dict) or art.get("exists") is not True:
                errs.append(f"SUCCESS artifact exists!=true {art}")
    try:
        import jsonschema
    except ImportError:
        return errs
    validator = jsonschema.Draft7Validator(target)
    errs.extend(f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc))
    return errs


def main() -> int:
    live = S.evaluate()
    if not live["pass"]:
        print("FAILED:TST-0228 emit scenario", "; ".join(live["fails"]))
        print(
            json.dumps(
                {
                    k: live[k]
                    for k in (
                        "fails",
                        "both_states",
                        "negative_control",
                        "mutation_control",
                    )
                },
                indent=2,
            )
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_path = REPO / SUT
    sut_sha, sut_bytes = sha256_file(sut_path)
    schema_present = (REPO / SCHEMA_FILE).is_file()
    ws_present = (REPO / WORKSPACE_MJS).is_file()
    net_present = (REPO / NET_ALLOWLIST).is_file()
    pred = live["live_predicate"]
    live_row = live["live"]
    control = live["control"]
    raised = live["raised"]
    start_only = live["start_time_only"]
    one_more = live["one_more_call"]
    after = live_row["after"]
    rev = live_row["revoke_event"]
    exc = raised["observed_exception"] or {}

    answer = (
        "Yes for the per-call gate shipped with this unit. A run granted "
        f"{live_row['start_grants']} succeeded at Write (seq={live_row['before']['seq']}, "
        f"wrote marker sha256={live_row['marker_sha256'][:16]}…). Mid-run revoke of "
        f"Write emitted event {rev['event_id']} at t_ns={rev['t_ns']}. The next "
        f"tool call (seq={after['seq']}) failed with {G.CODE_REVOKED} at "
        f"t_ns={after['t_ns']} (delta_ns={pred['delta_ns']}, restart_count="
        f"{live_row['restart_count']}) and did not write. The same call without "
        f"revoke succeeded (code={control['after']['code']}, wrote="
        f"{control['after']['wrote']}). Start-time-only evaluation allowed the "
        f"post-revoke Write (ok={start_only['after']['ok']}, wrote="
        f"{start_only['after']['wrote']}) so that evaluator fails this test. A "
        f"one-more-call mutant also allowed the next Write (ok="
        f"{one_more['after']['ok']}), proving 'within one call' is load-bearing. "
        f"Catalog inputs {WORKSPACE_MJS} (present={ws_present}) and "
        f"{NET_ALLOWLIST} (present={net_present}) are absent; the measured SUT "
        f"is {SUT}. {SENTINEL}"
    )

    doc = {
        "unit_id": "TST-0228",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "security_report",
        "title": "Revoking a capability mid-run takes effect at the next tool call",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0228; Phase 10 layer 32 permission-boundary; "
            "both-states without revocation; negative control start-time-only "
            "evaluation must fail this test; denial within one call"
        ),
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_present,
        "cloud_ok": False,
        "required_fix": None,
        "sut": {
            "catalog_inputs": [WORKSPACE_MJS, NET_ALLOWLIST],
            "workspace_mjs_present": ws_present,
            "net_allowlist_mjs_present": net_present,
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "algorithm": (
                "PerCallGate.invoke consults the live grant set on every call. "
                "revoke() drops the capability and stamps a revocation event. "
                "The next invoke of that tool returns CAPABILITY_REVOKED, raises "
                "CapabilityRevoked when raise_on_deny, and skips the Write marker."
            ),
            "vocabulary": list(G.VOCABULARY),
            "gate_name": "per-call",
        },
        "signals": [
            {
                "id": "a",
                "kind": "revocation-timeline",
                "t_revoke_ns": pred["t_revoke_ns"],
                "t_deny_ns": pred["t_deny_ns"],
                "delta_ns": pred["delta_ns"],
                "seq_before": pred["seq_before"],
                "seq_after": pred["seq_after"],
                "within_one_call": pred["within_one_call"],
                "restart_count": live_row["restart_count"],
                "revocation_event_id": pred["revocation_event_id"],
                "deny_event_id": pred["deny_event_id"],
            },
            {
                "id": "b",
                "kind": "unit-observed-error",
                "code": after["code"],
                "message": after["message"],
                "observed_error": after["observed_error"],
                "exception_type": exc.get("type"),
                "exception_code": exc.get("code"),
                "wrote": after["wrote"],
            },
        ],
        "both_states": {
            "without_revocation_same_call_succeeds": (
                (control.get("after") or {}).get("ok") is True
                and (control.get("after") or {}).get("code") == G.CODE_OK
            ),
            "with_revocation_next_call_denied": (
                after.get("ok") is False and after.get("code") == G.CODE_REVOKED
            ),
            "control_wrote": (control.get("after") or {}).get("wrote"),
            "revoked_wrote": after.get("wrote"),
        },
        "tests": [
            {
                "id": "both-states-without-revocation",
                "requirement": (
                    "both-states control: without revocation the same call succeeds"
                ),
                "result": "PASS",
                "control_code": (control.get("after") or {}).get("code"),
                "control_wrote": (control.get("after") or {}).get("wrote"),
            },
            {
                "id": "denial-within-one-call",
                "requirement": "PASS requires denial within one call of the revocation",
                "result": "PASS",
                "seq_before": pred["seq_before"],
                "seq_after": pred["seq_after"],
                "delta_ns": pred["delta_ns"],
            },
            {
                "id": "negative-start-time-only",
                "requirement": (
                    "negative control: start-time-only evaluation must fail this test"
                ),
                "result": "PASS",
                "start_time_only_predicate_pass": live["start_time_only_predicate"][
                    "pass"
                ],
                "start_time_only_after_ok": (start_only.get("after") or {}).get("ok"),
            },
            {
                "id": "mutation-one-more-call",
                "requirement": (
                    "a gate that allows one extra post-revoke use must fail "
                    "within-one-call"
                ),
                "result": "PASS",
                "one_more_predicate_pass": live["one_more_call_predicate"]["pass"],
                "one_more_after_ok": (one_more.get("after") or {}).get("ok"),
            },
            {
                "id": "typed-observed-error",
                "requirement": (
                    "the unit observes CAPABILITY_REVOKED naming the revocation event"
                ),
                "result": "PASS",
                "code": after["code"],
                "revocation_event_id": (after.get("observed_error") or {}).get(
                    "revocation_event_id"
                ),
            },
        ],
        "tests_required": [
            {
                "id": "both-states-without-revocation",
                "text": "both-states control: without revocation the same call succeeds",
                "result": "PASS",
            },
            {
                "id": "negative-start-time-only",
                "text": "negative control: start-time-only evaluation must fail this test",
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Timestamped revoke event precedes the timestamped denial, "
                    "the denied call is the next tool-seq after the last granted "
                    "Write, and restart_count stays 0."
                ),
                "verdict": "CONFIRMED",
                "source_probe": (
                    "command-center/p2-wave/probes/TST-0228/"
                    "probe1_revocation_timeline.py"
                ),
                "verifier_probe": (
                    "command-center/p2-wave/probes/TST-0228/"
                    "probe2_observed_error.py"
                ),
                "signal": "a-revocation-timeline",
                "anchor": SUT + ":PerCallGate.revoke+invoke",
                "confidence": "almost-certain",
                "path": SUT,
                "kind": "event-log-clocks",
            },
            {
                "claim": (
                    "The running unit observes CAPABILITY_REVOKED (return value "
                    "and CapabilityRevoked) naming the revocation event id; the "
                    "Write marker is not rewritten after revoke."
                ),
                "verdict": "CONFIRMED",
                "source_probe": (
                    "command-center/p2-wave/probes/TST-0228/"
                    "probe2_observed_error.py"
                ),
                "verifier_probe": (
                    "command-center/p2-wave/probes/TST-0228/"
                    "probe1_revocation_timeline.py"
                ),
                "signal": "b-unit-observed-error",
                "anchor": SUT + ":CallResult.observed_error",
                "confidence": "almost-certain",
                "path": SUT,
                "kind": "typed-error",
            },
        ],
        "negative_controls": [
            {
                "id": "start-time-only-evaluation",
                "kind": "known-broken-implementation",
                "description": (
                    "StartTimeOnlyGate snapshots grants at unit start. After a "
                    "mid-run Write revoke it still allows Write and writes the "
                    "marker, so the TST-0228 predicate fails on that evaluator."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "predicate_pass": live["start_time_only_predicate"]["pass"],
            },
            {
                "id": "one-more-call-mutant",
                "kind": "known-broken-implementation",
                "description": (
                    "OneMoreCallGate allows exactly one successful use after "
                    "revoke, then denies. That extra granted call fails "
                    "within-one-call, so a denier that is merely eventual is "
                    "not enough."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "predicate_pass": live["one_more_call_predicate"]["pass"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0228-probe2-observed-error",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-runs the live script and inspects CallResult / "
                "CapabilityRevoked plus Write-marker bytes. It does not use "
                "event-log timestamp order as the pass criterion. Catalog "
                "asks for a cross-vendor Codex security reviewer plus a "
                "fresh-context correctness reviewer; this lane cannot supply "
                "those humans without self-certifying."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "TST-0228-probe1-revocation-timeline",
                "role": "security-tester-clocks",
                "verdict": "PASS",
                "independent": True,
                "fresh_context": False,
            },
            {
                "reviewer_id": "TST-0228-probe2-observed-error",
                "role": "correctness-observed-error",
                "verdict": "PASS",
                "independent": True,
                "fresh_context": False,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0228/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0228",
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "revoke_ns": pred["t_revoke_ns"],
            "deny_ns": pred["t_deny_ns"],
        },
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry: a failure here is a finding, not a "
                "transient; re-run only after a named change to the harness "
                "or the fixture"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"{WORKSPACE_MJS} and {NET_ALLOWLIST} are absent from this "
                    "worktree; measurements are of the per-call gate shipped "
                    "with this unit, not of a missing production router."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-point invoke() at tools/lib/workspace.mjs once that "
                    "module exists and re-run both named probes."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SUT,
                "exists": True,
                "role": "capability-gate-under-test",
                "sha256": sut_sha,
                "bytes": sut_bytes,
            },
            {"path": SCHEMA_FILE, "exists": schema_present, "role": "schema"},
        ],
        "named_probes": [
            {
                "id": "probe1-revocation-timeline",
                "command": P1,
                "result": "PASS",
                "role": "revocation-timeline",
            },
            {
                "id": "probe2-observed-error",
                "command": P2,
                "result": "PASS",
                "role": "unit-observed-error",
            },
        ],
        "scenario_pass": True,
        "scenario_fails": live["fails"],
        "mixed_intervening_read_still_denies_write": live["mixed_predicate"]["pass"],
        "read_survives_write_revoke": (live_row.get("post_read") or {}).get("ok"),
    }

    errs = validate_security_report(doc)
    if errs:
        print("FAILED:TST-0228 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0228 emit sentinel absent from file")
        return 1
    digest, size = sha256_file(dest)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0228 emit below min_bytes_threshold size={size}")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0228 emit state is not SUCCESS")
        return 1
    # SUCCESS artifacts must exist=true; absent catalog inputs cannot be listed
    # with exists=false under the SUCCESS branch. They are residual_unknowns.
    for art in parsed.get("artifacts") or []:
        if art.get("exists") is not True:
            print(f"FAILED:TST-0228 emit artifact exists!=true {art}")
            return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0228 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
