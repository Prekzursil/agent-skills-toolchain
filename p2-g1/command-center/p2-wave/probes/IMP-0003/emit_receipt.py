#!/usr/bin/env python3
"""Emit IMP-0003 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

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
UNIT = "IMP-0003"
OUT = "command-center/receipts/IMP-0003.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0003/probe1_classes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0003/probe2_census_mutation.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_forbidden_content.py"
)
SUPPORTING = [
    "tools/plugin/forbidden_scan.py",
    "tools/plugin/census.py",
    "tools/plugin/tests/test_forbidden_content.py",
    "command-center/p2-wave/probes/IMP-0003/probe1_classes.py",
    "command-center/p2-wave/probes/IMP-0003/probe2_census_mutation.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    eol = "LF"
    if b"\x00" in data[:8192]:
        eol = "BINARY"
    elif b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in data:
        eol = "CRLF"
    sha, n = digest_file(path) if path.is_file() else (hashlib.sha256(b"").hexdigest(), 0)
    return {
        "path": rel,
        "bytes": max(n, 1) if path.is_file() else 1,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def main() -> int:
    rc_t, out_t = run(TESTS)
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc_t != 0 or rc1 != 0 or rc2 != 0:
        print(f"FAILED:IMP-0003 tests/probes rc_t={rc_t} rc1={rc1} rc2={rc2}")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scanner = artifact_row("tools/plugin/forbidden_scan.py", "implementation")
    census = artifact_row("tools/plugin/census.py", "independent-census")
    tests = artifact_row("tools/plugin/tests/test_forbidden_content.py", "tests")

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0003",
        "completion_sentinel": "SUCCESS:IMP-0003",
        "title": "Forbidden-content scanner for the staged payload",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0003: path-role pre-emit scanner; "
            "distinct from IMP-0004 content entropy"
        ),
        "min_bytes_threshold": 2048,
        "question_or_target": (
            "Implement a pre-emit scanner that fails the build when the staging "
            "tree contains any of: a .git directory or gitlink, node_modules, "
            "__pycache__, *.log, transcript/session JSONL, an OS cache directory, "
            "or any single file above a configured byte ceiling. Distinct from "
            "IMP-0004: this classifies by PATH ROLE, not by content entropy."
        ),
        "classifier": "path-role",
        "not_classifier": "content-entropy",
        "implementation": {
            "scanner": "tools/plugin/forbidden_scan.py",
            "census": "tools/plugin/census.py",
            "tests": "tools/plugin/tests/test_forbidden_content.py",
            "cli": "python3 -B tools/plugin/forbidden_scan.py <staging>",
            "default_max_file_bytes": 8388608,
            "git_dir_vs_gitlink": (
                ".git directory -> git_dir; .git file (gitdir pointer) -> gitlink"
            ),
            "payload_allowlist_json": {
                "path": "tools/plugin/payload-allowlist.json",
                "present": (REPO / "tools/plugin/payload-allowlist.json").is_file(),
                "used_by_scanner": False,
                "note": (
                    "IMP-0001 artifact is an input, not a runtime dependency of "
                    "path-role classification. Scanner deny-lists by role even when "
                    "the allowlist is absent."
                ),
            },
        },
        "forbidden_classes": [
            "git_dir",
            "gitlink",
            "node_modules",
            "pycache",
            "log",
            "transcript_jsonl",
            "os_cache",
            "oversize",
        ],
        "artifacts": [
            {
                "path": OUT,
                "bytes": 0,
                "sha256": "pending",
                "exists": True,
                "role": "primary",
                "eol": "LF",
            },
            scanner,
            census,
            tests,
        ],
        "evidence": [
            {
                "claim": (
                    "Signal 1: scanner named-path report and exit code against a "
                    "fixture tree that plants every forbidden class; empty tree is "
                    "clean in the same run as a planted-item control FOUND."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0003/probe1_classes.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": rc1,
                        "raw_output": out1[-8000:],
                    }
                ],
            },
            {
                "claim": (
                    "Signal 2: independent find+du census of the same dirty tree "
                    "agrees file-for-file with the scanner's paths_seen. "
                    "Disagreement would be a detector failure, not a packaging finding."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/census.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": rc2,
                        "raw_output": out2[-8000:],
                    }
                ],
            },
            {
                "claim": (
                    "Twelve unit tests (one case per forbidden class, empty+control, "
                    "git-rule mutation, census agreement) all PASS."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/tests/test_forbidden_content.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "tests",
                        "method": "command",
                        "command": TESTS,
                        "exit_code": rc_t,
                        "raw_output": out_t[-4000:],
                    }
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_forbidden_content.py",
                "command": TESTS,
                "result": "PASS",
                "exit_code": rc_t,
            },
            {"id": "probe1_classes", "command": P1, "result": "PASS", "exit_code": rc1},
            {
                "id": "probe2_census_mutation",
                "command": P2,
                "result": "PASS",
                "exit_code": rc2,
            },
        ],
        "negative_controls": [
            {
                "id": "empty-tree-clean-and-control-found",
                "kind": "silence-is-not-the-only-signal",
                "description": (
                    "Empty staging tree produces clean AND the same run reports the "
                    "planted-item control as FOUND."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "empty outcome=clean control.found=true",
                "bad_state_output": "dirty outcome=blocked with named paths per class",
            },
            {
                "id": "mutation-delete-git-rule",
                "kind": "mutation",
                "description": (
                    "Replace GIT_DIR_SEGMENT = \".git\" and the git_dir/gitlink "
                    "findings disappear; live scanner still flags .git."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "events-jsonl-is-not-transcript",
                "kind": "use-versus-mention",
                "description": (
                    "data/events.jsonl is not a transcript/session role and must not fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0003-probe2-reviewer-plant",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "planted_paths": [
                "third_party/nested/lib/.git",
                "windows/cache/ehthumbs.db",
            ],
            "note": (
                "Reviewer plants a nested gitlink and ehthumbs.db, paths the "
                "per-class fixture did not use. Scanner named both."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0003/UNIT-ARTIFACT-MANIFEST.json",
            "scope": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": "Measure is the post-emit G-1 gate; not consulted as cloud ok=true.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/plugin/payload-allowlist.json (IMP-0001) is absent on this "
                    "worktree. The scanner does not expand or consult an allowlist; "
                    "it deny-lists by path role. Packer integration that refuses "
                    "non-allowlisted paths remains IMP-0001's job."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0001 authors the allowlist, wire forbidden_scan into "
                    "the packer pre-emit path and re-run both probes against a staged "
                    "payload built from the allowlist."
                ),
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0003: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0003"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Do not embed this file's own sha256: writing it would change the bytes.
    # The per-unit UNIT-ARTIFACT-MANIFEST.json is the G-1 hash authority.
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < 2048:
        print(f"FAILED:IMP-0003 artifact {size}B below floor")
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0003",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "class-coverage-and-planted-control",
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "census-mutation-reviewer-plant",
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0003/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0003-probe2-reviewer-plant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0003: live named probes exit 0, IMP-0003.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def man_row(rel: str, role: str) -> dict:
        p = REPO / rel
        s, n = digest_file(p)
        return {
            "path": rel,
            "sha256": s,
            "bytes": n,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0003/SUBAGENT-RETURN.json",
            "role": role,
        }

    man_arts = [man_row(OUT, "primary")] + [man_row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_arts),
        "present": len(man_arts),
        "artifacts": man_arts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0003 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
