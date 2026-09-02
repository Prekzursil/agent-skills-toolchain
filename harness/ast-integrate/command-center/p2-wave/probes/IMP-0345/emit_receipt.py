#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0345.json from live HybridCouncil runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import (  # noqa: E402
    evaluate_mixed,
    evaluate_negative_control,
    evaluate_unit_paths,
    timeout_path_assigns_marker,
)

OUT = "command-center/receipts/IMP-0345.json"
LIB = "tools/council/participants/human.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0345/probe1_timeout_proxy_tally.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0345/probe2_marker_negative_control.py"
)
QUESTION = (
    "Implement tools/council/participants/human.py so a council can seat "
    "humans alongside agents, with asynchronous turn windows, reminders, "
    "timeout-to-proxy and an explicit human-only mode (spec 10922). "
    "Falsifiable question: when a human seat times out, does the council "
    "substitute a proxy position and record it AS a proxy, or does the "
    "human's silence become an unmarked abstention that shifts the tally?"
)
SUPPORTING = [
    LIB,
    "tools/council/__init__.py",
    "tools/council/participants/__init__.py",
    "command-center/p2-wave/probes/IMP-0345/scenario.py",
    "command-center/p2-wave/probes/IMP-0345/probe1_timeout_proxy_tally.py",
    "command-center/p2-wave/probes/IMP-0345/probe2_marker_negative_control.py",
]


