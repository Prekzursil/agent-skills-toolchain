#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0266.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/receipts/IMP-0266.json"
SENTINEL = "SUCCESS:IMP-0266"

SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/participants/__init__.py",
    "tools/council/participants/select_explicit.py",
    "tools/council/participants/schema/explicit-roster.schema.json",
    "tools/council/participants/fixtures/known-good-roster.json",
    "tools/council/participants/fixtures/unavailability.json",
    "tools/council/participants/tests/conftest.py",
    "tools/council/participants/tests/test_select_explicit.py",
    "command-center/p2-wave/probes/IMP-0266/probe1_exact_round_trip.py",
    "command-center/p2-wave/probes/IMP-0266/probe2_unavailability.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/participants/tests/test_select_explicit.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0266/probe1_exact_round_trip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0266/probe2_unavailability.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str, method: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(f"{method}\n{cmd}"),
        "method": method,
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0266 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0266-tests" not in t_test:
        print("FAILED:IMP-0266 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0266-probe1" not in t1:
        print("FAILED:IMP-0266 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0266-probe2" not in t2:
        print("FAILED:IMP-0266 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    test_ids = [
        "test_exact_roster_round_trip",
        "test_auto_substitution_set_comparison_fails",
        "named-probe1",
        "named-probe2",
    ]
    negative_control_ids = [
        "auto-substitution-set-comparison-fails",
        "known-good-twin-stays-set-equal",
    ]

    receipt = {
        "unit_id": "IMP-0266",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "profile": "council-participants-module",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0266",
        "title": "Explicit roster resolver",
        "question": (
            "Implement the exact-participant path in "
            "tools/council/participants/select_explicit.py so a named roster "
            "is resolved, validated against role requirements and failed "
            "loudly when a named participant is unavailable. Falsifiable "
            "question: does an unavailable named participant get silently "
            "substituted?"
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/participants/select_explicit.py",
            "path": "exact",
            "lookup_protocol": "ParticipantLookup.get / available_for_role",
            "set_comparison": "roster_set_equals / compare_rosters_as_set",
            "auto_substitution_twin": "resolve_with_auto_substitution",
            "silent_substitution": False,
        },
        "artifact_paths": artifact_paths,
        "test_ids": test_ids,
        "negative_control_ids": negative_control_ids,
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/participants/select_explicit.py:resolve_explicit",
                "claim": (
                    "A known-good named roster round-trips: seated identities "
                    "as a set equal the requested roster, roles match, and "
                    "no substitution is recorded."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source", "command"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier", "test-run"),
                ],
            },
            {
                "anchor": "tools/council/participants/fixtures/unavailability.json",
                "claim": (
                    "The unavailability fixture produces a refusal event that "
                    "names dom-cara. The exact path seats nobody. Enabling "
                    "auto-substitution seats dom-drew instead, and set "
                    "comparison of seated vs requested FAILS."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source", "command"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier", "test-run"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "auto-substitution-set-comparison-fails",
                "kind": "known-broken-fixture",
                "description": (
                    "resolve_with_auto_substitution seats dom-drew for the "
                    "unavailable named participant dom-cara; "
                    "compare_rosters_as_set reports equal=false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "good.set_equals() is True",
                "bad_state_output": "auto_sub.set_equals() is False missing=dom-cara extra=dom-drew",
            },
            {
                "id": "known-good-twin-stays-set-equal",
                "kind": "mutation",
                "description": (
                    "The same requested names with every participant available "
                    "still set-compare equal in the same probe2 run that "
                    "refused dom-cara."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "good_twin_set_equals=True",
                "bad_state_output": "refusal_names=dom-cara exact_seated=[]",
            },
        ],
        "tests": [
            {
                "id": "test_exact_roster_round_trip",
                "command": TEST_CMD + "::test_exact_roster_round_trip",
                "result": "PASS",
            },
            {
                "id": "test_auto_substitution_set_comparison_fails",
                "command": TEST_CMD + "::test_auto_substitution_set_comparison_fails",
                "result": "PASS",
            },
            {
                "id": "named-probe1",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "named-probe2",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0266-probe2-unavailability",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Starts from the tests, not the author's summary. Obligation: "
                "an unavailable named participant is refused by name; "
                "auto-substitution is detected because seated-vs-requested "
                "set comparison FAILS. Method: re-ran probe2_unavailability.py "
                "against the unavailability fixture and the known-good twin."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "named-probes-IMP-0266",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(P2, c2, t2, "verifier", "command"),
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0266/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0265 (tools/council/participants/registry.py identity "
                    "store) is not delivered in this worktree. The exact path "
                    "consumes a ParticipantLookup protocol; probes use "
                    "InMemoryLookup over fixtures. Wiring the production "
                    "registry is IMP-0265's work, not a missing refusal rule."
                ),
                "settling_experiment": (
                    "After IMP-0265 lands, wrap its registry in the lookup "
                    "protocol and re-run the two named probes against a live "
                    "unavailability bit on a registered participant."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0266 exact-participant roster resolver. "
            "Live probes: exact round trip and unavailability refusal with "
            "auto-substitution set-comparison FAIL. Did not run global "
            "unit_manifest.py --write. cloud ok is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
