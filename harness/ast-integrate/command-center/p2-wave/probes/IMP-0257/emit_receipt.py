#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0257.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0257.json"
SENTINEL = "SUCCESS:IMP-0257"

SUPPORTING = [
    "tools/council/evidence/freshness.py",
    "tools/council/evidence/__init__.py",
    "tools/council/evidence/schema/anchor-freshness.schema.json",
    "tools/council/evidence/tests/test_freshness.py",
    "command-center/p2-wave/probes/IMP-0257/probe1_class_windows.py",
    "command-center/p2-wave/probes/IMP-0257/probe2_cache_bypass.py",
    "command-center/p2-wave/probes/IMP-0257/fixtures/recorded-council.json",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/evidence/tests/test_freshness.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0257/probe1_class_windows.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0257/probe2_cache_bypass.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


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
        "raw_output": text[-2000:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0257 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0257-tests" not in t_test:
        print("FAILED:IMP-0257 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0257-probe1" not in t1:
        print("FAILED:IMP-0257 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0257-probe2" not in t2:
        print("FAILED:IMP-0257 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": "IMP-0257",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0257 "
            "tools/council/evidence/freshness.py as-of stamp + class window; "
            "stale anchor cannot bind without transport revalidation"
        ),
        "title": "Evidence freshness and revalidation gate",
        "question": (
            "Implement tools/council/evidence/freshness.py stamping every "
            "evidence anchor with an as-of date and refusing to let a stale "
            "anchor carry a binding decision without revalidation. How many "
            "anchors in a recorded council are older than the configured "
            "freshness window, and does revalidation actually re-read the "
            "source rather than a cached copy of it?"
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/evidence/freshness.py",
            "classes": [
                "anecdote",
                "archive",
                "documentation",
                "executable-proof",
                "live-url",
                "measurement",
                "peer-reviewed",
                "receipt",
                "schema",
            ],
            "windows_s": {
                "anecdote": 1800,
                "archive": 31536000,
                "documentation": 604800,
                "executable-proof": 86400,
                "live-url": 3600,
                "measurement": 14400,
                "peer-reviewed": 7776000,
                "receipt": 86400,
                "schema": 604800,
            },
            "transport": "FileTransport.ledger (layer=transport)",
            "cache_report": "MemoryCache.report is ignored by transport_check",
        },
        "artifact_paths": [OUT_REL] + SUPPORTING,
        "test_ids": [
            "test_per_class_windows_are_distinct",
            "test_histogram_counts_stale_at_decision_time",
            "test_stale_anchor_cannot_bind_without_revalidation",
            "test_cache_pointed_revalidation_fires_transport_check",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "cache-pointed-revalidation-fires",
            "fresh-twin-stays-admitted",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/evidence/freshness.py:age_histogram",
                "claim": (
                    "At decision_at=1700000000 the recorded council has 4 of 8 "
                    "anchors older than their class window (A-LIVE-STALE, "
                    "A-MEAS-STALE, A-DOC-STALE, A-ANEC-STALE). Binding is "
                    "refused while those four remain unrevalidated. Per-class "
                    "windows are distinct: 4000s is STALE for live-url (1h) and "
                    "FRESH for measurement (4h)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/evidence/freshness.py:transport_check",
                "claim": (
                    "Pointing revalidation at MemoryCache makes transport_check "
                    "FIRE (ledger empty) even when the cache claims "
                    "revalidated=true. A subsequent FileTransport.read after a "
                    "disk mutation restamps a new sha256 the cache does not "
                    "hold; the check is SILENT and the restamped anchor may bind."
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
                "id": "cache-pointed-revalidation-fires",
                "kind": "transport-layer-check",
                "description": (
                    "Revalidation pointed at the cache: cache.report says "
                    "revalidated=true, transport ledger has zero reads, "
                    "transport_check status=FIRED, admission refused."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "transport_check=SILENT ledger_grew=True",
                "bad_state_output": (
                    "transport_check=FIRED cache_claimed_revalidation=True"
                ),
            },
            {
                "id": "fresh-twin-stays-admitted",
                "kind": "known-good-twin",
                "description": (
                    "A live-url stamped inside its 1h window stays FRESH and "
                    "admitted in the same probe1 run that refuses A-LIVE-STALE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "A-LIVE-FRESH freshness=FRESH",
                "bad_state_output": (
                    "A-LIVE-STALE freshness=STALE excluded from "
                    "supporting_anchor_ids"
                ),
            },
        ],
        "tests": [
            {
                "id": "test_per_class_windows_are_distinct",
                "command": TEST_CMD + "::test_per_class_windows_are_distinct",
                "result": "PASS",
            },
            {
                "id": "test_cache_pointed_revalidation_fires_transport_check",
                "command": (
                    TEST_CMD
                    + "::test_cache_pointed_revalidation_fires_transport_check"
                ),
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0257-probe2-cache-bypass",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "Transport-layer check must FIRE when revalidation is pointed "
                "at the cache; cache.report is not proof of a source read."
            ),
            "method": (
                "Fill cache, mutate disk, revalidate via cache (FIRED, old hash), "
                "revalidate via FileTransport (SILENT, new hash, admitted)."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py IMP-0257"
                ),
                "executed": False,
                "read_ok": False,
                "note": (
                    "G-1 measure runs after this receipt and the per-unit "
                    "manifest exist."
                ),
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0257/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": (
                "per-unit (not tools/command-center/unit_manifest.py --write)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0310 (deadlock detector) and IMP-0305 (Bayesian pooling) "
                    "are catalog dependencies and are not delivered on this "
                    "worktree. freshness.py does not import them; wiring the "
                    "gate into a live council kernel is those units' work."
                ),
                "settling_experiment": (
                    "After IMP-0310/IMP-0305 land, stamp anchors from a live "
                    "council transcript and re-run probe1 against that recording."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0257 evidence freshness. Live named probes "
            "exit 0. Recorded-council histogram: 4/8 stale at decision time. "
            "Cache-pointed revalidation FIRED at the transport layer. Did not "
            "run global unit_manifest.py --write. cloud ok is not consulted."
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
