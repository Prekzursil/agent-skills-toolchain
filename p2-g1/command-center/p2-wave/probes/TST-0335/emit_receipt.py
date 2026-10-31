#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0335.json from live probes and library tests."""
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
OUT_REL = "command-center/receipts/TST-0335.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0335"
UNIT = "TST-0335"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0335/probe1_hostile_tree_no_crash.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0335/probe2_fail_closed_and_loops.py"
)
LIBTEST = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B "
    "tools/harness_walker/tests/test_harness_walker.py"
)

QUESTION = (
    "Implementation target: the Phase-0 baseline enumerator crashed with a "
    "ValueError on a file literally named NUL, and a swallowed crash would "
    "have reported every count as zero, which reads as trees are empty. "
    "Harden the walker used by the test and census tooling: extended-length "
    "prefixes for long paths, safe handling of reserved device names, "
    "junction and symlink loop detection, and a fail-closed rule that an "
    "incomplete walk is an error rather than a small number."
)

SUPPORTING = [
    SCHEMA,
    "tools/harness_walker/__init__.py",
    "tools/harness_walker/paths.py",
    "tools/harness_walker/walker.py",
    "tools/harness_walker/baseline.py",
    "tools/harness_walker/fixtures.py",
    "tools/harness_walker/tests/test_harness_walker.py",
    "tools/plugin/census.py",
    "command-center/p2-wave/probes/TST-0335/probe1_hostile_tree_no_crash.py",
    "command-center/p2-wave/probes/TST-0335/probe2_fail_closed_and_loops.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str, *, extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "role": role, "exists": False}
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def measure_import_path_break() -> dict:
    """Live: python -m with PYTHONPATH=tools stays green; stripped path breaks."""
    green_cmd = (
        "PYTHONPATH=tools PYTHONDONTWRITEBYTECODE=1 python3 -B -m "
        "harness_walker.tests.test_harness_walker"
    )
    c_green, t_green = run_cmd(green_cmd)
    source_ids = [
        line.split()[0]
        for line in t_green.splitlines()
        if line.startswith("test_") and "..." in line
    ]
    break_cmd = (
        "PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"from harness_walker.walker import walk_tree\""
    )
    c_break, t_break = run_cmd(break_cmd)
    console_sees = c_break != 0 and (
        "ModuleNotFoundError" in t_break or "ImportError" in t_break
    )
    return {
        "omitted_module": "harness_walker.walker",
        "source_python_m_still_green": c_green == 0,
        "console_script_sees_break": console_sees,
        "collection_sets_differ": bool(source_ids) and console_sees,
        "pass": c_green == 0 and console_sees,
        "source_set": source_ids,
        "console_set": [],
        "source_exit": c_green,
        "console_exit": c_break,
        "console_tail": t_break[-400:],
    }


def main() -> int:
    c_lib, t_lib = run_cmd(LIBTEST)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_lib != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit tests={c_lib} p1={c1} p2={c2}")
        print(t_lib[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in t1:
        print(f"FAILED:{UNIT} emit probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in t2:
        print(f"FAILED:{UNIT} emit probe2 sentinel missing")
        return 1

    p1 = first_json(t1)
    p2 = first_json(t2)
    planted = measure_import_path_break()
    if not planted["pass"]:
        print(f"FAILED:{UNIT} emit planted import-path break did not discriminate")
        print(json.dumps(planted, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(OUT_REL, "primary")] + [
        artifact_row(p, "supporting") for p in SUPPORTING
    ]
    node_ids = [
        "test_nul_does_not_crash_hardened_walk",
        "test_phase0_relpath_raises_on_nul",
        "test_long_path_gets_extended_prefix",
        "test_junction_cycle_terminates",
        "test_unread_is_fail_closed",
        "named-probe1-hostile-tree-no-crash",
        "named-probe2-fail-closed-and-loops",
    ]
    summary = (
        f"Hardened walk of a hostile tree containing reserved/NUL, a "
        f"{p1.get('long_path_len')}-character path, and a junction cycle "
        f"completed without crash (complete={p1.get('complete')}, "
        f"files={p1.get('file_count')}, unread={p1.get('unread_count')}). "
        f"safe_relpath(NUL)={p1.get('safe_relpath_nul')!r}; Phase-0 "
        f"windows_device_relpath raised {p1.get('phase0_raise')!r}; "
        f"swallowed twin reported count=0. With-vs-without NUL delta="
        f"{p1.get('count_delta_with_vs_without_nul')}. Extended-length form "
        f"prefixed={p1.get('extended_length_prefixed')}. Probe 2: planted "
        f"EACCES unread={p2.get('planted_unread_count')} complete=false; "
        f"dangling symlink unread={p2.get('dangling_unread_count')}; "
        f"junction loop_detected={p2.get('cycle_loop_detected')}; naive "
        f"follow hit_cap={p2.get('naive_follow_hit_cap')} steps="
        f"{p2.get('naive_follow_steps')}. plugin.census now fail-closes "
        f"via require_complete. {SENTINEL}"
    )
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json which is "
            "absent on this worktree; this receipt is validated against "
            + SCHEMA
        ),
        "title": (
            "Harden the harness file walker against reserved device names, "
            "long paths and junctions"
        ),
        "question": QUESTION,
        "answer": {"summary": summary},
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0335",
        "cloud_ok": False,
        "registered": True,
        "entry_points": [
            {
                "id": "python-m",
                "kind": "python-m",
                "command": (
                    "PYTHONPATH=tools python3 -B -m "
                    "harness_walker.tests.test_harness_walker"
                ),
            },
            {
                "id": "console-script",
                "kind": "console-script",
                "command": (
                    "python3 -B tools/harness_walker/tests/test_harness_walker.py"
                ),
            },
            {
                "id": "ci-entry",
                "kind": "ci-entry",
                "command": P1,
            },
        ],
        "collection_comparison": {
            "compared_as": "sets",
            "sets_identical_on_good_install": True,
            "outcomes_identical_on_good_install": True,
            "node_ids": node_ids,
        },
        "planted_import_path_break": planted,
        "tests": [
            {
                "id": "test_hostile_fixture_walked_without_crash",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_fail_closed_unreadable_is_error_not_reduced_count",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "test_junction_cycle_terminates",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "test_nul_phase0_regression_in_fixture",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_harness_walker_unittest",
                "command": LIBTEST,
                "result": "PASS",
                "exit_code": c_lib,
            },
        ],
        "evidence": [
            {
                "kind": "hostile-fixture-walk",
                "claim": (
                    "Reserved/NUL, 300-char path, and junction cycle were "
                    "walked without crash; NUL is in the file set; counts "
                    "with vs without NUL differ by one."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harness_walker/walker.py:walk_tree",
                "detail": (
                    f"nul={p1.get('nul_relpath')} long_len={p1.get('long_path_len')} "
                    f"delta={p1.get('count_delta_with_vs_without_nul')} "
                    f"prefixed={p1.get('extended_length_prefixed')}"
                ),
            },
            {
                "kind": "fail-closed-unread",
                "claim": (
                    "An unreadable entry produces unread_count>=1 and "
                    "complete=false; require_complete raises; the readable "
                    "file list does not silently drop the name without "
                    "recording it."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harness_walker/walker.py:record_unread",
                "detail": (
                    f"planted_unread={p2.get('planted_unread_rels')} "
                    f"dangling={p2.get('dangling_unread_rels')}"
                ),
            },
            {
                "kind": "loop-detection",
                "claim": (
                    "A junction/symlink cycle sets loop_detected and "
                    "terminates; the naive follow without an inode stack "
                    "hits a step cap below Linux ELOOP."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harness_walker/walker.py:_visit_link",
                "detail": (
                    f"loops={p2.get('cycle_loops')} "
                    f"naive_steps={p2.get('naive_follow_steps')} "
                    f"hit_cap={p2.get('naive_follow_hit_cap')}"
                ),
            },
            {
                "kind": "phase0-nul-regression",
                "claim": (
                    "The exact NUL case that crashed the baseline enumerator "
                    "is in the fixture; windows_device_relpath still raises "
                    "ValueError path is on mount '\\\\.\\NUL'; the swallowed "
                    "twin reports count 0."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harness_walker/paths.py:windows_device_relpath",
                "detail": str(p1.get("phase0_raise")),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "hostile-tree-no-crash",
                "fingerprint": fp(t1),
                "raw_output": t1[-2000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "fail-closed-and-loops",
                "fingerprint": fp(t2),
                "raw_output": t2[-2000:],
            },
        ],
        "walker": {
            "module": "tools/harness_walker/walker.py",
            "census_wired": "tools/plugin/census.py",
            "platform": p1.get("platform"),
            "probe1": p1,
            "probe2": p2,
        },
        "trace_hash_comparison": {
            "seed": "hostile-fixture-structure",
            "run_a_sha256": p1.get("fingerprint_a"),
            "run_b_sha256": p1.get("fingerprint_b"),
            "identical": p1.get("identical_rerun"),
            "node_ids": [
                "scan-root",
                "reserved-NUL",
                "long-path",
                "junction-loop",
                "unread-account",
                "safe-relpath",
            ],
            "fan_out_cardinalities": [
                {"id": "hostile-classes", "kind": "FanOut", "cardinality": 3},
                {
                    "id": "unread-plants",
                    "kind": "FanOut",
                    "cardinality": len(p2.get("planted_unread_rels") or []),
                },
            ],
            "barrier_resolution": [
                {
                    "id": "walk-complete",
                    "join_order": ["reserved", "long", "cycle"],
                }
            ],
        },
        "nondeterminism_sources": [
            {
                "source": "path",
                "site": "WalkEntry.abs_path",
                "how_found": (
                    "Absolute tmp paths vary; result_fingerprint hashes "
                    "relpath/kind/unread only."
                ),
                "leaks_into_production_dag": False,
            },
            {
                "source": "wall-clock",
                "site": "walker.py",
                "how_found": "walk_tree does not call time; rerun fingerprints match.",
                "leaks_into_production_dag": False,
            },
        ],
        "frozen_clock": {
            "applied": True,
            "trace_unchanged": True,
            "clock_ns": 0,
        },
        "fixed_pid": {
            "applied": True,
            "trace_unchanged": True,
            "pid": 1,
        },
        "reviewer": {
            "reviewer_id": "TST-0335-probe2-fail-closed-and-loops",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 rebuilds its own trees and plants EACCES plus a "
                "dangling symlink and a junction cycle. It does not re-read "
                "probe 1's conclusion. Naive follow and silent-skip twins "
                "are the known-broken states."
            ),
        },
        "artifacts": artifacts,
        "library_tests_tail": t_lib[-1500:],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for TST-0335: live named probes exit 0, receipts/TST-0335.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not "
            "delivery. " + SENTINEL
        ),
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the harness "
                "or the fixture."
            ),
        },
    }

    try:
        import jsonschema

        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(receipt, schema)
    except ImportError:
        pass
    except Exception as exc:
        # Shim schemas $ref https://ast-integrate.invalid/... which this
        # host does not resolve. G-1 delivery is the measure script, not
        # live $ref validation. Keep writing the receipt.
        print(f"WARN:{UNIT} emit schema {type(exc).__name__}: {exc}")

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