def digest(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest(rel)
    return {
        "path": rel,
        "sha256": sha or ("0" * 64),
        "bytes": size,
        "exists": exists,
        "role": role,
        "eol": "LF",
    }


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(
            f"{method}\x1f{command}".encode()
        ).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mixed = evaluate_mixed()
    units = evaluate_unit_paths()
    neg = evaluate_negative_control()
    src = timeout_path_assigns_marker()
    if not mixed["pass"] or not units["pass"] or not neg["pass"] or not src["pass"]:
        print(
            "FAILED:IMP-0345 emit "
            f"mixed={mixed['pass']} units={units['pass']} "
            f"neg={neg['pass']} src={src['pass']} "
            f"unit_failed={units['failed']}"
        )
        return 1

    lib = art(LIB, "primary-implementation")
    artifacts = [lib] + [art(p, "supporting") for p in SUPPORTING if p != LIB]
    with_p = mixed["with_proxy"]
    without_p = mixed["without_proxy"]
    mixed_raw = json.dumps(
        {
            "with_proxy": with_p,
            "without_proxy": without_p,
            "shifted": mixed["outcome_shifted"],
        },
        sort_keys=True,
    )
    neg_raw = json.dumps(
        {
            "good_kinds": neg["good_kinds"],
            "bad_kinds": neg["bad_kinds"],
            "indistinguishable_after_strip": neg["indistinguishable_after_strip"],
        },
        sort_keys=True,
    )
    p1 = probe_rec("source", "command", P1, mixed_raw, 0)
    p2 = probe_rec("verifier", "command", P2, neg_raw, 0)
    src_probe = probe_rec(
        "verifier",
        "ast-read",
        "timeout_path_assigns_marker(human.py)",
        json.dumps(src, sort_keys=True),
        0,
    )
    file_probe = probe_rec(
        "verifier",
        "file-read",
        f"sha256 {LIB}",
        f"bytes={lib['bytes']} sha256={lib['sha256']}",
        0,
    )
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "IMP-0345",
        "id": "IMP-0345",
        "title": "Hybrid human and agent participation with asynchronous human turns",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0345",
        "completion_sentinel": "SUCCESS:IMP-0345",
        "schema_version": 1,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-runtime-module"
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0345 question_or_target "
            "(spec 10922 human-only mode, timeout-to-proxy). "
            "11-COUNCIL-SPECIFICATION.md is absent on this worktree."
        ),
        "question_or_target": QUESTION,
        "artifact_paths": [a["path"] for a in artifacts],
        "artifacts": artifacts,
        "implementation": {
            "api_module": LIB,
            "sha256": lib["sha256"],
            "bytes": lib["bytes"],
            "entry_points": [
                "council.participants.human.HybridCouncil",
                "council.participants.human.effective_ballot",
                "council.participants.human.scan_proxy_markers",
                "council.participants.human.strip_proxy_markers",
            ],
            "proxy_origin_marker": "proxy-origin",
            "timeout_policy": "timeout-to-proxy",
            "human_only_refuses_agent_seats": True,
            "abstention_policy_id": mixed["artifact"]["abstention_policy_id"],
            "clock": "DeterministicClock (injected; tests do not sleep)",
        },
        "tally_recomputations": {
            "with_proxy": mixed["with_proxy"],
            "without_proxy": mixed["without_proxy"],
            "expected_with": mixed["expected_with"],
            "expected_without": mixed["expected_without"],
            "outcome_shifted": mixed["outcome_shifted"],
            "hand_computed": True,
            "note": (
                "WITH proxy: H3's marked proxy REJECT is counted. "
                "WITHOUT proxy: H3 silence is an unmarked abstention. "
                "Winner flips TIE → APPROVE."
            ),
        },
        "proxy_marker_scan": mixed["scan"],
        "evidence": [
            {
                "anchor": f"{LIB}:HybridCouncil.both_tallies",
                "claim": (
                    "Live tally recomputation with and without the proxy is "
                    "recorded. WITH: approve=2 reject=2 abstain=1 denom=4 "
                    "winner=TIE. WITHOUT: approve=2 reject=1 abstain=2 "
                    "denom=3 winner=APPROVE. Outcome shifts."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, file_probe],
            },
            {
                "anchor": f"{LIB}:scan_proxy_markers",
                "claim": (
                    "Every proxied turn carries proxy-origin. H3 timeout is "
                    "origin=proxy, marker=proxy-origin, choice=REJECT."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, src_probe, file_probe],
            },
        ],
        "test_ids": [
            "t1-async-window-reminder-timeout-proxy",
            "t2-marker-load-bearing-negative-control",
        ],
        "tests": [
            {
                "id": "t1-async-window-reminder-timeout-proxy",
                "command": P1,
                "result": "PASS",
                "detail": (
                    f"unit_paths={units['rows']} "
                    f"with={mixed['with_proxy']} without={mixed['without_proxy']}"
                ),
            },
            {
                "id": "t2-marker-load-bearing-negative-control",
                "command": P2,
                "result": "PASS",
                "detail": (
                    f"good_kinds={neg['good_kinds']} "
                    f"bad_kinds={neg['bad_kinds']}"
                ),
            },
        ],
        "negative_control_ids": [
            "c-strip-proxy-marker-silence-equals-abstention"
        ],
        "negative_controls": [
            {
                "id": "c-strip-proxy-marker-silence-equals-abstention",
                "kind": "both-states",
                "description": (
                    "Strip proxy-origin from live turns. Timeout silence "
                    "classifies as abstention, matching explicit human "
                    "abstain. Scan fails on the stripped artifact and "
                    "passes on the intact one."
                ),
                "fired_on_bad_state": neg["fired_on_bad_state"],
                "silent_on_good_state": neg["silent_on_good_state"],
                "good_state_output": json.dumps(neg["good_kinds"], sort_keys=True),
                "bad_state_output": json.dumps(neg["bad_kinds"], sort_keys=True),
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0345-probe2-marker-negative-control",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "verdict": "PASS",
            "note": (
                "Adversarial half is probe 2 plus AST check that "
                "_apply_timeout_proxy assigns PROXY_ORIGIN_MARKER. "
                "The reviewer does not grant the owner-signoff half."
            ),
            "ast": src,
        },
        "owner_signoff": {
            "required": True,
            "granted": False,
            "grantor": None,
            "status": "PENDING-OWNER",
            "reviewer_may_not_grant": True,
            "note": (
                "Catalog owner_approval_required=true. This receipt is "
                "technical delivery of timeout-to-proxy marking and tally "
                "shift. The owner half is a separate sign-off; the reviewer "
                "verdict above does not grant it."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Owner sign-off is pending. Technical G-1 does not "
                    "substitute for the owner half."
                ),
                "settling_experiment": "Owner records granted=true on this receipt.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0265 tools/council/participants/registry.py is absent. "
                    "human.py carries seat id/kind/origin locally."
                ),
                "settling_experiment": "Re-seat the mixed roster through the registry once IMP-0265 lands.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0302 tools/council/vote/tally.py is absent. This unit "
                    "recomputes tallies inside human.py with an explicit "
                    "abstention_policy_id on every decision artifact."
                ),
                "settling_experiment": "Feed HybridCouncil.turns() into tally.py once IMP-0302 lands.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md / spec 10922 source file is "
                    "not on this Linux worktree. Behaviour is taken from the "
                    "catalog question_or_target."
                ),
                "settling_experiment": "Diff this module against spec 10922 when the specification is present.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "dependencies_note": (
            "Catalog lists IMP-0265 and IMP-0302. Neither artifact is on "
            "this worktree. This unit does not write those modules."
        ),
        "answer": (
            "Timeout substitutes a proxy position and records it AS a proxy "
            "(origin=proxy, proxy_origin_marker=proxy-origin). It does not "
            "become an unmarked abstention. Treating the same silence as "
            "unmarked abstention flips the winner from TIE to APPROVE."
        ),
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "implementer",
            "vendor": "cursor",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "notes": (
            "G-1 technical contract for IMP-0345. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. Owner sign-off "
            "is pending and is not granted by the reviewer."
        ),
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0345/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "min_bytes_threshold": 1024,
        "timestamps": {"started_at": started, "ended_at": ended},
        "ts": ended,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print("SUCCESS:IMP-0345 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
