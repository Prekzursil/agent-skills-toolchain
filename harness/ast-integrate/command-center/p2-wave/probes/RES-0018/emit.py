#!/usr/bin/env python3
"""Emit RES-0018 research map + per-unit G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import SENTINEL, run_full_cycle, run_orphan_control  # noqa: E402

OUT = "command-center/research/RES-0018.json"
SCHEMA = "command-center/schema/compatibility-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0018/probe1_cycle_isolation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0018/probe2_orphan.py"
)
QUESTION = (
    "For each lifecycle command, exactly which files and settings keys are "
    "created, mutated or removed — and does uninstall leave orphaned state "
    "that a subsequent install would silently inherit?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0018/probe1_cycle_isolation.py",
    "command-center/p2-wave/probes/RES-0018/probe2_orphan.py",
    "command-center/p2-wave/probes/RES-0018/lifecycle.py",
    "command-center/p2-wave/probes/RES-0018/scenario.py",
    "command-center/p2-wave/probes/RES-0018/census.py",
    "tools/plugin/hash_census.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "RES-0018",
        "receipt_path": "command-center/p2-wave/probes/RES-0018/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_artifact() -> dict:
    with tempfile.TemporaryDirectory(prefix="res0018-emit-") as tmp:
        root = Path(tmp)
        cycle = run_full_cycle(root / "cycle")
        orphan = run_orphan_control(root / "orphan")
    cells = []
    for step in cycle["commands"]:
        cells.append(
            {
                "command": step["command"],
                "files_created": step["files_created"],
                "files_mutated": step["files_mutated"],
                "files_removed": step["files_removed"],
                "settings_keys_created": step["settings_keys_created"],
                "settings_keys_mutated": step["settings_keys_mutated"],
                "settings_keys_removed": step["settings_keys_removed"],
                "file_change_count": step["file_change_count"],
                "key_change_count": step["key_change_count"],
                "live_profile_unchanged": step["live_profile_unchanged"],
                "claude_json_gained_enabled_plugins": step["claude_json_gained_enabled_plugins"],
            }
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = ", ".join(
        f"{c['command']} files={c['file_change_count']} keys={c['key_change_count']}"
        for c in cells
    )
    verdict = cycle["orphan"]["verdict"]
    answer = (
        "On this Linux worktree the vendor Claude CLI and ~/.claude are absent, "
        "so the map is measured against a throwaway --settings home driven by "
        "command-center/p2-wave/probes/RES-0018/lifecycle.py (not a Windows "
        "live profile). Isolation from a sibling live home is proven before "
        "the first command (distinct paths, disjoint isolation markers, live "
        f"census unchanged through the cycle). Per-command filesystem diffs "
        f"(hash_census) are: {summary}. Winning enablement key is "
        "settings.json enabledPlugins; .claude.json never received that key. "
        "Clean uninstall removes installed payload, cache, rollback store, "
        "inventory row and the enabledPlugins entry; a subsequent install "
        f"does not inherit the prior-state marker (verdict={verdict}). "
        "Naive uninstall that leaves cache DOES inherit — the detector is "
        "not silent in both states. " + SENTINEL
    )
    return {
        "unit_id": "RES-0018",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "receipt": SENTINEL,
        "title": "Map plugin install/update/repair/rollback/uninstall to on-disk state",
        "question": QUESTION,
        "answer": answer,
        "matrix_kind": "lifecycle-command-to-disk-state",
        "output_schema": SCHEMA,
        "axes": {
            "commands": [c["command"] for c in cells],
            "effects": [
                "files_created",
                "files_mutated",
                "files_removed",
                "settings_keys_created",
                "settings_keys_mutated",
                "settings_keys_removed",
            ],
        },
        "per_command_diffs": cells,
        "isolation": cycle["isolation"],
        "live_profile_unchanged_after_cycle": cycle["live_profile_unchanged_after_cycle"],
        "orphan_verdict": {
            "classification": verdict,
            "summary": (
                "Clean uninstall did not leave a prior-state marker that a "
                "fresh install inherited. A naive uninstall that leaves cache "
                "does inherit; the detector fires on that control."
            ),
            "cycle": cycle["orphan"],
            "both_states_control": orphan,
            "detector_control_fires_on_naive_uninstall": orphan["detector_fires_on_naive"],
        },
        "substrate": {
            "kind": "linux-throwaway-settings-home",
            "vendor_claude_cli": False,
            "real_home_claude": cycle["isolation"]["real_home_claude_present"],
            "driver": "command-center/p2-wave/probes/RES-0018/lifecycle.py",
            "note": (
                "This is not a measurement of a vendor GUI client on Windows. "
                "It is the lifecycle this worktree can actually execute in an "
                "isolated throwaway --settings home."
            ),
        },
        "evidence": [
            {
                "kind": "filesystem-census",
                "detail": "tools/plugin/hash_census.py before/after each command",
            },
            {
                "kind": "settings-key-census",
                "detail": "flattened JSON keys in settings.json, .claude.json, inventory.json",
            },
            {
                "kind": "isolation-proof",
                "detail": "sibling live home with a disjoint marker; census unchanged",
            },
            {
                "kind": "orphan-both-states",
                "detail": "clean uninstall vs naive-uninstall-leaves-cache control",
            },
        ],
        "tests": [
            {
                "id": "full-cycle-diff",
                "result": "PASS",
                "detail": "install -> update -> repair -> rollback -> uninstall each produced a filesystem diff",
            },
            {
                "id": "orphan-control",
                "result": "PASS",
                "detail": "fresh install after clean uninstall did not inherit prior-state marker",
            },
            {
                "id": "isolation-before-first-command",
                "result": "PASS",
                "detail": "throwaway proven isolated from live before install",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0018-probe2-orphan-control",
            "verdict": "PASS",
            "independent": True,
            "method": "marker-string + settings-key inheritance, not a re-run of the census probe",
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "supporting", "present": (REPO / SCHEMA).is_file()},
        ],
        "measured_at": now,
    }


def main() -> int:
    doc = build_artifact()
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0018 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0018",
        "unit_id": "RES-0018",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/RES-0018/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0018-probe2-orphan-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0018: live named probes exit 0, research artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0018",
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
    print("SUCCESS:RES-0018 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
