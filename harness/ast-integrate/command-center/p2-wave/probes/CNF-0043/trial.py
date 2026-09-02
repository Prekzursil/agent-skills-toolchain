#!/usr/bin/env python3
"""Live trials: kill at each phase then rollback; plus the hybrid control."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from hashes import compare, inventory
from health import coherence_health, file_count_health
from installer import kill_signature, upgrade
from rollback import restore
from scenario import N, N1, PHASES, seed_pre_upgrade


def _serial_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"path": r["path"], "sha256": r["sha256"], "bytes": r["bytes"]} for r in rows]


def run_kill_trial(phase: str) -> dict[str, Any]:
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase}")
    with tempfile.TemporaryDirectory(prefix=f"cnf0043-{phase}-") as tmp:
        root = Path(tmp) / "target"
        seed = seed_pre_upgrade(root)
        pre = inventory(root)
        killed = upgrade(root, kill_after=phase)
        sig = kill_signature(root, phase)
        at_kill = inventory(root)
        naive_at_kill = file_count_health(root)
        coherence_at_kill = coherence_health(root, expected_version=N1, user_sha256=seed["user_sha256"])
        rb = restore(root, seed["snapshot"])
        post = inventory(root)
        hashes = compare(pre, post)
        hc = coherence_health(root, expected_version=N1, user_sha256=seed["user_sha256"])
        naive_after = file_count_health(root)
        recovered = (
            sig["ok"]
            and rb["ok"]
            and hashes["identical"]
            and hc["ok"]
            and not hc["hybrid"]
        )
        return {
            "id": f"kill-after-{phase.replace('_', '-')}",
            "phase": phase,
            "kill_landed": sig["ok"],
            "kill_signature": sig,
            "installer": {
                "killed_after": killed["killed_after"],
                "completed_phases": killed["completed_phases"],
                "complete": killed["complete"],
                "versions_at_kill": killed["versions"],
            },
            "state_inventory_at_kill": _serial_inventory(at_kill),
            "naive_file_count_at_kill": {
                "ok": naive_at_kill["ok"],
                "kind": naive_at_kill["kind"],
                "plugin_files_present": naive_at_kill["plugin_files_present"],
            },
            "coherence_at_kill": {
                "ok": coherence_at_kill["ok"],
                "hybrid": coherence_at_kill["hybrid"],
                "files_version": coherence_at_kill["files_version"],
                "manifest_version": coherence_at_kill["manifest_version"],
                "cache_version": coherence_at_kill["cache_version"],
            },
            "rollback_transcript": {
                "ok": rb["ok"],
                "restored_paths": rb["restored_paths"],
                "removed_residue": rb["removed_residue"],
                "user_paths_preserved": rb["user_paths_preserved"],
                "step_ops": [s["op"] for s in rb["steps"]],
                "step_count": len(rb["steps"]),
            },
            "hash_comparison": hashes,
            "health_check": {
                "ok": hc["ok"],
                "kind": hc["kind"],
                "expected_version": hc["expected_version"],
                "hybrid": hc["hybrid"],
                "files_version": hc["files_version"],
                "manifest_version": hc["manifest_version"],
                "cache_version": hc["cache_version"],
                "probes": hc["probes"],
                "aggregate_refuses_blocked": True,
            },
            "naive_file_count_after_rollback": {
                "ok": naive_after["ok"],
                "kind": naive_after["kind"],
            },
            "recovered_to_pre_state": recovered,
        }


def run_all_kill_points() -> list[dict[str, Any]]:
    return [run_kill_trial(phase) for phase in PHASES]


def catalog_kill_points(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Read kill_points from a receipt: top-level (legacy) or report (schema)."""
    raw = doc.get("kill_points")
    if isinstance(raw, list) and raw:
        return raw
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    nested = report.get("kill_points")
    return nested if isinstance(nested, list) else []


def catalog_hybrid(doc: dict[str, Any]) -> dict[str, Any]:
    """Read hybrid_probe from a receipt: top-level (legacy) or report (schema)."""
    raw = doc.get("hybrid_probe")
    if isinstance(raw, dict) and raw:
        return raw
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    nested = report.get("hybrid_probe")
    return nested if isinstance(nested, dict) else {}


def run_hybrid_control() -> dict[str, Any]:
    """Leave a file_copy hybrid in place. File-count says healthy; coherence must not."""
    with tempfile.TemporaryDirectory(prefix="cnf0043-hybrid-") as tmp:
        root = Path(tmp) / "target"
        seed = seed_pre_upgrade(root)
        upgrade(root, kill_after="file_copy")
        sig = kill_signature(root, "file_copy")
        naive = file_count_health(root)
        real = coherence_health(root, expected_version=N, user_sha256=seed["user_sha256"])
        real_vs_pre = coherence_health(root, expected_version=N1, user_sha256=seed["user_sha256"])
        discriminated = naive["ok"] is True and real["ok"] is False and real["hybrid"] is True
        return {
            "constructed": True,
            "kill_window": "file_copy",
            "kill_landed": sig["ok"],
            "observed": sig["observed"],
            "naive_file_count": {
                "ok": naive["ok"],
                "kind": naive["kind"],
                "plugin_files_present": naive["plugin_files_present"],
            },
            "coherence_against_n": {
                "ok": real["ok"],
                "hybrid": real["hybrid"],
                "kind": real["kind"],
                "files_version": real["files_version"],
                "manifest_version": real["manifest_version"],
                "cache_version": real["cache_version"],
            },
            "coherence_against_n1": {
                "ok": real_vs_pre["ok"],
                "hybrid": real_vs_pre["hybrid"],
            },
            "false_healthy_under_file_count": naive["ok"] is True,
            "coherence_rejects_hybrid": real["ok"] is False and real["hybrid"] is True,
            "discriminated": discriminated,
            "note": (
                "A hybrid of N files + N-1 manifest + N-1 cache still has three "
                "plugin files, so file-count reports healthy. Coherence must fail. "
                "That false-healthy is the worst outcome this unit probes for."
            ),
        }
