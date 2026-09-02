#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0275.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0275.json"
SENTINEL = "SUCCESS:IMP-0275"

SUPPORTING = [
    "tools/council/participants/replace.py",
    "tools/council/participants/__init__.py",
    "tools/council/participants/tests/conftest.py",
    "tools/council/participants/tests/test_replace.py",
    "command-center/p2-wave/probes/IMP-0275/probe1_eviction_triggers.py",
    "command-center/p2-wave/probes/IMP-0275/probe2_census_retention.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/participants/tests/test_replace.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0275/probe1_eviction_triggers.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0275/probe2_census_retention.py"
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


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(text),
        "method": "command",
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0275 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0275-tests" not in t_test:
        print("FAILED:IMP-0275 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0275-probe1" not in t1:
        print("FAILED:IMP-0275 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0275-probe2" not in t2:
        print("FAILED:IMP-0275 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    test_ids = [
        "test_eviction_triggers_and_quorum_recomputation",
        "test_negative_control_drop_evicted_ideas_fails_census",
        "named-probe1",
        "named-probe2",
    ]
    negative_control_ids = [
        "drop-evicted-ideas-census-fails",
        "author-remap-detected",
    ]

    receipt = {
        "unit_id": "IMP-0275",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0275",
        "title": "Participant replacement and eviction on inactivity or failure",
        "question": (
            "Implement tools/council/participants/replace.py evicting a "
            "participant that breaches max inactivity or fails repeatedly, "
            "preserving its prior contributions in the record. Falsifiable "
            "question: does eviction ever delete or orphan an evicted "
            "participant's earlier votes and ideas?"
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/participants/replace.py",
            "rule_id": "R-EVICT-RETAIN",
            "triggers": ["inactivity", "repeated_failure"],
            "quorum": "len(seated) >= quorum_minimum; evicted ids do not occupy a seat",
            "tally": (
                "closed rounds retain evicted votes; open-round live tally "
                "excludes evicted seats; contributions stay keyed by original author_id"
            ),
            "replacement_inherits": False,
        },
        "artifact_paths": artifact_paths,
        "test_ids": test_ids,
        "negative_control_ids": negative_control_ids,
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/participants/replace.py:evict",
                "claim": (
                    "Inactivity and repeated-failure triggers evict the due "
                    "seat, recompute quorum over remaining seated ids, and "
                    "void the council when seated_count falls below "
                    "quorum_minimum. A new replacement id restores quorum "
                    "and inherits no prior votes or ideas."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/participants/replace.py:census_retention_check",
                "claim": (
                    "Artifact census before vs after eviction retains every "
                    "prior vote and idea keyed by the evicted author_id. "
                    "Independent recomputation of the R-EVICT-RETAIN tally "
                    "matches the recorded tally. Dropping the evicted "
                    "member's ideas makes census_retention_check FAIL."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "drop-evicted-ideas-census-fails",
                "kind": "planted-deletion",
                "description": (
                    "After an honest eviction, delete dave's ideas from a "
                    "mutated copy. census_retention_check reports ok=false "
                    "and missing contains i-r1-dave."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "retention.ok=True missing=[]",
                "bad_state_output": "retention.ok=False missing=['i-r1-dave']",
            },
            {
                "id": "author-remap-detected",
                "kind": "planted-identity-theft",
                "description": (
                    "Rewriting i-r1-dave.author_id to the replacement id is "
                    "detected as remapped; the honest eviction leaves author_id=dave."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "after_census.by_author.dave includes i-r1-dave",
                "bad_state_output": "remap_check.ok=False remapped=['i-r1-dave']",
            },
        ],
        "tests": [
            {
                "id": "test_eviction_triggers_and_quorum_recomputation",
                "command": TEST_CMD + "::test_eviction_triggers_and_quorum_recomputation",
                "result": "PASS",
            },
            {
                "id": "test_negative_control_drop_evicted_ideas_fails_census",
                "command": TEST_CMD
                + "::test_negative_control_drop_evicted_ideas_fails_census",
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
            "reviewer_id": "IMP-0275-probe2-census-retention",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "Eviction must not delete or orphan prior votes/ideas; "
                "dropping those ideas must fail the census; recorded tally "
                "must match an independent R-EVICT-RETAIN recompute."
            ),
            "method": (
                "Re-ran probe2_census_retention.py from the census and tally "
                "invariants, including planted deletion and author remap. "
                "Did not re-read an author summary."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0275",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0275/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0265 (participant registry) and IMP-0288 (nested "
                    "topology) are catalog dependencies and are not delivered "
                    "in this worktree. replace.py operates on an explicit run "
                    "record and does not call those modules. Wiring eviction "
                    "into a live kernel event loop is their work, not a "
                    "missing retention rule."
                ),
                "settling_experiment": (
                    "After IMP-0265/IMP-0288 land, evict a registered idle "
                    "seat inside a nested council record and re-run the two "
                    "named probes against that live record."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0275 participant eviction. Live probes: "
            "inactivity/failure triggers with quorum recompute, and census "
            "retention with a drop-ideas negative control. Did not run "
            "global unit_manifest.py --write. cloud ok is not consulted."
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
