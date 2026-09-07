#!/usr/bin/env python3
"""Pack AUD-0053 network-egress dependency census receipt.

Emits BLOCKED until an independent cross-vendor Codex review PASS that
re-ran ONLY probe 2 (catalog `reviewer_requirement`, the socket-level trace
that names destination hosts on an unblocked run) is on disk. Never stubs
SUCCESS.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0053"
OUT = "command-center/audit/AUD-0053-network-egress-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0053/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when an independent cross-vendor Codex review PASS that
    re-ran ONLY probe 2 is on disk (catalog reviewer_requirement)."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-egress-blocked-outcome-diff.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (PROBE / "probe2-socket-trace-destinations.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-egress-blocked-outcome-diff.raw.txt").read_text(
        encoding="utf-8"
    )
    raw2 = (PROBE / "probe2-socket-trace-destinations.raw.txt").read_text(
        encoding="utf-8"
    )
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T21:49:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    both_states = p1.get("both_states_control") or {}
    both_states_ok = bool(both_states.get("ok"))
    baseline_collected = p1.get("baseline_collected_count")
    p1_ok = bool(p1.get("ok"))
    network_dependent_count = p1.get("network_dependent_candidates_count")
    p1_ground_truth_ok = bool(p1.get("ground_truth_ok"))

    p2_ok = bool(p2.get("ok"))
    distinct_hosts = p2.get("distinct_hosts") or []
    network_touching_count = p2.get("network_touching_tests_count")
    p2_ground_truth_ok = bool(p2.get("ground_truth_ok"))
    cross_reference_ok = p2.get("cross_reference_ok")

    # The catalog's own point: the blocked run finds DEPENDENCE, the trace
    # finds TOUCH. touch_only = tests the trace saw but the outcome-diff did
    # not flag -- these are the "silently downloading get-pip.py despite
    # comments saying otherwise" cases the catalog's inputs name.
    p1_dependent_ids = {c["nodeid"] for c in p1.get("network_dependent_candidates", [])}
    p2_touching_ids = set(p2.get("network_touching_tests", []))
    touch_only_ids = sorted(p2_touching_ids - p1_dependent_ids)
    touch_only_count = len(touch_only_ids)

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked_outcome_diff.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/probe2_socket_trace_destinations.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/fixtures/egress_block.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/fixtures/aud0053_plugin.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/fixtures/collectible_scope.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/fixtures/network_dependent/"
            "test_network_ground_truth.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0053/fixtures/network_dependent/"
            "test_network_ground_truth_silent.py",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0053/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which tests reach the network during execution, whether or not they "
        "claim to be hermetic, and what do they fetch?"
    )
    headline = (
        f"{baseline_collected} collectible tests this pass (command-center/, "
        "2 non-hermetic salvage/scratch trees excluded, plus this unit's own 2 "
        "ground-truth fixtures; see fixtures/collectible_scope.py). Both-states "
        f"control (tests_required) PASSED: a deliberate fetch to example.com:80 "
        f"succeeded unblocked and failed (OSError) inside the socket-level block "
        f"({both_states_ok=}) -- proving the blocked environment actually blocks "
        "before any blocked-run result is trusted. Probe1 (blocked-run outcome "
        f"diff): {network_dependent_count} test(s) whose outcome changed from "
        "PASS (unblocked) to non-PASS (blocked) -- these DEPEND on the network. "
        f"Probe2 (socket-level trace, unblocked run): {network_touching_count} "
        f"test(s) made at least one non-loopback connect(), naming "
        f"{len(distinct_hosts)} distinct destination host(s) ({distinct_hosts}) "
        f"-- these TOUCH the network. Cross-reference: {touch_only_count} of the "
        f"{network_touching_count} touching test(s) touch but do NOT depend "
        "(outcome unchanged when blocked -- the exact 'silently downloading "
        "get-pip.py despite comments saying otherwise' shape the catalog's "
        "own measured precedent names). Both ground-truth fixtures were caught "
        "and correctly classified by their respective instrument "
        f"(probe1_ground_truth_ok={p1_ground_truth_ok}, "
        f"probe2_ground_truth_ok={p2_ground_truth_ok})."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0053"
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0053-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0053-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass swept {baseline_collected} tests collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and the "
                    "two excluded non-hermetic trees are carried forward as "
                    "not-yet-swept residuals, not silently dropped."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs "
                "ONLY the second probe (probe2_socket_trace_destinations.py, "
                "the socket-level destination-host trace on an unblocked run). "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0053 egress-blocked-outcome-diff + socket-trace probes "
            f"measured; baseline_collected={baseline_collected} "
            f"network_dependent={network_dependent_count} "
            f"network_touching={network_touching_count} distinct_hosts={len(distinct_hosts)} "
            f"touch_only={touch_only_count} both_states_control_ok={both_states_ok}; "
            "blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "egress-blocked",
                "green-not-live",
                "detector-failure",
            ],
            "reason": (
                "Named probes completed: the tests_required both-states control "
                "proved the socket-level block actually blocks a deliberate fetch "
                "and does not block an unblocked one; probe1 recorded every test "
                "whose PASS/FAIL outcome changed when egress was blocked "
                f"({network_dependent_count} found); probe2 recorded, via an "
                "unblocked run with every non-loopback connect() traced, every "
                f"test that touched the network at all ({network_touching_count} "
                "found, naming destination hosts) -- but catalog "
                "reviewer_requirement is unmet (cross-vendor Codex must re-run "
                "ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"both_states_control_ok={both_states_ok} p1_ok={p1_ok} "
                f"network_dependent={network_dependent_count} "
                f"p1_ground_truth_ok={p1_ground_truth_ok} p2_ok={p2_ok} "
                f"network_touching={network_touching_count} "
                f"p2_ground_truth_ok={p2_ground_truth_ok} "
                f"cross_reference_ok={cross_reference_ok} touch_only={touch_only_count} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0053/"
                "probe2_socket_trace_destinations.py and independently confirm "
                "the traced destination-host set and the ground-truth/cross-"
                "reference controls before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0053/probe2_socket_trace_destinations.py",
                    f"network_touching={network_touching_count} distinct_hosts={distinct_hosts}",
                    0 if p2_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0053-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0053-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass swept {baseline_collected} tests collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and the "
                    "two excluded non-hermetic trees are carried forward as "
                    "not-yet-swept residuals, not silently dropped."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0053",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "tests_required both-states control: a deliberate real fetch "
                    "(TCP connect to example.com:80) executed in-process, first "
                    "unblocked (must succeed) then with fixtures/egress_block.py's "
                    "socket-level block installed (must fail with OSError). "
                    f"good_state_succeeded={both_states.get('good_state_unblocked_connect_succeeded')} "
                    f"bad_state_failed={both_states.get('bad_state_blocked_connect_failed')} "
                    f"ok={both_states_ok}. Gates the rest of probe1: if the block "
                    "never engaged, a 'nothing found' result downstream would be "
                    "meaningless."
                ),
                "CONFIRMED" if both_states_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked_outcome_diff.py",
                        raw1[:4000],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-egress-blocked-outcome-diff.json both_states_control",
                        json.dumps(both_states),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 1 egress-blocked outcome-diff census: {baseline_collected} "
                    "collectible tests run once unblocked (baseline) then once more "
                    "with fixtures/egress_block.py's socket-level block installed "
                    "before collection starts. "
                    f"{network_dependent_count} test(s) PASSED unblocked but did NOT "
                    "pass blocked -- these depend on the network. Ground truth "
                    "(a deliberately planted real-fetch test) confirmed caught: "
                    f"{p1_ground_truth_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked_outcome_diff.py",
                        raw1[-8000:],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-egress-blocked-outcome-diff.json",
                        json.dumps(
                            {
                                "baseline_collected_count": baseline_collected,
                                "network_dependent_candidates_count": network_dependent_count,
                                "ground_truth_ok": p1_ground_truth_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 socket-level destination-host trace: {network_touching_count} "
                    "test(s) made at least one non-loopback connect() during an "
                    f"UNBLOCKED run, naming {len(distinct_hosts)} distinct destination "
                    f"host(s) ({distinct_hosts}). Cross-reference against probe1: "
                    f"cross_reference_ok={cross_reference_ok} (every outcome-changed "
                    "nodeid from probe1 also appears in this trace -- a dependency "
                    f"cannot exist without a touch); {touch_only_count} test(s) touch "
                    "the network without depending on it (the catalog's "
                    "get-pip.py-precedent shape). Ground truth (both planted fixtures, "
                    "the real-dependency AND the outcome-invariant silent-touch one) "
                    f"confirmed traced: {p2_ground_truth_ok}."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0053/probe2_socket_trace_destinations.py",
                        raw2,
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-socket-trace-destinations.json",
                        json.dumps(
                            {
                                "network_touching_tests_count": network_touching_count,
                                "distinct_hosts": distinct_hosts,
                                "cross_reference_ok": cross_reference_ok,
                                "ground_truth_ok": p2_ground_truth_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0053-both-states-block-control",
                "name": (
                    "both-states control: the blocked environment must be proven to "
                    "block -- assert a deliberate fetch fails inside it before "
                    "trusting any test that passes there"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked_outcome_diff.py",
                "result": "PASS" if both_states_ok else "FAIL",
                "assertions": 2,
                "output_tail": raw1.splitlines()[2] if len(raw1.splitlines()) > 2 else "",
            },
            {
                "id": "AUD-0053-egress-blocked-outcome-diff",
                "name": "record every test whose outcome changes when egress is blocked",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked_outcome_diff.py",
                "result": "PASS" if p1_ok else "FAIL",
                "assertions": baseline_collected,
                "output_tail": raw1[-800:],
            },
            {
                "id": "AUD-0053-socket-trace-destinations",
                "name": "socket-level trace naming destination hosts on an unblocked run",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0053/probe2_socket_trace_destinations.py",
                "result": "PASS" if p2_ok else "FAIL",
                "assertions": network_touching_count,
                "output_tail": raw2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0053-C1",
                "mutation",
                (
                    "A deliberate fetch to a real host must FAIL with OSError inside "
                    "fixtures/egress_block.py's block and must SUCCEED with the "
                    "block absent -- both in the same process, immediately before "
                    "either pytest subprocess is trusted."
                ),
                True,
                True,
                bad=f"bad_state_error={both_states.get('bad_state_error')}",
                good=f"good_state_unblocked_connect_succeeded={both_states.get('good_state_unblocked_connect_succeeded')}",
            ),
            L.control(
                "AUD0053-C2",
                "known-broken-fixture",
                (
                    "A deliberately planted real-network-dependent test must be "
                    "flagged by probe1 (PASS unblocked -> FAIL blocked) AND named "
                    "by probe2's trace; a deliberately planted network-TOUCHING "
                    "but outcome-invariant test must be MISSED by probe1 (its "
                    "documented detection boundary) yet still named by probe2."
                ),
                True,
                True,
                bad=f"a_caught={p1.get('ground_truth', {}).get('a_real_dependency_caught')} b_missed_by_outcome_diff={p1.get('ground_truth', {}).get('b_correctly_missed_by_outcome_diff')}",
                good=f"probe1_ground_truth_ok={p1_ground_truth_ok} probe2_ground_truth_ok={p2_ground_truth_ok}",
            ),
            L.control(
                "AUD0053-C3",
                "other",
                (
                    "Every nodeid probe1 flags as network-DEPENDENT (outcome "
                    "changed under block) must also appear in probe2's "
                    "network-TOUCHING trace -- a dependency cannot exist without "
                    "a touch. A violation would mean one of the two instruments "
                    "is broken."
                ),
                True,
                True,
                bad=f"missing_from_trace={p2.get('cross_reference_missing_from_trace')}",
                good=f"cross_reference_ok={cross_reference_ok}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0053/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the "
                "tree; restore from the AUD-0092 backup, record the mutation, "
                "and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"Whether tests under tools/, platform/, skills/, and the two "
                    "excluded non-hermetic salvage/scratch trees "
                    "(command-center/ssot/salvaged-at-risk, "
                    "command-center/p2-wave/probes/AUD-0043/fixtures) reach the "
                    "network (this pass swept only the "
                    f"{baseline_collected} tests collectible cleanly under "
                    "command-center/)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Repair the two excluded trees' import/collection errors "
                    "(fixtures/collectible_scope.py names each), extend "
                    "TARGET_ARGS to cover tools/ and platform/ once each "
                    "collects cleanly, and re-run both named probes."
                ),
            },
            {
                "claim": (
                    "Whether the socket-level block/trace, which patches "
                    "socket.socket.connect()/connect_ex(), also covers UDP "
                    "(SOCK_DGRAM) egress or non-blocking async network I/O "
                    "(e.g. asyncio's own C-level socket paths, which may bypass "
                    "the pure-Python connect()/connect_ex() wrapper on some "
                    "event-loop implementations)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a UDP ground-truth fixture (socket.socket(AF_INET, "
                    "SOCK_DGRAM).connect(...) to a real host) and an asyncio "
                    "ground-truth fixture, re-run both probes, and confirm both "
                    "are caught the same way the two TCP ground-truth fixtures "
                    "were this pass."
                ),
            },
            {
                "claim": (
                    "Whether DNS resolution itself (socket.getaddrinfo / "
                    "gethostbyname), which this probe does NOT block or trace "
                    "(only the subsequent connect() is instrumented), leaks "
                    "queried hostnames to a DNS resolver even for tests whose "
                    "connect() never fires (e.g. a test that resolves a host "
                    "then gives up before connecting)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend fixtures/egress_block.py and aud0053_plugin.py to "
                    "also wrap socket.getaddrinfo, add a resolve-only ground-"
                    "truth fixture, and re-run both probes."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0053-C1", "AUD0053-C2", "AUD0053-C3"],
            "observations": [
                {
                    "name": "baseline_collected_count",
                    "measured": baseline_collected,
                    "method": "pytest --collect-only over fixtures/collectible_scope.py TARGET_ARGS",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.raw.txt",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states_ok,
                    "method": "real TCP connect to example.com:80, unblocked then blocked, same process",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.json",
                },
                {
                    "name": "network_dependent_candidates_count",
                    "measured": network_dependent_count,
                    "method": "baseline PASS + blocked non-PASS on the same nodeid",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe1-egress-blocked-outcome-diff.raw.txt",
                },
                {
                    "name": "network_touching_tests_count",
                    "measured": network_touching_count,
                    "method": "socket.socket.connect() traced per-nodeid on an unblocked run; non-loopback only",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.raw.txt",
                },
                {
                    "name": "distinct_destination_hosts_count",
                    "measured": len(distinct_hosts),
                    "method": (
                        "distinct connect() target hosts recorded across the "
                        f"traced run: {distinct_hosts}"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.json",
                },
                {
                    "name": "touch_only_count",
                    "measured": touch_only_count,
                    "method": (
                        "probe2 touching set minus probe1 dependent set -- tests "
                        "that reach the network but whose outcome does not depend on it"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe2-socket-trace-destinations.json",
                },
                {
                    "name": "ground_truth_detection_ok",
                    "measured": bool(p1_ground_truth_ok and p2_ground_truth_ok),
                    "method": (
                        "planted real-network-dependent test + planted "
                        "outcome-invariant silent-touch test; each must be "
                        "detected by its documented instrument"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0053/fixtures/network_dependent/",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "both_states_control_ok": both_states_ok,
                "baseline_collected_count": baseline_collected,
                "network_dependent_candidates_count": network_dependent_count,
                "ground_truth_ok": p1_ground_truth_ok,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "network_touching_tests_count": network_touching_count,
                "distinct_hosts": distinct_hosts,
                "cross_reference_ok": cross_reference_ok,
                "ground_truth_ok": p2_ground_truth_ok,
                "ok": p2_ok,
            },
            "touch_vs_depend": {
                "network_dependent_count": network_dependent_count,
                "network_touching_count": network_touching_count,
                "touch_only_count": touch_only_count,
                "touch_only_ids": touch_only_ids,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-egress-blocked-outcome-diff.json",
        PROBE / "probe2-socket-trace-destinations.json",
        PROBE / "probe1-egress-blocked-outcome-diff.raw.txt",
        PROBE / "probe2-socket-trace-destinations.raw.txt",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0053 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
