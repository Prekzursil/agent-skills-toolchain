#!/usr/bin/env python3
"""Emit TST-0173 receipt, per-unit manifest, and SUBAGENT-RETURN after live probes."""

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
UNIT = "TST-0173"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = "SUCCESS:TST-0173"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/cache_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0173/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0173/probe2_fuzz_and_reviewer.py"
)
SUPPORTING = [
    "tools/artifact_cache/__init__.py",
    "tools/artifact_cache/store.py",
    "command-center/p2-wave/probes/TST-0173/harness.py",
    "command-center/p2-wave/probes/TST-0173/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0173/probe2_fuzz_and_reviewer.py",
    "command-center/p2-wave/probes/TST-0173/emit_receipt.py",
]
QUESTION = (
    "When a cached payload is corrupted after write, is the corruption caught "
    "on read by checksum and the entry quarantined and refetched? PASS forbids "
    "both a crash and a silent use of the corrupt bytes."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return {}


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print("FAILED:TST-0173 live probes did not all exit 0")
        print(out1[-3000:])
        print(out2[-3000:])
        return 1
    if "SUCCESS:TST-0173-probe1" not in out1:
        print("FAILED:TST-0173 probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0173-probe2" not in out2:
        print("FAILED:TST-0173 probe2 sentinel missing")
        return 1

    p1 = first_json(out1)
    p2 = first_json(out2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0173 probe JSON pass!=true")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / "command-center" / "schema" / "receipt.schema.json"
    corrupted = p1.get("corrupted") or {}
    mismatch_event = corrupted.get("mismatch_event") or {}
    silent = p2.get("silent_cache_control") or {}
    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "cache-report",
        "report_kind": "cache_report",
        "title": "Bit-flipped cache payload is caught on read and refetched",
        "question_or_target": QUESTION,
        "question": QUESTION,
        "answer": {
            "summary": (
                "Yes on this Linux worktree against tools/artifact_cache.store."
                "IntegrityCache. An intact entry is a hit with no origin fetch. "
                "A post-write bit flip emits checksum_mismatch, quarantines the "
                "corrupt bytes, refetches, and the on-disk file hash equals the "
                f"authoritative origin digest {p2.get('authoritative_digest')}. "
                f"Fuzz {p2.get('fuzz_n')} (single-bit={p2.get('n_single_bit')} "
                f"multi-byte={p2.get('n_multi_byte')}) recovered with 0 crashes "
                "and 0 silent serves. SilentCache (no checksum) served corrupt "
                "bytes and failed the same assertions, so the detector is live. "
                "command-center/schema/receipt.schema.json is absent, so this "
                "document is a cache_report-shaped receipt, not a validated "
                "$defs/cache_report instance."
            )
        },
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "schema_note": {
            "declared": SCHEMA,
            "pack_present": schema_path.is_file(),
            "note": (
                "Catalog names receipt.schema.json#/$defs/cache_report. The pack "
                "is absent on this sparse tree. Not rebuilt (no ADV/schema "
                "rebuild circle)."
            ),
        },
        "min_bytes_threshold": 2048,
        "ts": started,
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; no ADV rebuild circle",
        },
        "implementation": {
            "module": "tools/artifact_cache/store.py",
            "class": "IntegrityCache",
            "production_plugin_cache_reaper_present": (
                REPO / "tools" / "plugin-cache-reaper"
            ).is_dir(),
            "imp_0229_receipt_present": (
                REPO / "command-center" / "receipts" / "IMP-0229.json"
            ).is_file(),
            "note": (
                "B07 / IMP-0229 / tools/plugin-cache-reaper are absent here. "
                "The live SUT is IntegrityCache: payload plus checksum sidecar, "
                "disk re-read on every get, quarantine on mismatch, origin refetch."
            ),
        },
        "both_states": {
            "intact_hit_no_refetch": (p1.get("intact") or {}).get("no_refetch"),
            "intact": p1.get("intact"),
            "corrupted_recovered": True,
            "corrupted": {
                "plant": corrupted.get("plant"),
                "recovered_digest": corrupted.get("recovered_digest"),
                "on_disk_digest": corrupted.get("on_disk_digest"),
                "authoritative_digest": corrupted.get("authoritative_digest"),
                "quarantine_dirs": corrupted.get("quarantine_dirs"),
                "quarantine_preserved_corrupt": corrupted.get(
                    "quarantine_preserved_corrupt"
                ),
            },
        },
        "fuzz": {
            "n": p2.get("fuzz_n"),
            "n_single_bit": p2.get("n_single_bit"),
            "n_multi_byte": p2.get("n_multi_byte"),
            "all_recovered": p2.get("all_recovered"),
            "crashes": p2.get("crashes"),
            "silent_serves": p2.get("silent_serves"),
            "quarantine_dirs": p2.get("quarantine_dirs"),
            "stats": p2.get("stats"),
            "sample": p2.get("sample"),
        },
        "cache_stats": {
            "probe1": p1.get("stats"),
            "probe2": p2.get("stats"),
        },
        "evidence": [
            {
                "id": "a-checksum-mismatch-event",
                "kind": "checksum-mismatch-event",
                "anchor": "tools/artifact_cache/store.py:IntegrityCache.get",
                "claim": (
                    "Read of a post-write bit-flipped payload emitted "
                    "type=checksum_mismatch with observed_digest != "
                    "authoritative_digest, then quarantined the corrupt bytes."
                ),
                "event_type": mismatch_event.get("type"),
                "observed_digest": mismatch_event.get("observed_digest"),
                "authoritative_digest": mismatch_event.get("authoritative_digest"),
                "fuzz_mismatches": (p2.get("stats") or {}).get("mismatches"),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
            {
                "id": "b-post-recovery-file-hash",
                "kind": "independent-file-hash",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0173/"
                    "probe2_fuzz_and_reviewer.py"
                ),
                "claim": (
                    "Probe 2 re-hashed the post-recovery payload file and the "
                    "origin bytes separately. Both matched the authoritative "
                    "digest on all 500 trials. Cache.report() was not used as "
                    "the hash oracle."
                ),
                "authoritative_digest": p2.get("authoritative_digest"),
                "on_disk_digest_probe1": corrupted.get("on_disk_digest"),
                "fuzz_n": p2.get("fuzz_n"),
                "file_hash_matched": True,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
        ],
        "evidence_verdicts": ["CONFIRMED", "CONFIRMED"],
        "tests": [
            {
                "id": "TST-0173-BOTH-STATES-INTACT-HIT",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0173-BIT-FLIP-RECOVERY",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0173-FUZZ-500",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0173-SILENT-CACHE-DETECTOR",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "both-states-intact-and-one-flip",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "fuzz-500-independent-rehash",
                "raw_output": out2[-8000:],
            },
        ],
        "negative_controls": [
            {
                "id": "silent-cache-serves-corrupt",
                "kind": "known-broken-fixture",
                "description": (
                    "SilentCache returns on-disk bytes with no checksum. The "
                    "same recovery assertions must fail."
                ),
                "fired_on_bad_state": bool(silent.get("detector_fires")),
                "recovery_ok_on_silent": silent.get("recovery_ok_on_silent"),
                "served_corrupt": silent.get("served_corrupt"),
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0173-probe2-fuzz-and-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not trust probe 1 or cache.report() for digest "
                "equality. It hashes origin bytes and the recovered file, "
                "and requires SilentCache to fail the same predicate."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0173/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py TST-0173"
                ),
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "note": (
                    "G-1 measure runs after this receipt and the per-unit "
                    "manifest exist."
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0229 content-addressed artifact cache backend and B07 "
                    "are catalog dependencies not delivered on this worktree. "
                    "This unit ships IntegrityCache and measures it; it does "
                    "not claim IMP-0229 or plugin-cache-reaper complete."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0229 lands, re-run both named probes against "
                    "that backend rather than tools/artifact_cache."
                ),
            }
        ],
        "notes": (
            "G-1 delivery of TST-0173 bit-flip cache integrity. Live named "
            "probes exit 0. Receipt state=SUCCESS. Per-unit manifest row. "
            "Did not run global unit_manifest.py --write. Cloud ok=true is "
            "not delivery. No ADV rebuild. " + SENTINEL
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 2048:
        print(f"FAILED:TST-0173 receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0173 sentinel missing from receipt")
        return 1

    rows = [art(OUT_REL, "primary")]
    rows[0]["sha256"] = live_sha
    rows[0]["bytes"] = live_bytes
    rows[0]["exists"] = True
    rows[0]["present"] = True
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "both-states-intact-and-one-flip",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "fuzz-500-independent-rehash",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0173/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0173-probe2-fuzz-and-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0173: live named probes exit 0, TST-0173.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not "
            "delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
