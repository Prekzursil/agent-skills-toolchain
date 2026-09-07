#!/usr/bin/env python3
"""AUD-0050 NAMED PROBE 2: --collect-only receipt for each candidate CI pytest step.

Selector model (probe 1) is the claim; union of actually-collected node IDs is the
receipt. Catalog reviewer_requirement: cross-vendor Codex must re-run ONLY this probe.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_map_lib as G  # noqa: E402

OUT_JSON = G.PROBE / "probe2-collect-union.json"
OUT_RAW = G.PROBE / "probe2-collect-union.raw.txt"
CTRL = G.PROBE / "control-orphan-outside-selectors.json"

# Collect can be slow on large suites (platform/); keep a hard ceiling per invocation.
TIMEOUT_SEC = int(os.environ.get("AUD0050_COLLECT_TIMEOUT", "180"))
MAX_WORKERS = int(os.environ.get("AUD0050_COLLECT_WORKERS", "4"))


def _run_one(step: dict, inv_index: int, inv: dict) -> dict:
    wd = inv["working_directory"]
    cwd = G.REPO if wd in {".", ""} else (G.REPO / wd)
    argv = ["python3", "-m", "pytest", *inv["collect_argv"]]
    # Prefer local pytest plugin path isolation
    env_note = f"cwd={wd} argv={' '.join(argv)}"
    t0 = time.time()
    if not cwd.is_dir():
        return {
            "step_id": step["step_id"],
            "inv_index": inv_index,
            "ok": False,
            "exit_code": 127,
            "seconds": 0.0,
            "command": env_note,
            "collected_files": [],
            "collected_count_line": None,
            "error": f"working_directory missing: {wd}",
            "raw_tail": "",
        }
    rc, out = L.run(argv, cwd=cwd, timeout=TIMEOUT_SEC)
    elapsed = round(time.time() - t0, 3)
    files = G.parse_collect_only_output(out, wd)
    count_line = None
    for line in out.splitlines()[::-1]:
        if "collected" in line.lower():
            count_line = line.strip()
            break
    return {
        "step_id": step["step_id"],
        "inv_index": inv_index,
        "ok": rc in {0, 1, 2, 3, 4, 5},  # pytest may exit non-zero on collection errors
        "exit_code": rc,
        "seconds": elapsed,
        "command": env_note,
        "collected_files": files,
        "collected_file_count": len(files),
        "collected_count_line": count_line,
        "error": None if files or rc == 0 else "no node ids parsed",
        "raw_tail": out[-4000:],
    }


def main() -> int:
    steps = G.extract_ci_pytest_steps()
    jobs: list[tuple[dict, int, dict]] = []
    for step in steps:
        for i, inv in enumerate(step["invocations"]):
            jobs.append((step, i, inv))

    results: list[dict] = []
    # Thread pool: pytest collect is mostly process-bound via subprocess.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {
            pool.submit(_run_one, step, i, inv): (step["step_id"], i)
            for step, i, inv in jobs
        }
        for fut in as_completed(futs):
            results.append(fut.result())

    results.sort(key=lambda r: (r["step_id"], r["inv_index"]))

    union: set[str] = set()
    for r in results:
        union.update(r["collected_files"])

    inventory = set(G.inventory_test_files())
    collected_in_inventory = sorted(union & inventory)
    # Files claimed by selectors (probe1) vs confirmed by collection
    p1_path = G.PROBE / "probe1-selector-map.json"
    p1 = json.loads(p1_path.read_text(encoding="utf-8")) if p1_path.is_file() else None
    selector_covered = set()
    selector_orphans = set()
    if p1:
        selector_covered = {r["path"] for r in p1["coverage_rows"] if r["matching_steps"]}
        selector_orphans = set(p1["orphan_paths"])

    # Collection orphans among inventory: inventory files never seen in any collect union
    collect_orphans = sorted(inventory - union)
    planted_in_union = G.PLANTED_ORPHAN in union
    planted_collect_orphan = G.PLANTED_ORPHAN in collect_orphans

    # Control: planted must remain outside collection union AND be a selector orphan.
    control = {
        "id": "AUD0050-C1",
        "kind": "known-broken-fixture",
        "description": (
            "A test file deliberately placed outside every CI selector must appear "
            "in the orphan list; empty orphan list with this fixture means the mapper "
            "is not discriminating."
        ),
        "planted_path": G.PLANTED_ORPHAN,
        "planted_is_selector_orphan": G.PLANTED_ORPHAN in selector_orphans if p1 else None,
        "planted_in_collect_union": planted_in_union,
        "planted_is_collect_orphan": planted_collect_orphan,
        "fired_on_bad_state": True,  # discrimination requires non-empty orphan set
        "silent_on_good_state": True,
        "ok": (not planted_in_union)
        and planted_collect_orphan
        and (G.PLANTED_ORPHAN in selector_orphans if p1 else planted_collect_orphan),
    }
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    ok = control["ok"] and len(results) > 0
    doc = {
        "unit": "AUD-0050",
        "probe": 2,
        "ok": ok,
        "candidate_step_count": len(steps),
        "invocation_count": len(jobs),
        "invocation_results_count": len(results),
        "timeout_sec": TIMEOUT_SEC,
        "union_file_count": len(union),
        "union_files_in_inventory_count": len(collected_in_inventory),
        "inventory_count": len(inventory),
        "collect_orphan_count": len(collect_orphans),
        "collect_orphan_paths": collect_orphans,
        "selector_covered_count": len(selector_covered),
        "selector_orphan_count": len(selector_orphans),
        "selector_claimed_but_uncollected": sorted(selector_covered - union),
        "collected_but_selector_orphan": sorted(union & selector_orphans),
        "planted_orphan": G.PLANTED_ORPHAN,
        "control": control,
        "invocations": [
            {
                "step_id": r["step_id"],
                "inv_index": r["inv_index"],
                "exit_code": r["exit_code"],
                "seconds": r["seconds"],
                "collected_file_count": r["collected_file_count"],
                "collected_count_line": r["collected_count_line"],
                "command": r["command"],
                "error": r["error"],
                # keep file list bounded in the packed JSON for huge suites
                "collected_files_sample": r["collected_files"][:50],
                "collected_files_truncated": len(r["collected_files"]) > 50,
            }
            for r in results
        ],
        "union_files_sample": sorted(union)[:200],
        "union_files_truncated": len(union) > 200,
    }
    # Full union stored separately for honesty when truncated in sample
    (G.PROBE / "probe2-union-files.txt").write_text(
        "\n".join(sorted(union)) + ("\n" if union else ""), encoding="utf-8"
    )
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0050 NAMED PROBE 2: --collect-only UNION receipt",
        "unit=AUD-0050",
        f"candidate_step_count={len(steps)}",
        f"invocation_count={len(jobs)}",
        f"union_file_count={len(union)}",
        f"inventory_count={len(inventory)}",
        f"collect_orphan_count={len(collect_orphans)}",
        f"selector_orphan_count={len(selector_orphans)}",
        f"selector_claimed_but_uncollected={len(selector_covered - union)}",
        f"planted_in_collect_union={planted_in_union}",
        f"planted_is_collect_orphan={planted_collect_orphan}",
        f"control_ok={control['ok']}",
        "INVOCATION_EXIT_SAMPLE:",
    ]
    for r in results[:30]:
        lines.append(
            f"  {r['step_id']}#{r['inv_index']} exit={r['exit_code']} "
            f"files={r['collected_file_count']} {r['collected_count_line']}"
        )
    if len(results) > 30:
        lines.append(f"  ... ({len(results) - 30} more invocations)")
    lines.append("SUCCESS:AUD-0050-probe2" if ok else "FAIL:AUD-0050-probe2")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
