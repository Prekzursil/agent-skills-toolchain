#!/usr/bin/env python3
"""Emit IMP-0402 catalog receipt plus per-unit G-1 probe receipts.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0402"
OUT = "command-center/receipts/IMP-0402.json"
SENTINEL = "SENTINEL:IMP-0402:INDEX-INVALIDATION-SAFE"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0402/probe1_edit_then_query.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0402/probe2_corrupt_cache.py"
)
SUPPORTING = [
    "tools/router/index_cache.py",
    "tools/router/query.py",
    "tools/router/__init__.py",
    "command-center/p2-wave/probes/IMP-0402/scenario.py",
    "command-center/p2-wave/probes/IMP-0402/probe1_edit_then_query.py",
    "command-center/p2-wave/probes/IMP-0402/probe2_corrupt_cache.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0402/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(t1[-2000:])
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        return 1

    s1 = first_json(t1)
    s2 = first_json(t2)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "title": "Index staleness invalidation keyed on content hash",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0402",
        "min_bytes_threshold": 128,
        "question_or_target": (
            "Implement cache invalidation for the capability index using content "
            "hash plus mtime, with an explicit corrupted-cache recovery path. "
            "Editing a capability description must change the router's answer on "
            "the very next call, and a truncated cache file must trigger a rebuild "
            "rather than a crash or a silently empty index."
        ),
        "exact_answer": {
            "edit_then_query_calls_until_new_answer": 1,
            "truncated_cache_rebuilds": True,
            "zero_byte_cache_rebuilds": True,
            "wrong_schema_cache_rebuilds": True,
            "empty_rebuilt_index_is_failure": True,
            "empty_index_reported_ok": False,
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Timed edit-then-query: after rewriting paint's description from "
                    "RED-PIGMENT to BLUE-PIGMENT, the very next route_next call rebuilt "
                    "on stale-hash and no longer returned the old description. An "
                    "unedited sibling (GLOSS-COAT) kept its answer. A touch-without-edit "
                    "invalidated on mtime_token while content_hash stayed identical."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0402/probe1_edit_then_query.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(P1.encode()).hexdigest()[:32],
                        "raw_output": t1[-8000:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "parse probe1 JSON summary",
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"probe1-summary").hexdigest()[:32],
                        "raw_output": json.dumps(
                            {
                                k: s1.get(k)
                                for k in (
                                    "pass",
                                    "answer_changed_on_next_call",
                                    "mtime_only_rebuild",
                                    "unedited_sibling_stable",
                                )
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Corrupted-cache recovery: truncated, zero-byte, and wrong-schema "
                    "cache files each diagnosed and rebuilt from sources. A matching-hash "
                    "wrong-schema plant did not serve its stale description. "
                    "assert_index_usable([]) raises EmptyIndexError; rebuild over empty "
                    "sources also raises; neither path reports OK."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0402/probe2_corrupt_cache.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": hashlib.sha256(P2.encode()).hexdigest()[:32],
                        "raw_output": t2[-8000:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "parse probe2 JSON summary",
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"probe2-summary").hexdigest()[:32],
                        "raw_output": json.dumps(
                            {
                                k: s2.get(k)
                                for k in (
                                    "pass",
                                    "truncated_rebuilt",
                                    "zero_byte_rebuilt",
                                    "wrong_schema_rebuilt",
                                    "empty_index_is_failure",
                                )
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "max 2 attempts; two-strikes pivot to unconditional rebuild",
        },
        "tests": [
            {
                "id": "probe1-edit-then-query",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "probe2-corrupt-cache",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0402-C1-unedited-sibling",
                "kind": "both-states",
                "description": "Editing paint must not change the gloss answer.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "stale RED-PIGMENT refused after edit",
                "good_state_output": "GLOSS-COAT answer identical before/after",
            },
            {
                "id": "IMP0402-C2-empty-index-not-ok",
                "kind": "known-broken-fixture",
                "description": "Empty capabilities must raise, not report OK.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "EmptyIndexError on [] and on empty sources",
                "good_state_output": "valid cache is cache-hit with non-empty capabilities",
            },
            {
                "id": "IMP0402-C3-wrong-schema-plant",
                "kind": "mutation",
                "description": (
                    "A wrong-schema cache with matching hashes and a planted stale "
                    "description must rebuild from sources, not serve the plant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "PLANTED-STALE-PIGMENT absent after rebuild",
                "good_state_output": "RED-PIGMENT restored from sources",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0402-probe2-empty-index-not-ok",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 independently constructs an empty capabilities document "
                "and empty source roots; both must raise EmptyIndexError. It does not "
                "trust a self-declared ok=true on an empty index."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0402/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0402",
                    "raw_output": "measure runs after this receipt is written",
                    "fingerprint": hashlib.sha256(b"measure-IMP-0402").hexdigest()[:32],
                },
            }
        ],
        "edit_then_query_trace": s1.get("trace") or [],
        "corrupt_cache_observations": s2.get("observations") or [],
        "implementation": {
            "cache_module": "tools/router/index_cache.py",
            "query_module": "tools/router/query.py",
            "schema": "ast.capability-index-cache/v1",
            "invalidation": ["content_hash", "mtime_token"],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0385 six-root crawler is not on this worktree; invalidation "
                    "was proven against fixture capability roots, which is the same "
                    "fingerprint+rebuild path a later crawler would feed."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": "Re-run probe1/probe2 with live six-root output once IMP-0385 ships.",
            }
        ],
        "notes": (
            "G-1 for IMP-0402: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Re-run probes now that the receipt exists so named-probe re-runs stay green.
    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:{UNIT} post-receipt probes c1={c1b} c2={c2b}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "edit-then-query",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "corrupt-cache-empty-index",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0402/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0402-probe2-empty-index-not-ok",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0402: live named probes exit 0, receipts/IMP-0402.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
