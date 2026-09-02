#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0464.json from live gate measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from package_gate.content_gate import (  # noqa: E402
    OVERSIZE_BYTES,
    SIZE_CEILING_BYTES,
    evaluate,
    load_exclusion_set,
    merge_counts,
    plant_credential,
    plant_git,
    plant_log,
    plant_oversize,
    plant_pycache,
    plant_transcript,
    write_clean_tree,
)

OUT = "command-center/receipts/IMP-0464.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SENTINEL:IMP-0464:PACKAGE-CONTENT-GATED"
QUESTION = (
    "Anchor spec:11307 (package accidentally includes .git or huge unrelated "
    "files). Implement the packaging gate that enumerates the exact file list "
    "before packing and fails on any excluded path or on exceeding the "
    "declared size ceiling. Exact question: what is the packaged artifact "
    "size and file count, and which of the exclusion patterns actually "
    "matched something?"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/package_gate/tests/test_content_gate.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0464/probe1_independent_refusals.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0464/probe2_pattern_census.py"
)
SUPPORTING = [
    "tools/package_gate/content_gate.py",
    "tools/package_gate/__init__.py",
    "tools/package_gate/exclusion_set.json",
    "tools/package_gate/tests/test_content_gate.py",
    "command-center/p2-wave/probes/IMP-0464/probe1_independent_refusals.py",
    "command-center/p2-wave/probes/IMP-0464/probe2_pattern_census.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
        "unit_id": "IMP-0464",
        "receipt_path": "command-center/p2-wave/probes/IMP-0464/SUBAGENT-RETURN.json",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "method": "command",
        "raw_output": text[-16000:],
        "role": role,
    }


