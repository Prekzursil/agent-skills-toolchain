#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0197.json (portability_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import campaign as C  # noqa: E402
import enumerator as E  # noqa: E402

OUT = "command-center/receipts/TST-0197.json"
UNIT = "TST-0197"
SENTINEL = "SUCCESS:TST-0197"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/portability_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0197/probe1_enumerator_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0197/probe2_dir_listing.py"
)
QUESTION = (
    "Does the enumerator survive files named NUL/CON/AUX/PRN/COM1/LPT1 in a "
    "scanned tree, using the extended-length prefix where required? PASS "
    "requires a complete count with the reserved entries reported, never an "
    "exception and never a silent zero."
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0197/enumerator.py",
    "command-center/p2-wave/probes/TST-0197/fixture.py",
    "command-center/p2-wave/probes/TST-0197/naive.py",
    "command-center/p2-wave/probes/TST-0197/dirlist.py",
    "command-center/p2-wave/probes/TST-0197/campaign.py",
    "command-center/p2-wave/probes/TST-0197/probe1_enumerator_count.py",
    "command-center/p2-wave/probes/TST-0197/probe2_dir_listing.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    result = C.run_campaign()
    if not result["pass"]:
        print(f"FAILED:{UNIT} campaign checks {json.dumps(result['checks'], sort_keys=True)}")
        return 1

    enum_h = result["enumerator_hostile"]
    enum_o = result["enumerator_ordinary"]
    list_h = result["dirlist_hostile"]
    planted = result["planted_hostile"]
    seed = result["regression_seed"]
    naive_zero = result["naive_swallowed"]
    naive_raise = result["naive_raising"]
    posix = result["posix_relpath_nul"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    baseline = REPO / "command-center/BASELINE-SNAPSHOT.json"
    user_prompts = REPO / "_USER-PROMPTS.md"

    artifacts = [art(p, "supporting") for p in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "portability_report",
        "output_schema": SCHEMA,
        "title": "Reserved device names do not crash tree enumeration",
        "question": QUESTION,
        "answer": (
            "YES on this Linux worktree. A scandir walker that accumulates "
            "relative paths from directory-entry names completes over a planted "
            f"tree of {planted['planted_count']} files including "
            f"{list(E.RESERVED_BASENAMES)}, reports every reserved basename, "
            "and matches an independent os.listdir count. It never calls "
            "os.path.relpath. The Phase-0 seed is reproduced with ntpath: "
            f"{seed['nul_message']}. Swallowing that ValueError yields count=0 "
            "while the files still exist. posixpath.relpath does not raise on "
            "a real file named NUL here; the crash is Windows device-namespace "
            "collapse, not POSIX. Extended-length `\\\\?\\` forms are recorded "
            "per reserved entry; live `\\\\?\\` open is used only when os.name=='nt'."
        ),
        "spec_anchor": (
            "catalog TST-0197 / Phase-0 ValueError: path is on mount '\\\\.\\NUL'"
        ),
        "min_bytes_threshold": 2048,
        "named_inputs": [
            {
                "path": "_USER-PROMPTS.md",
                "present": user_prompts.is_file(),
                "note": "catalog cites :11016 layer 28 and :11309; file absent on this worktree"
                if not user_prompts.is_file()
                else "present",
            },
            {
                "path": "command-center/BASELINE-SNAPSHOT.json",
                "present": baseline.is_file(),
            },
        ],
        "platform": {
            "os_name": enum_h["os_name"],
            "enumerator_api": enum_h["api"],
            "dirlist_api": list_h["api"],
            "used_os_path_relpath": False,
            "extended_length_open_live": enum_h["os_name"] == "nt",
        },
        "evidence": {
            "enumerator_count": {
                "signal": "(a) the enumerator's returned count with reserved names present",
                "count": enum_h["count"],
                "complete": enum_h["complete"],
                "exception": enum_h["exception"],
                "reserved": enum_h["reserved"],
                "reserved_basenames_found": enum_h["reserved_basenames_found"],
                "known_present_found": enum_h["known_present_found"],
                "planted_count": planted["planted_count"],
                "rels": enum_h["rels"],
                "errors": enum_h["errors"],
                "sample_extended_length_forms": [
                    {
                        "rel": f["rel"],
                        "extended_length_form": f["extended_length_form"],
                        "device_namespace_form": f["device_namespace_form"],
                    }
                    for f in enum_h["files"]
                    if f["reserved"]
                ],
            },
            "dir_listing": {
                "signal": "(b) an independent count from a different API (dir listing) over the same tree",
                "api": list_h["api"],
                "count": list_h["count"],
                "complete": list_h["complete"],
                "rels": list_h["rels"],
                "matches_enumerator": sorted(list_h["rels"]) == sorted(enum_h["rels"]),
            },
        },
        "tests": [
            {
                "id": "TST-0197-DETECTOR-CONTROL-KNOWN-PRESENT",
                "result": "PASS",
                "name": (
                    "detector control: enumerator finds a KNOWN-PRESENT ordinary "
                    "file in the same tree before trusting any count"
                ),
            },
            {
                "id": "TST-0197-REGRESSION-NTPATH-NUL",
                "result": "PASS",
                "name": (
                    "regression seed: ntpath.relpath raises ValueError on "
                    "\\\\.\\NUL (Windows os.path.relpath identity)"
                ),
                "message": seed["nul_message"],
            },
            {
                "id": "TST-0197-RESERVED-REPORTED",
                "result": "PASS",
                "name": "complete count reports NUL/CON/AUX/PRN/COM1/LPT1",
            },
            {
                "id": "TST-0197-COUNTS-MATCH",
                "result": "PASS",
                "name": "enumerator count equals independent os.listdir count",
            },
            {
                "id": "TST-0197-BOTH-STATES-ORDINARY-TREE",
                "result": "PASS" if not enum_o["reserved"] else "FAIL",
                "name": "ordinary-only tree: no reserved names, known-present still found",
            },
        ],
        "negative_controls": [
            {
                "id": "naive-ntpath-swallow-silent-zero",
                "kind": "known-broken-enumerator",
                "fired_on_bad_state": naive_zero.get("count") == 0
                and naive_zero.get("swallowed") is True,
                "silent_on_good_state": enum_h["count"] == planted["planted_count"],
                "description": (
                    "ntpath.relpath on \\\\.\\NUL raises; swallowing it returns "
                    "count=0 while reserved files remain on disk"
                ),
                "bad_state_output": naive_zero.get("swallowed_error"),
                "good_state_output": f"safe enumerator count={enum_h['count']}",
            },
            {
                "id": "posix-relpath-does-not-raise",
                "kind": "platform-difference",
                "fired_on_bad_state": seed["nul_raises_valueerror"],
                "silent_on_good_state": posix["raises"] is False,
                "description": (
                    "posixpath.relpath on a real file named NUL does not raise "
                    "on this Linux host; the crash requires ntpath + device namespace"
                ),
            },
        ],
        "regression_seed": {
            "module": "ntpath",
            "path": r"\\.\NUL",
            "raises_valueerror": seed["nul_raises_valueerror"],
            "message": seed["nul_message"],
            "naive_raising": naive_raise.get("raised"),
            "naive_swallowed_count": naive_zero.get("count"),
        },
        "reviewer": {
            "reviewer_id": "TST-0197-probe2-dir-listing",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 recounts the same planted tree with os.listdir "
                "(not os.scandir) and requires the reserved basenames to appear "
                "in that listing. Catalog second-shell (pwsh7 vs Git Bash on "
                "Windows) review is not claimed on this Linux worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live Windows CreateFileW of a file named NUL via \\\\?\\ "
                    "was not executed; this host is POSIX. Extended-length "
                    "forms are computed and recorded, not opened."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 on a Windows shell (pwsh7 and Git "
                    "Bash) over a \\\\?\\-created reserved-name tree."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement (second Windows shell) is not "
                    "satisfied by this Linux run."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Independent reviewer re-runs probe2 under pwsh7 and Git Bash.",
            },
        ],
        "scope": {
            "proof_surface": (
                "planted reserved-name tree + scandir enumerator + os.listdir "
                "cross-count + ntpath.relpath ValueError seed"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "a Windows pwsh7 / Git Bash reviewer re-ran the probe",
                "product-side long-path behaviour (TST-0335 / layer 29)",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "portability-tester",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "enumerator-count", "command": P1},
            {"id": "probe2", "role": "dir-listing", "command": P2},
        ],
        "artifacts": artifacts,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0197/UNIT-ARTIFACT-MANIFEST.json",
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
        "defects": [],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"{SENTINEL} receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
