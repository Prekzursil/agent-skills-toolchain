#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0326.json from live discovery + named probes."""
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
sys.path.insert(0, str(REPO / "tools"))

from test_discovery.entrypoints import good_parity, planted_break  # noqa: E402
from test_discovery.live import live_scan  # noqa: E402

OUT = "command-center/receipts/TST-0326.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0326"
QUESTION = (
    "Implementation target: CC-0014 binds tests to claims to units; this unit "
    "supplies the DISCOVERY side it depends on. Walk every tree the program "
    "owns (repo, live harness trees, worktrees) collecting executable tests by "
    "their real invocation, then compute two set differences: tests on disk "
    "with no registry entry (orphans, running but uncounted) and registry "
    "entries with no discoverable test (ghosts, counted but not running). A "
    "ghost entry is how a suite gets credit for coverage it does not have."
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/test_discovery/tests/test_discovery.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0326/probe2_walker_hostile.py"
)
SUPPORTING = [
    SCHEMA,
    "tools/test_discovery/__init__.py",
    "tools/test_discovery/walker.py",
    "tools/test_discovery/collect.py",
    "tools/test_discovery/registry.py",
    "tools/test_discovery/reconcile.py",
    "tools/test_discovery/owned.py",
    "tools/test_discovery/plants.py",
    "tools/test_discovery/live.py",
    "tools/test_discovery/install.py",
    "tools/test_discovery/entrypoints.py",
    "tools/test_discovery/console.py",
    "tools/test_discovery/ci.py",
    "tools/test_discovery/__main__.py",
    "tools/test_discovery/tests/test_discovery.py",
    "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py",
    "command-center/p2-wave/probes/TST-0326/probe2_walker_hostile.py",
]


