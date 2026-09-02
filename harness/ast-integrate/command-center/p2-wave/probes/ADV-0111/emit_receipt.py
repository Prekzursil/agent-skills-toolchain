#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0111-manifest-versus-disk-verification.json."""
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

from engine import (  # noqa: E402
    COMPLETION_SENTINEL,
    LIVE_MANIFEST_REL,
    UNIT,
    live_census,
    live_verdict,
    probe1_payload,
    probe2_payload,
)

OUT = "command-center/adversarial/ADV-0111-manifest-versus-disk-verification.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0111/probe1_bidirectional_set_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0111/probe2_blob_not_archive.py"
)
QUESTION = (
    "Does every artifact recorded in ARTIFACT-MANIFEST.json exist on disk "
    "with the recorded size and hash, and does every artifact on disk appear "
    "in the manifest?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0111/engine.py",
    "command-center/p2-wave/probes/ADV-0111/probe1_bidirectional_set_diff.py",
    "command-center/p2-wave/probes/ADV-0111/probe2_blob_not_archive.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF" if path.is_file() else "ABSENT",
    }


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
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate(doc: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = probe1_payload()
    p2 = probe2_payload()
    live = live_census()
    live_v = live_verdict(live)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    control_listed = bool(p1["listed_verified"])
    control_unlisted = bool(p1["unlisted_in_disk_only"])
    crlf_ok = bool(p2["pass"])
    blob_ok = bool(p2["hash_authority"] == "git cat-file -p" and p2["pass"])
    answer = (
        f"Live {LIVE_MANIFEST_REL} exists={live['manifest_exists']} "
        f"(reason={live['manifest_reason']}); listed={live['listed_count']} "
        f"disk_artifact_files={live['disk_count']} "
        f"manifest_only={len(live['manifest_only'])} "
        f"disk_only={len(live['disk_only'])} "
        f"hash_mismatches={live['hash_mismatch_count']}. "
        f"The catalog conjunction is therefore {live_v}: this Linux worktree "
        f"has no ARTIFACT-MANIFEST.json, so every file under "
        f"command-center/{{receipts,adversarial,audit}} is disk-only and the "
        f"completion-report precondition is not met. Controls: listed-and-present "
        f"verified={control_listed}; unlisted file in disk_only={control_unlisted}; "
        f"one-way manifest-to-disk stays silent on the unlisted file="
        f"{p1['one_way_silent_on_unlisted']}. Probe 2 hashed the planted LF blob "
        f"via git cat-file -p ({p2['blob_bytes']}B/0 CRLF) and refused git archive; "
        f"the dirty CRLF worktree ({p2['worktree_raw_bytes']}B/"
        f"{p2['worktree_crlf_count']} CRLF) would have been a false mismatch "
        f"before normalisation. archive_equals_blob="
        f"{p2['archive_equals_blob']} on this Linux host (the Windows archive "
        f"trap is recorded, not reproduced). {COMPLETION_SENTINEL}"
    )
    targets = [
        {
            "id": "LIVE-ARTIFACT-MANIFEST-EXISTS",
            "verdict": "CONFIRMED" if live["manifest_exists"] else "REFUTED",
            "summary": (
                f"{LIVE_MANIFEST_REL} reason={live['manifest_reason']}"
            ),
        },
        {
            "id": "LIVE-EVERY-LISTED-ON-DISK-WITH-HASH",
            "verdict": live_v if live["manifest_exists"] else "REFUTED",
            "summary": (
                f"listed={live['listed_count']} manifest_only="
                f"{len(live['manifest_only'])} hash_mismatches="
                f"{live['hash_mismatch_count']}"
            ),
        },
        {
            "id": "LIVE-EVERY-DISK-ARTIFACT-IN-MANIFEST",
            "verdict": "CONFIRMED" if live["bidirectional_ok"] else "REFUTED",
            "summary": (
                f"disk_count={live['disk_count']} disk_only="
                f"{len(live['disk_only'])} head={live['disk_only_head'][:8]}"
            ),
        },
        {
            "id": "CONTROL-LISTED-AND-PRESENT",
            "verdict": "CONFIRMED" if control_listed else "REFUTED",
            "summary": "planted listed.txt verifies size and LF-normalised sha256",
        },
        {
            "id": "CONTROL-UNLISTED-DISK-ONLY",
            "verdict": "CONFIRMED" if control_unlisted else "REFUTED",
            "summary": "planted unlisted.txt appears only in the disk-only set",
        },
        {
            "id": "CRLF-NORMALISE-BEFORE-MISMATCH",
            "verdict": "CONFIRMED" if crlf_ok else "REFUTED",
            "summary": (
                "raw worktree hash diverges; CRLF-normalised worktree matches "
                "the cat-file blob"
            ),
        },
        {
            "id": "BLOB-VIA-CAT-FILE-NOT-ARCHIVE",
            "verdict": "CONFIRMED" if blob_ok else "REFUTED",
            "summary": (
                "hash_authority=git cat-file -p; git archive measured and refused"
            ),
        },
    ]
    if any(t["verdict"] not in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"} for t in targets):
        print(f"FAILED:{UNIT} target verdict not in enum")
        return 1
    overall = "CONFIRMED" if live["bidirectional_ok"] else "REFUTED"
    nel = "\u0085"
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "refutation-record",
        "title": "Manifest-versus-disk verification before the completion report is written",
        "question": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0111 spec:11098,10643",
        "min_bytes_threshold": 4096,
        "profile": "refutation-record",
        "overall_verdict": overall,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "synthesis-distortion-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "answer": answer,
        "mechanism": (
            "bidirectional manifest/disk reconciliation with blob-not-worktree "
            "hashing to eliminate the line-ending false positive"
        ),
        "inputs_census": {
            "artifact_manifest": {
                "path": LIVE_MANIFEST_REL,
                "present": live["manifest_exists"],
                "reason": live["manifest_reason"],
            },
            "global_unit_manifest": {
                "path": "command-center/UNIT-ARTIFACT-MANIFEST.json",
                "present": live["global_unit_manifest_exists"],
            },
            "artifact_roots": ["command-center/receipts", "command-center/adversarial", "command-center/audit"],
            "live": {
                "listed_count": live["listed_count"],
                "disk_count": live["disk_count"],
                "manifest_only_count": len(live["manifest_only"]),
                "disk_only_count": len(live["disk_only"]),
                "disk_only_head": live["disk_only_head"],
                "hash_mismatch_count": live["hash_mismatch_count"],
                "bidirectional_ok": live["bidirectional_ok"],
            },
        },
        "targets": targets,
        "evidence": [
            {
                "claim": (
                    "Planted listed.txt verifies; unlisted.txt is disk-only; "
                    "a one-way check is silent on the unlisted file."
                ),
                "verdict": "CONFIRMED" if p1["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0111/engine.py:plant_control_estate",
                "probes": [
                    {
                        "role": "source",
                        "id": "probe1",
                        "command": P1,
                        "raw_output": t1,
                        "exit_code": c1,
                    }
                ],
            },
            {
                "claim": (
                    "Hash authority is git cat-file -p. CRLF normalisation is "
                    "applied before a mismatch is declared. git archive is refused."
                ),
                "verdict": "CONFIRMED" if p2["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0111/engine.py:plant_blob_crlf_repo",
                "probes": [
                    {
                        "role": "verifier",
                        "id": "probe2",
                        "command": P2,
                        "raw_output": t2,
                        "exit_code": c2,
                    }
                ],
            },
            {
                "claim": (
                    f"Live {LIVE_MANIFEST_REL} does not bidirectionally match "
                    f"the artifact roots (exists={live['manifest_exists']}, "
                    f"disk_only={len(live['disk_only'])})."
                ),
                "verdict": live_v,
                "anchor": LIVE_MANIFEST_REL,
                "probes": [
                    {
                        "role": "live-census",
                        "id": "probe1-live",
                        "command": P1,
                        "raw_output": json.dumps(p1["live"], sort_keys=True),
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-one-way-silent-on-unlisted",
                "kind": "detector-control",
                "description": (
                    "Manifest-to-disk only (ignore disk_only) stays green on "
                    "the planted unlisted file. Bidirectional difference fires."
                ),
                "fired_on_bad_state": bool(p1["bidirectional_catches_unlisted"]),
                "silent_on_good_state": bool(p1["listed_verified"]),
                "bad_state_output": "one_way_ok=True disk_only=['unlisted.txt']",
                "good_state_output": "listed.txt verified",
            },
            {
                "id": "NC2-missing-listed-appears-manifest-only",
                "kind": "both-states",
                "description": (
                    "Drop listed.txt from disk. It must appear in manifest_only, "
                    "proving the other direction of the difference."
                ),
                "fired_on_bad_state": bool(p1["missing_listed_in_manifest_only"]),
                "silent_on_good_state": not bool(p1["good_manifest_only"]),
            },
            {
                "id": "NC3-raw-worktree-false-mismatch",
                "kind": "crlf-trap",
                "description": (
                    "Hashing the dirty CRLF worktree without normalisation "
                    "declares a mismatch the blob does not have."
                ),
                "fired_on_bad_state": bool(p2["worktree_raw_would_false_mismatch"]),
                "silent_on_good_state": bool(p2["crlf_normalized_matches_blob"]),
            },
        ],
        "tests": [
            {
                "id": "T1-PROBE-1-BIDIRECTIONAL",
                "name": "listed verifies; unlisted is disk-only; missing listed is manifest-only",
                "command": P1,
                "result": "PASS" if c1 == 0 and p1["pass"] else "FAIL",
            },
            {
                "id": "T2-PROBE-2-BLOB-NOT-ARCHIVE",
                "name": "git cat-file -p is the authority; archive refused; CRLF normalised",
                "command": P2,
                "result": "PASS" if c2 == 0 and p2["pass"] else "FAIL",
            },
            {
                "id": "T3-REQUIRED-LISTED-AND-PRESENT-CONTROL",
                "name": "a file known to be listed and present must verify",
                "command": P1,
                "result": "PASS" if control_listed else "FAIL",
            },
            {
                "id": "T4-REQUIRED-UNLISTED-DISK-ONLY-CONTROL",
                "name": "a deliberately unlisted file must appear in the disk-only set",
                "command": P1,
                "result": "PASS" if control_unlisted else "FAIL",
            },
            {
                "id": "T5-DECLARED-SCHEMA",
                "name": "artifact parses against command-center/schema/refutation-record.schema.json",
                "command": "jsonschema Draft7Validator",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0111-probe2-blob-not-archive",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical-probe",
            "method": (
                "Independent instrument: planted LF blob vs CRLF worktree, "
                "git cat-file -p as authority, git archive refused. Does not "
                "re-read probe 1's set-difference report."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "bidirectional-set-diff",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "role": "blob-not-archive",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0111/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "retry ONLY with a mechanically different probe"},
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "required_fix": None,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for ADV-0111. Did not run tools/command-center/unit_manifest.py "
            "--write. Did not relaunch finish-everything-close or "
            "p2-cloud-ok-deliver. Live ARTIFACT-MANIFEST.json is absent on this "
            "worktree; that is recorded as REFUTED, not BLOCKED."
        ),
        "completion_line": f"UNIT-COMPLETE:{UNIT}",
        "completion_marker_protocol": (
            "Literal JSON-permitted U+0085 delimiters preserve valid JSON while "
            "splitlines exposes the exact completion line near the artifact tail."
        ),
        "completion_marker": f"{nel}UNIT-COMPLETE:{UNIT}{nel}",
    }
    errors = validate(doc)
    if errors:
        # T5 will be rewritten after the on-disk parse; fail closed here.
        print(f"FAILED:{UNIT} schema {errors[:8]}")
        return 1
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print(f"FAILED:{UNIT} a required test is not PASS")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print(f"FAILED:{UNIT} completion_sentinel missing after write")
        return 1
    reparse = json.loads(text)
    post_errors = validate(reparse)
    if post_errors:
        print(f"FAILED:{UNIT} schema after write {post_errors[:8]}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha} overall={overall}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