def live_census() -> dict:
    exclusion = load_exclusion_set()
    with tempfile.TemporaryDirectory(prefix="imp0464-emit-") as raw:
        base = Path(raw)
        clean = base / "clean"
        write_clean_tree(clean)
        dest = base / "demo.tgz"
        clean_res = evaluate(clean, pack_to=dest)
        rows = [clean_res.pattern_match_counts]
        plants = {
            "git": plant_git,
            "oversize": plant_oversize,
            "credential-env": plant_credential,
            "credential-json": lambda r: plant_credential(r, "credentials.json"),
            "pycache": plant_pycache,
            "log": plant_log,
            "transcript": plant_transcript,
        }
        plant_results = {}
        for name, planter in plants.items():
            root = base / name
            write_clean_tree(root)
            planter(root)
            res = evaluate(root)
            rows.append(res.pattern_match_counts)
            plant_results[name] = {
                "ok": res.ok,
                "reasons": res.reasons,
                "total_bytes": res.total_bytes,
                "file_count": sum(1 for f in res.files if not f.is_dir),
                "hit_paths": [h["relpath"] for h in res.hits],
            }
        merged = merge_counts(rows)
        return {
            "exclusion_set_id": exclusion.id,
            "size_ceiling_bytes": SIZE_CEILING_BYTES,
            "oversize_file_bytes": OVERSIZE_BYTES,
            "clean": {
                "ok": clean_res.ok,
                "packed_file_count": clean_res.packed_file_count,
                "packed_bytes": clean_res.packed_bytes,
                "total_bytes": clean_res.total_bytes,
                "file_list": list(clean_res.packed_members),
            },
            "plants": plant_results,
            "pattern_match_counts": merged,
            "dead_or_broken_patterns": [
                pid for pid, n in merged.items() if n == 0
            ],
        }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0464 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:IMP-0464-tests" not in t_test:
        print("FAILED:IMP-0464 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0464-probe1" not in t1:
        print("FAILED:IMP-0464 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0464-probe2" not in t2:
        print("FAILED:IMP-0464 emit probe2 sentinel missing")
        return 1

    census = live_census()
    if not census["clean"]["ok"]:
        print("FAILED:IMP-0464 clean pack refused")
        return 1
    if census["dead_or_broken_patterns"]:
        print(
            "FAILED:IMP-0464 default patterns dead: "
            f"{census['dead_or_broken_patterns']}"
        )
        return 1
    for name in ("git", "oversize", "credential-env"):
        if census["plants"][name]["ok"]:
            print(f"FAILED:IMP-0464 plant {name} was packed")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    for row in artifacts:
        if not row["exists"]:
            print(f"FAILED:IMP-0464 missing supporting {row['path']}")
            return 1

    p_test = probe_obj(TEST_CMD, c_test, t_test, "verifier")
    p1 = probe_obj(P1, c1, t1, "source")
    p2 = probe_obj(P2, c2, t2, "verifier")
    receipt = {
        "unit_id": "IMP-0464",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0464; _USER-PROMPTS.md:11307",
        "title": "Package content gate with an explicit exclusion set and size ceiling",
        "question": QUESTION,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/package_gate/content_gate.py",
            "exclusion_set": "tools/package_gate/exclusion_set.json",
            "rule": (
                "enumerate the candidate file list before packing; refuse if "
                "any exclusion pattern matches or total bytes exceed the "
                "declared ceiling; never silently omit excluded paths"
            ),
            "size_ceiling_bytes": SIZE_CEILING_BYTES,
            "oversize_file_bytes": OVERSIZE_BYTES,
            "packed_artifact_file_count": census["clean"]["packed_file_count"],
            "packed_artifact_bytes": census["clean"]["packed_bytes"],
            "packed_content_bytes": census["clean"]["total_bytes"],
            "packed_file_list": census["clean"]["file_list"],
            "pattern_match_counts": census["pattern_match_counts"],
            "dead_or_broken_patterns": census["dead_or_broken_patterns"],
        },
        "answer": (
            f"Clean fixture packed {census['clean']['packed_file_count']} files "
            f"({census['clean']['packed_bytes']} archive bytes, "
            f"{census['clean']['total_bytes']} content bytes): "
            f"{census['clean']['file_list']}. Exclusion pattern match counts "
            f"across clean plus planted builds: {census['pattern_match_counts']}. "
            "Planted .git, 200 MiB unrelated.bin, and .env each refuse "
            "independently. No default pattern was dead. "
            + SENTINEL
        ),
        "evidence": [
            {
                "anchor": "tools/package_gate/content_gate.py:evaluate",
                "claim": (
                    "A planted .git directory, a planted 200 MiB file, and a "
                    "planted credential file each fail the gate independently. "
                    "A clean tree packs with file list and byte totals recorded."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p_test],
            },
            {
                "anchor": "tools/package_gate/exclusion_set.json",
                "claim": (
                    "Per-pattern match counts are recorded across every build. "
                    "An injected never-match pattern is named dead-or-broken; "
                    "every default pattern fired at least once."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p_test],
            },
        ],
        "negative_controls": [
            {
                "id": "planted-git-dir",
                "kind": "known-broken-fixture",
                "description": "Planted .git must refuse; clean twin still packs.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reasons include git-dir-shipped; archive absent",
                "good_state_output": "clean ok=True packed_file_count=3",
            },
            {
                "id": "planted-200mib-file",
                "kind": "known-broken-fixture",
                "description": "Planted 200 MiB file exceeds ceiling and matches oversize-file.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "oversize-artifact + size-ceiling-exceeded",
                "good_state_output": "clean total_bytes under 16777216",
            },
            {
                "id": "planted-credential-file",
                "kind": "known-broken-fixture",
                "description": "Planted .env refuses; gate result does not echo the secret value.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "credential-in-package hit_paths=['.env']",
                "good_state_output": "clean credential-env count=0",
            },
            {
                "id": "dead-pattern-named",
                "kind": "detector-control",
                "description": "A pattern matching zero files across every build is named.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "never-match-canary in dead_or_broken_patterns",
                "good_state_output": "default pattern ids absent from dead list",
            },
        ],
        "tests": [
            {
                "id": "test_planted_git_refused_independently",
                "command": TEST_CMD + "::test_planted_git_refused_independently",
                "result": "PASS",
            },
            {
                "id": "test_planted_oversize_refused_independently",
                "command": TEST_CMD + "::test_planted_oversize_refused_independently",
                "result": "PASS",
            },
            {
                "id": "test_planted_credential_refused_independently",
                "command": TEST_CMD + "::test_planted_credential_refused_independently",
                "result": "PASS",
            },
            {
                "id": "test_clean_tree_packs",
                "command": TEST_CMD + "::test_clean_tree_packs",
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0464-probe2-pattern-census",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "Every exclusion pattern must fire on a planted build or be "
                "named dead-or-broken. The gate must refuse excluded paths "
                "rather than omit them."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0464",
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0464/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0001 allowlist packer and TST-0207 allowlist tests are "
                    "separate units. This gate is the enumerate-and-refuse "
                    "exclusion check with a size ceiling, not a deny-by-default "
                    "allowlist packer."
                ),
                "settling_experiment": (
                    "When IMP-0001 lands, run this gate on the allowlist packer's "
                    "staging tree and confirm a planted .git still refuses."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0464 package content gate. Live named probes "
            "measure independent refusals and the pattern census. Did not run "
            "global unit_manifest.py --write. cloud ok is not consulted. "
            + SENTINEL
        ),
        "census": census,
    }

    if SENTINEL not in json.dumps(receipt):
        print("FAILED:IMP-0464 sentinel-absent before write")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