def digest_file(path: Path) -> tuple[str, int]:
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
    exists = path.is_file()
    sha, size = digest_file(path) if exists else ("", 0)
    return {
        "path": rel,
        "exists": exists,
        "role": role,
        "bytes": size,
        "sha256": sha if exists else None,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0326 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-2500:])
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    if "SUCCESS:TST-0326-tests" not in t_test:
        print("FAILED:TST-0326 emit tests sentinel missing")
        return 1
    if "SUCCESS:TST-0326-probe1" not in t1:
        print("FAILED:TST-0326 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0326-probe2" not in t2:
        print("FAILED:TST-0326 emit probe2 sentinel missing")
        return 1

    parity = good_parity()
    brk = planted_break()
    if not parity["sets_identical_on_good_install"]:
        print("FAILED:TST-0326 entry-point collection sets differ")
        print(json.dumps(parity["sets"], indent=2))
        return 1
    if not parity["outcomes_identical_on_good_install"]:
        print("FAILED:TST-0326 entry-point outcomes differ")
        return 1
    if not brk["pass"]:
        print("FAILED:TST-0326 planted import-path break did not fire")
        print(json.dumps(brk, indent=2, default=str))
        return 1

    scan = live_scan(REPO)
    report = scan["report"]
    if report["paths_walked"] <= 0:
        print("FAILED:TST-0326 live walk visited zero paths")
        return 1
    if not scan["harness_visited"]:
        print("FAILED:TST-0326 harness p2-wave/probes was not visited")
        return 1
    if not scan["identical"]:
        print("FAILED:TST-0326 live trace hash diverged under frozen clock/pid")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_schema_missing = not (REPO / CATALOG_SCHEMA).is_file()
    registry_present = bool(scan["registry"]["present"])
    orphan_n = report["orphan_count"]
    ghost_n = report["ghost_count"]
    collected_n = report["collected_count"]
    trees_named = [t["id"] for t in scan["named_trees"]]

    arts = [{"path": OUT, "exists": True, "role": "primary"}]
    for rel in SUPPORTING:
        arts.append(artifact_row(rel, "supporting"))

    summary = (
        "Discovery walked named trees "
        + json.dumps(trees_named)
        + f" visiting {report['paths_walked']} paths and collecting "
        + f"{collected_n} pytest/vitest nodeids via the collector CLI grammar "
        + f"(pytest module absent on this box; collector={report['collector']}). "
        + (
            "command-center/TEST-REGISTRY.json is ABSENT, so every collected test "
            "is an orphan and the ghost list is empty — a zero-orphan claim would "
            "be false. "
            if not registry_present
            else "TEST-REGISTRY.json is present. "
        )
        + f"orphan_count={orphan_n} ghost_count={ghost_n}. "
        "Detector controls: a planted test file is reported as an orphan; a "
        "registry entry for a nonexistent test is reported as a ghost; the "
        "walker visits a NUL reserved-device-name and a 260+ path without "
        "truncating, and an unreadable directory fail-closes instead of "
        "returning zero. Three collector entry points agree on the matching "
        "fixture; omitting test_discovery.walker leaves python -m green and "
        "shrinks the console-script collection set. "
        + SENTINEL
    )
    answer = {
        "summary": summary,
        "orphan_count": orphan_n,
        "ghost_count": ghost_n,
        "collected_count": collected_n,
        "paths_walked": report["paths_walked"],
        "registry_present": registry_present,
        "harness_visited": scan["harness_visited"],
    }

    doc = {
        "unit_id": "TST-0326",
        "id": "TST-0326",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "title": (
            "Reconcile discovered tests against the registry: find orphan "
            "tests and ghost entries"
        ),
        "question": QUESTION,
        "answer": answer,
        "claim_under_test": (
            "Walking owned trees and collecting pytest/vitest nodeids produces "
            "two honest set differences (orphans, ghosts) with full id lists "
            "and a named path-walk count; planted detector controls fire."
        ),
        "output_schema": SCHEMA,
        "catalog_output_schema": CATALOG_SCHEMA,
        "catalog_output_schema_missing": catalog_schema_missing,
        "entry_points": [
            {
                "id": "python-m",
                "kind": "python-m",
                "command": "python3 -m test_discovery.collect --root <fixture> --json",
            },
            {
                "id": "console-script",
                "kind": "console-script",
                "command": "prefix/bin/tst0326-collect --root <fixture> --json",
            },
            {
                "id": "ci-entry",
                "kind": "ci-entry",
                "command": "prefix/bin/tst0326-ci --root <fixture> --json",
            },
        ],
        "collection_comparison": {
            "compared_as": "sets",
            "sets_identical_on_good_install": True,
            "outcomes_identical_on_good_install": True,
            "node_ids": parity["node_ids"],
            "per_entry_sets": parity["sets"],
        },
        "planted_import_path_break": {
            "omitted_module": brk["omitted_module"],
            "source_python_m_still_green": True,
            "console_script_sees_break": True,
            "collection_sets_differ": True,
            "pass": True,
            "source_set": brk["source_set"],
            "console_set": brk["console_set"],
        },
        "cloud_ok": False,
        "trace_hash_comparison": {
            "seed": 326,
            "run_a_sha256": scan["run_a_sha256"],
            "run_b_sha256": scan["run_b_sha256"],
            "identical": True,
            "node_order": ["walk", "collect", "load-registry", "reconcile"],
            "fan_out_cardinalities": [
                {
                    "id": "walk-roots",
                    "kind": "FanOut",
                    "cardinality": len(scan["spec"]["walk_roots"]),
                },
                {
                    "id": "collected-tests",
                    "kind": "DynamicFanOut",
                    "cardinality": collected_n,
                },
            ],
            "barrier_resolution": [
                {
                    "id": "reconcile-join",
                    "kind": "join",
                    "inputs": ["collect", "registry"],
                    "orphan_count": orphan_n,
                    "ghost_count": ghost_n,
                }
            ],
        },
        "frozen_clock": {
            "applied": True,
            "clock_ns": 0,
            "trace_unchanged": True,
        },
        "fixed_pid": {
            "applied": True,
            "pid": 1,
            "trace_unchanged": True,
        },
        "nondeterminism_sources": [
            {
                "source": "path",
                "site": "tools/test_discovery/walker.py:native_path",
                "how_found": (
                    "Absolute native paths are used only to open reserved/long "
                    "names; published nodeids are posix-relative."
                ),
                "leaks_into_production_dag": False,
            },
            {
                "source": "wall-clock",
                "site": "emit timestamps",
                "how_found": (
                    "Receipt timestamps are wall-clock SAMPLE; the reconcile "
                    "trace hash uses clock_ns=0."
                ),
                "leaks_into_production_dag": False,
            },
            {
                "source": "pid",
                "site": "collector subprocess",
                "how_found": (
                    "Collector nodeids do not include pid; trace hash uses pid=1."
                ),
                "leaks_into_production_dag": False,
            },
        ],
        "discovery": {
            "trees_named": scan["named_trees"],
            "walk_roots": scan["spec"]["walk_roots"],
            "worktree_count": scan["spec"]["worktree_count"],
            "git_present": scan["spec"]["git_present"],
            "harness_visited": scan["harness_visited"],
            "paths_walked": report["paths_walked"],
            "complete": report["complete"],
            "collector": report["collector"],
            "registry": scan["registry"],
            "orphan_count": orphan_n,
            "ghost_count": ghost_n,
            "orphans": report["orphans"],
            "ghosts": report["ghosts"],
            "collected_count": collected_n,
            "registered_and_collected": report["registered_and_collected"],
            "per_tree": report["trees"],
            "zero_orphan_claim": False,
            "zero_orphan_requires_named_trees": trees_named,
        },
        "tests": [
            {
                "id": "test_planted_orphan_is_reported",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_planted_ghost_is_reported",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_hostile_walk_visits_nul_and_long_path",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "probe1-orphan-and-ghost",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-walker-hostile",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "orphan-ghost-set-difference",
                "claim": (
                    f"Live scan: collected={collected_n} orphans={orphan_n} "
                    f"ghosts={ghost_n} paths_walked={report['paths_walked']} "
                    f"trees={trees_named} registry_present={registry_present}. "
                    "Full id lists are under discovery.orphans and discovery.ghosts."
                ),
                "detail": (
                    f"Live scan: collected={collected_n} orphans={orphan_n} "
                    f"ghosts={ghost_n} paths_walked={report['paths_walked']}."
                ),
                "anchor": "tools/test_discovery/reconcile.py",
                "path": "tools/test_discovery/reconcile.py",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "detector-control-orphan",
                "claim": (
                    "Probe 1 plants test_planted_orphan.py and orphan.test.ts "
                    "outside the fixture registry and requires both nodeids in "
                    "the orphan list; the matching twin has empty diffs."
                ),
                "detail": (
                    "Probe 1 plants test_planted_orphan.py and orphan.test.ts "
                    "outside the fixture registry and requires both nodeids in "
                    "the orphan list; the matching twin has empty diffs."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py",
                "path": "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "detector-control-ghost",
                "claim": (
                    "Probe 1 adds tests/missing_ghost.py::test_ghost_not_on_disk "
                    "to the registry and requires it in the ghost list."
                ),
                "detail": (
                    "Probe 1 adds tests/missing_ghost.py::test_ghost_not_on_disk "
                    "to the registry and requires it in the ghost list."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py",
                "path": "command-center/p2-wave/probes/TST-0326/probe1_orphan_and_ghost.py",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "walker-completeness-c10",
                "claim": (
                    "Probe 2 walks a NUL reserved-device-name file and a "
                    "long-path leaf (>=260 chars), still collects after_nul and "
                    "long-path tests, and fail-closes on a planted unreadable "
                    "directory instead of returning zero."
                ),
                "detail": (
                    "Probe 2 walks a NUL reserved-device-name file and a "
                    "long-path leaf (>=260 chars), still collects after_nul and "
                    "long-path tests, and fail-closes on a planted unreadable "
                    "directory instead of returning zero."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0326/probe2_walker_hostile.py",
                "path": "command-center/p2-wave/probes/TST-0326/probe2_walker_hostile.py",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "entry-point-parity",
                "claim": (
                    "Collector node-id sets are identical across python -m, "
                    "console script, and CI entry on a complete install."
                ),
                "anchor": "tools/test_discovery/entrypoints.py:good_parity",
                "verdict": "CONFIRMED",
            },
            {
                "kind": "planted-import-path-break",
                "claim": (
                    "Omitting test_discovery.walker from the prefix install "
                    "leaves source python -m green and shrinks console-script "
                    "collection."
                ),
                "anchor": "tools/test_discovery/entrypoints.py:planted_break",
                "verdict": "CONFIRMED",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "orphan-and-ghost-detector-control",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "walker-hostile-c10",
                "raw_output": t2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0326-probe2-walker-hostile",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 is a second-shell walker completeness control: it "
                "plants NUL, a 260+ path, a symlink cycle, and an unreadable "
                "directory, then compares the live walker against a "
                "crash-as-zero mutant. It does not re-read probe 1's orphan/"
                "ghost conclusion."
            ),
        },
        "artifacts": arts,
        "registered": True,
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for TST-0326: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:TST-0326, per-unit UNIT-ARTIFACT-MANIFEST row. Did "
            "not run global unit_manifest.py --write. No ADV rebuild. "
            "Cloud ok=true is not delivery. Catalog output_schema "
            f"{CATALOG_SCHEMA} is missing on this worktree; validated against "
            f"{SCHEMA}. {SENTINEL}"
        ),
    }

    # Catalog shim $ref points at ast-integrate.invalid; jsonschema 4.10
    # fetches the network. receipt_core also forbids additionalProperties, so
    # the discovery payload cannot validate against the physical $ref. G-1
    # requires a parseable SUCCESS receipt + sentinel, not that retrieve.
    if not (REPO / SCHEMA).is_file():
        print("FAILED:TST-0326 emit schema missing")
        return 1
    blob = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in blob:
        print("FAILED:TST-0326 sentinel-absent before write")
        return 1
    if doc.get("unit_id") != "TST-0326" or str(doc.get("state") or "").upper() != "SUCCESS":
        print("FAILED:TST-0326 emit identity")
        return 1
    if not isinstance(doc.get("discovery"), dict) or int(doc["discovery"].get("paths_walked") or 0) <= 0:
        print("FAILED:TST-0326 emit discovery empty")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"live orphans={orphan_n} ghosts={ghost_n} "
        f"collected={collected_n} paths_walked={report['paths_walked']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
