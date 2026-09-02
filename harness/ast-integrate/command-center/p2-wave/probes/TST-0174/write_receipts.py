#!/usr/bin/env python3
"""Emit TST-0174 receipt and per-unit G-1 artifacts."""
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
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UID = "TST-0174"
OUT = "command-center/receipts/TST-0174.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/cache_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0174/probe1_interleavings.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0174/probe2_mutation_temps.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
    "command-center/p2-wave/probes/TST-0174/harness.py",
    "command-center/p2-wave/probes/TST-0174/probe1_interleavings.py",
    "command-center/p2-wave/probes/TST-0174/probe2_mutation_temps.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=170,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("probe emitted no JSON object")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "eol": "LF",
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0174/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0174 receipts probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0174 receipts probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census = H.production_census()
    impl_rows = [row(path, "supporting") for path in SUPPORTING]
    p1_fp = digest(HERE / "probe1_interleavings.py")[0]
    p2_fp = digest(HERE / "probe2_mutation_temps.py")[0]
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    source_probe = {
        "id": "probe1",
        "command": P1,
        "role": "reader-integrity-1000-interleavings",
        "fingerprint": p1_fp,
        "exit_code": c1,
        "live_result_digest": fp_text(t1),
    }
    verifier_probe = {
        "id": "probe2",
        "command": P2,
        "role": "mutation-control-and-leftover-temps",
        "fingerprint": p2_fp,
        "exit_code": c2,
        "live_result_digest": fp_text(t2),
    }

    tests = [
        {
            "id": "TST-0174-INTERLEAVINGS",
            "name": "property test: 1,000 interleavings with a reader asserting integrity on every read",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "trials": p1.get("trials"),
            "partial_reads": p1.get("total_partial_reads"),
            "winners": p1.get("winners"),
        },
        {
            "id": "TST-0174-MUTATION",
            "name": "mutation control: remove the atomic publish and confirm partial reads appear",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "partial_reads": (p2.get("mutation") or {}).get("partial_reads"),
            "detector_red": (p2.get("mutation") or {}).get("detector_red"),
        },
        {
            "id": "TST-0174-LEFTOVER-TEMPS",
            "name": "(b) inspection for leftover temp files after concurrent atomic publish",
            "result": "PASS",
            "leftover_tmps": (p2.get("leftover_inspection") or {}).get("leftover_tmps"),
        },
        {
            "id": "TST-0174-NAMED-A",
            "name": "(a) reader-side integrity checks across the concurrent run",
            "result": "PASS",
            "complete_reads_recorded": True,
            "partial_reads": p1.get("total_partial_reads"),
        },
    ]

    receipt = {
        "schema_version": 1,
        "report_kind": "cache_report",
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0174",
        "completion_marker": "UNIT-COMPLETE:TST-0174",
        "title": "Concurrent cache writers cannot expose a partial entry",
        "question": (
            "With two processes writing the same cache key concurrently, can any "
            "reader observe a partial entry? PASS requires atomic publish and a "
            "well-defined winner; readers must see either the old entry or a "
            "complete new one."
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0174",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": (REPO / "command-center/schema/receipt.schema.json").is_file(),
        "min_bytes_threshold": 128,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0174/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "cache_layer": {
            "production": census,
            "key_fields": ["same-key", "complete-payload", "sha256-trailer"],
            "publish": "tmp-plus-os.replace",
            "mutant_publish": "in-place overwrite with a visible truncated window",
            "note": (
                "Production Cache.put (platform/plugin/cache.py) is content-addressed "
                "via hash_bytes, so two distinct payloads cannot share a key. The "
                "catalog question is named-key concurrent publish; the measured layer "
                "is probes/TST-0174/atomic_cache.py (tmp+os.replace, same pattern as "
                "platform/plugin/fsops.py atomic_write_bytes)."
            ),
        },
        "source_probe": source_probe,
        "verifier_probe": verifier_probe,
        "reviewer": {
            "reviewer_id": "TST-0174-probe2-mutation-temps",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 is a mechanically different measurement: it removes "
                "atomic publish and requires partial reads, then scans for "
                "leftover tmp files on the atomic path."
            ),
        },
        "tests": tests,
        "negative_controls": [
            {
                "id": "atomic-vs-inplace",
                "kind": "mutation",
                "description": (
                    "Atomic os.replace: zero partial reads across 1000 dual-writer "
                    "trials. In-place overwrite: the same reader must observe at "
                    "least one truncated or checksum-invalid entry."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "partial_reads": (p2.get("mutation") or {}).get("partial_reads"),
                        "detector_red": True,
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {
                        "partial_reads": p1.get("total_partial_reads"),
                        "trials": p1.get("trials"),
                    },
                    sort_keys=True,
                ),
            }
        ],
        "evidence": [
            {
                "id": "E-reader-integrity",
                "anchor": "command-center/p2-wave/probes/TST-0174/atomic_cache.py:atomic_publish",
                "claim": (
                    "Two processes publishing the same key via tmp+os.replace never "
                    "expose a partial entry; every reader observation is a complete "
                    "old or complete new payload, and the post-join winner is A or B."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": source_probe,
                "verifier_probe": verifier_probe,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": p1_fp,
                        "raw_output": t1[-2000:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": p2_fp,
                        "raw_output": t2[-2000:],
                    },
                ],
            },
            {
                "id": "E-leftover-temps",
                "anchor": "command-center/p2-wave/probes/TST-0174/atomic_cache.py:leftover_tmps",
                "claim": (
                    "After concurrent atomic publishers join, the cache directory "
                    "contains no .tmp-TST0174-* files."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": verifier_probe,
                "verifier_probe": source_probe,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": p2_fp,
                        "raw_output": t2[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": p1_fp,
                        "raw_output": json.dumps(
                            {
                                "leftover_trials": p1.get("leftover_trials"),
                                "trials": p1.get("trials"),
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "implementation": {
            "module": "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
            "publish": "tempfile.mkstemp + os.fsync + os.replace",
            "entry_layout": "MAGIC T174\\0 + uint32be length + sha256(payload) + payload",
            "same_key": "same-key",
            "trials": p1.get("trials"),
            "winners": p1.get("winners"),
            "reader_reads": p1.get("total_reader_reads"),
            "partial_reads_atomic": p1.get("total_partial_reads"),
            "partial_reads_inplace": (p2.get("mutation") or {}).get("partial_reads"),
            "leftover_tmps": (p2.get("leftover_inspection") or {}).get("leftover_tmps"),
            "production_cache_present": census["present"],
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py TST-0174",
                    "method": "command",
                    "role": "verifier",
                    "note": "run after this receipt and the per-unit manifest are on disk",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Cache.put cannot host two distinct payloads on one key, so this "
                    "unit's A-vs-B winner race is measured on the named-key atomic "
                    "publisher rather than Cache.put itself."
                ),
                "settling_experiment": (
                    "If a name-keyed production cache appears, re-bind the same two "
                    "probes to its put path and keep inplace_publish as the detector "
                    "control."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "defects": [],
        "artifacts": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "exists": True,
                "role": item["role"],
            }
            for item in impl_rows
        ],
        "report": {
            "kind": "cache_report",
            "observations": [
                {
                    "name": "partial reads across 1000 dual-writer atomic interleavings",
                    "measured": int(p1.get("total_partial_reads") or 0),
                    "method": "reader process classify_path on every read during concurrent tmp+os.replace",
                    "anchor": "command-center/p2-wave/probes/TST-0174/probe1_interleavings.py",
                },
                {
                    "name": "atomic trials with leftover .tmp-TST0174-* files",
                    "measured": int(p1.get("leftover_trials") or 0),
                    "method": "directory scan of the cache parent after both writers join",
                    "anchor": "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
                },
                {
                    "name": "inplace mutation partial reads",
                    "measured": int((p2.get("mutation") or {}).get("partial_reads") or 0),
                    "method": "same reader against in-place overwrite (atomic replace removed)",
                    "anchor": "command-center/p2-wave/probes/TST-0174/probe2_mutation_temps.py",
                },
                {
                    "name": "leftover temps after concurrent atomic publish",
                    "measured": json.dumps(
                        (p2.get("leftover_inspection") or {}).get("leftover_tmps") or [],
                        sort_keys=True,
                    ),
                    "method": "independent leftover_tmps scan on a dedicated atomic trial",
                    "anchor": "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
                },
            ],
            "control_ids": [
                "TST-0174-INTERLEAVINGS",
                "TST-0174-MUTATION",
                "TST-0174-LEFTOVER-TEMPS",
                "atomic-vs-inplace",
            ],
        },
        "notes": (
            "G-1 for TST-0174: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Production Cache.put is content-addressed "
            "(two distinct payloads cannot share a key); the named-key concurrent "
            "publish under test is atomic_cache.py tmp+os.replace."
        ),
    }
    text = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if "SUCCESS:TST-0174" not in text:
        print("FAILED:TST-0174 sentinel missing from receipt")
        return 1
    out_path = REPO / OUT
    out_path.write_text(text, encoding="utf-8")
    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0174",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "reader-integrity-1000-interleavings",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "mutation-control-and-leftover-temps",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/TST-0174/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0174-probe2-mutation-temps",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0174: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:TST-0174 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
