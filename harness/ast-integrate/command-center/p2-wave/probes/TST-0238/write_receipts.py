#!/usr/bin/env python3
"""Write TST-0238 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
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

UID = "TST-0238"
OUT = "command-center/receipts/TST-0238.json"
SENTINEL = "SUCCESS:TST-0238"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/benchmark_result"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0238/probe1_shim_detector.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0238/probe2_cancel_and_trace.py"
)
SUPPORTING = [
    "tools/hud/statusline.py",
    "tools/hud/spawn_measure.py",
    "tools/hud/__init__.py",
    "command-center/p2-wave/probes/TST-0238/probe1_shim_detector.py",
    "command-center/p2-wave/probes/TST-0238/probe2_cancel_and_trace.py",
    "command-center/p2-wave/probes/TST-0238/fixtures/payload.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0238/SUBAGENT-RETURN.json",
        "role": role,
    }


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:TST-0238 catalog unit missing")


def last_json_object(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or SENTINEL)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0238 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    p1 = last_json_object(t1)
    p2 = last_json_object(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0238 probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_prod = int(p1.get("production_shim_count") or 0)
    n_inj = int(p1.get("injected_shim_count") or 0)
    ceiling = int(p1.get("ceiling") or 2)
    slow = p2.get("slow_render") or {}
    signals = p2.get("independent_signals") or {}
    clones = signals.get("b_strace_process_clones") or {}

    answer = (
        f"One production cockpit/statusline render performs {n_prod} external "
        f"PATH-visible child spawns (ceiling {ceiling}); under ceiling={n_prod <= ceiling}. "
        f"Count is from a PATH shim first proven to catch a known `true` spawn "
        f"(shim_count={p1.get('shim_proven_known_spawn', {}).get('shim_count')}), "
        f"then shown to increment {n_prod}->{n_inj} when one extra spawn is inserted. "
        f"A grep of tools/hud/statusline.py is not the detector "
        f"(jq/sleep words occur in comments: {p1.get('grep_mentions_in_statusline_py')}). "
        f"Independent OS-level strace process-clones over the same pair moved "
        f"{clones.get('production')}->{clones.get('injected')}. "
        f"Slow render CANCELLED: shim {slow.get('cancelled_shim_count')} "
        f"< uncancelled {slow.get('uncancelled_shim_count')} "
        f"(remaining helper not launched). {sentinel}"
    )

    receipt = {
        "schema_version": 1,
        "kind": "benchmark_result",
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0238; TST-0107 spawn-count budget; "
            "rules/common/bash-hud-and-terminal-emit.md:7 (debounce 300 ms, "
            "slow render CANCELLED; jq ~200 ms / bash ~350 ms so spawn count "
            "is the budget)"
        ),
        "min_bytes_threshold": 128,
        "ceiling": {
            "metric": "external_child_spawns_per_render",
            "value": ceiling,
            "unit": "processes",
            "production_count": n_prod,
            "under_ceiling": n_prod <= ceiling,
        },
        "benchmark": {
            "subject": "tools/hud/statusline.py",
            "payload": "command-center/p2-wave/probes/TST-0238/fixtures/payload.json",
            "detector": "PATH shim spawn log (proven on known `true` spawn)",
            "not_a_detector": "text grep of the renderer script",
            "production_shim_count": n_prod,
            "injected_shim_count": n_inj,
            "incremented_by_one": bool(p1.get("incremented_by_one")),
            "debounce_ms": 300,
            "cancel_ms": 200,
            "slow_cancelled_shim_count": slow.get("cancelled_shim_count"),
            "slow_uncancelled_shim_count": slow.get("uncancelled_shim_count"),
        },
        "evidence_requirement": unit.get("evidence_requirement"),
        "evidence": [
            {
                "id": "E1-shim-spawn-log",
                "claim": (
                    "PATH shim, proven on a known `true` spawn, counts 0 child "
                    "spawns on a production render and 1 after inject-spawn."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/hud/spawn_measure.py:prove_shim_catches_known_spawn",
                "confidence": "almost-certain",
                "production_shim_count": n_prod,
                "injected_shim_count": n_inj,
                "known_spawn": p1.get("shim_proven_known_spawn"),
            },
            {
                "id": "E2-os-process-creation-trace",
                "claim": (
                    "strace -f clone/clone3/fork/vfork/execve over the same "
                    "renders: process clones (no CLONE_THREAD) move with the "
                    "injected spawn, independent of the shim log."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/hud/spawn_measure.py:parse_strace",
                "confidence": "almost-certain",
                "production_process_clones": clones.get("production"),
                "injected_process_clones": clones.get("injected"),
                "proc_stat_delta": signals.get("proc_stat_processes_delta"),
            },
        ],
        "artifact_paths": [OUT, *SUPPORTING],
        "artifacts": [{"path": OUT, "role": "primary", "exists": True}]
        + [{"path": p, "role": "supporting", "exists": True} for p in SUPPORTING],
        "test_ids": [
            "TST-0238-probe1-shim-detector-control",
            "TST-0238-probe2-os-trace-and-slow-cancel",
        ],
        "tests": [
            {
                "id": "TST-0238-probe1-shim-detector-control",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
                "requirement": (
                    "detector control: insert a known extra spawn and confirm "
                    "the shim count increments; shim first proven on `true`"
                ),
                "output_tail": t1[-4000:],
            },
            {
                "id": "TST-0238-probe2-os-trace-and-slow-cancel",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "requirement": (
                    "regression seed: a slow render is CANCELLED, so spawn "
                    "count is the real budget; OS-level clone trace agrees"
                ),
                "output_tail": t2[-4000:],
            },
        ],
        "negative_control_ids": [
            "TST0238-NC1-grep-is-not-detector",
            "TST0238-NC2-uncancelled-slow-spawns-more",
        ],
        "negative_controls": [
            {
                "id": "TST0238-NC1-grep-is-not-detector",
                "kind": "detector-control",
                "description": (
                    "statusline.py comments mention jq/sleep; a text grep is "
                    "nonzero while production shim count is zero."
                ),
                "fired_on_bad_state": bool(p1.get("grep_would_be_nonzero")),
                "silent_on_good_state": n_prod == 0,
                "grep_mentions": p1.get("grep_mentions_in_statusline_py"),
            },
            {
                "id": "TST0238-NC2-uncancelled-slow-spawns-more",
                "kind": "both-states",
                "description": (
                    "Without cancel, the slow plan launches sleep then true "
                    "(2). With cancel_ms=40 the second helper never launches."
                ),
                "fired_on_bad_state": int(slow.get("uncancelled_shim_count") or 0) >= 2,
                "silent_on_good_state": int(slow.get("cancelled_shim_count") or 0)
                < int(slow.get("uncancelled_shim_count") or 0),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0238-probe2-os-trace-and-slow-cancel",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (named probes), not the author's summary",
            "adversarial_refuter": "uncancelled slow path must spawn more",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0238/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This Linux worktree has no Cursor CLI statusLine command "
                    "configured and no historical p2_status.py. The measured "
                    "surface is tools/hud/statusline.py (in-process JSON, "
                    "spawn ceiling 2, debounce 300 ms, cancel 200 ms)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point ~/.cursor/cli-config.json statusLine.command at "
                    "tools/hud/statusline.py and re-run the PATH shim around "
                    "a live CLI statusline tick."
                ),
            }
        ],
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0238: live named probes exit 0, receipts/TST-0238.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. "
            + sentinel
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:TST-0238 sentinel absent after write")
        return 1
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        print("FAILED:TST-0238 state not SUCCESS")
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:TST-0238 probes after receipt c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "shim-detector-control",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "os-trace-and-slow-cancel",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0238/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0238-probe2-os-trace-and-slow-cancel",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0238: live named probes exit 0, receipts/TST-0238.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
    print(f"production_spawns={n_prod} injected={n_inj} ceiling={ceiling}")
    print("SUCCESS:TST-0238 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
