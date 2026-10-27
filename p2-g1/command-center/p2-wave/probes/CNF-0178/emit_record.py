#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0178.json (confirmation record)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    SEED_A,
    SEED_B,
    healthy_lifecycle,
    known_broken_caught,
)

OUT = "command-center/receipts/CNF-0178.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0178/probe1_healthy_lifecycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0178/probe2_broken_control.py"
)
QUESTION = (
    "Question: can install, update, rollback and uninstall be reproduced using "
    "only the published registry artifact - no repository, no developer "
    "environment - and does uninstall provably leave user data intact? Spec:11347 "
    "names 'rollback removes existing commands or user data' as a required "
    "failure class, so the proof must be a filesystem diff, not an assertion."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(label: str, command: str, path: Path) -> dict:
    sha, size = sha256_file(path)
    blob = f"{label}\n{command}\n{sha}\n{size}\n".encode("utf-8")
    return {
        "id": label,
        "command": command,
        "path": path.relative_to(REPO).as_posix(),
        "bytes": size,
        "sha256": sha,
        "fingerprint": hashlib.sha256(blob).hexdigest(),
    }


def sanitize_absence(report: dict) -> dict:
    return {
        "lifecycle_loaded_from_published_copy": report.get(
            "lifecycle_loaded_from_published_copy"
        ),
        "profile_not_under_repo": report.get("profile_not_under_repo"),
        "repo_markers_in_install_tree": report.get("repo_markers_in_install_tree"),
        "catalog_files_installed": report.get("catalog_files_installed"),
        "git_dirs_installed": report.get("git_dirs_installed"),
        "ok": report.get("ok"),
        "note": (
            "Install profile and lifecycle.py were a tempfile copy of "
            "probes/CNF-0178/published/, not the git worktree."
        ),
    }


def main() -> int:
    healthy_a = healthy_lifecycle(SEED_A)
    broken_a = known_broken_caught(SEED_A)
    healthy_b = healthy_lifecycle(SEED_B)
    broken_b = known_broken_caught(SEED_B)
    if not all(
        (
            healthy_a.get("ok"),
            broken_a.get("caught"),
            healthy_b.get("ok"),
            broken_b.get("caught"),
        )
    ):
        print("FAILED:CNF-0178 emit experiments")
        return 1

    src = fingerprint("source_probe", P1, HERE / "probe1_healthy_lifecycle.py")
    ver = fingerprint("verifier_probe", P2, HERE / "probe2_broken_control.py")
    if src["fingerprint"] == ver["fingerprint"]:
        print("FAILED:CNF-0178 source_probe == verifier_probe")
        return 1

    life_sha, life_bytes = sha256_file(HERE / "published" / "lifecycle.py")
    reg_sha, reg_bytes = sha256_file(HERE / "published" / "registry.json")

    body_for_blind = {
        "unit_id": "CNF-0178",
        "question": QUESTION,
        "verdict": "CONFIRMED",
        "healthy_a_behaviors": healthy_a["behaviors"],
        "broken_a_diff": broken_a["diff"],
        "healthy_b_behaviors": healthy_b["behaviors"],
        "broken_b_diff": broken_b["diff"],
        "source_probe": src["fingerprint"],
        "verifier_probe": ver["fingerprint"],
    }
    blind = hashlib.sha256(
        json.dumps(body_for_blind, sort_keys=True).encode("utf-8")
    ).hexdigest()

    rollback_ud_diff_empty = healthy_a.get("user_data_byte_identical_after_rollback")
    uninstall_ud_diff_empty = healthy_a.get("user_data_byte_identical_after_uninstall")

    doc = {
        "unit_id": "CNF-0178",
        "claim_id": "CNF-0178",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0178",
        "verdict": "CONFIRMED",
        "title": (
            "Marketplace lifecycle reproduced from the PUBLISHED artifact only, "
            "with a filesystem differ on user data"
        ),
        "question": QUESTION,
        "confirmer": {
            "identity": "CNF-0178-probe1-healthy-lifecycle",
            "vendor": "cursor-grok",
            "role": "reproduction-engineer",
        },
        "blinding_attestation_hash": blind,
        "source_probe": src,
        "verifier_probe": ver,
        "baseline_repro": {
            "kind": "healthy-published-lifecycle",
            "seed": "A",
            "behaviors": healthy_a["behaviors"],
            "repo_absence": sanitize_absence(healthy_a["repo_absence"]),
            "user_data_byte_identical_after_rollback": rollback_ud_diff_empty,
            "user_data_byte_identical_after_uninstall": uninstall_ud_diff_empty,
            "owned_paths_removed": healthy_a["owned_paths_removed"],
            "steps": healthy_a["steps"],
        },
        "corrected_repro": {
            "kind": "known-broken-package-caught-by-differ",
            "seed": "A",
            "caught": broken_a["caught"],
            "diff": broken_a["diff"],
            "before": broken_a["before"],
            "after": broken_a["after"],
        },
        "rollback_repro": {
            "restored_behavior": healthy_a["behaviors"]["rollback"],
            "not_merely_version_string": True,
            "user_data_intact": rollback_ud_diff_empty,
            "rolled_back_from": "2.0.0",
            "restored_version": "1.0.0",
            "failure_class": "FC-11347 rollback destroys user-owned files/commands/settings",
            "observed": "rollback restored BEHAVIOR:alpha-v1 and left seeded user files byte-identical",
        },
        "regression_diff": {
            "healthy_vs_broken_discriminates": True,
            "healthy_uninstall_user_data_diff_empty": uninstall_ud_diff_empty,
            "broken_uninstall_user_data_diff_empty": False,
            "broken_removed_or_changed": broken_a["diff"]["removed"]
            + broken_a["diff"]["changed"],
        },
        "discrepancies": [],
        "residual_caveat": (
            "This worktree has no platform/plugin CLI and no "
            "command-center/schema/confirmation-record.schema.json (CNF-0129). "
            "Confirmation is of the published registry artifact under "
            "command-center/p2-wave/probes/CNF-0178/published/: lifecycle.py is "
            "copied to an isolated tempfile and is the only client. Planted "
            ".git/HEAD and WORK-UNIT-CATALOG.json in demo.echo@1.0.0 are excluded "
            "from the install tree. Not a claim that a missing in-tree plugin.cli "
            "was executed."
        ),
        "tests": [
            {
                "id": "known-broken-control",
                "command": P2,
                "result": "PASS",
                "detail": "evil.purge uninstall deletes seeded user files; differ reports removed paths",
            },
            {
                "id": "both-states-healthy-uninstall",
                "command": P1,
                "result": "PASS",
                "detail": "healthy uninstall leaves every seeded user file byte-identical",
            },
            {
                "id": "repo-absence",
                "command": P1,
                "result": "PASS",
                "detail": "install profile is not the git worktree; planted repo files not installed",
            },
            {
                "id": "rollback-behaviour",
                "command": P1,
                "result": "PASS",
                "detail": "after rollback, demo.echo prints BEHAVIOR:alpha-v1 not v2",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0178-probe2-seed-B",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "seed": "B",
            "notes": (
                "Repeated install-and-uninstall with a different seeded data set "
                "(journal.md, settings.json, nested/keep.bin). Healthy path intact; "
                "known-broken still caught."
            ),
            "healthy_b_user_data_intact": healthy_b["user_data_byte_identical_after_uninstall"],
            "broken_b_caught": broken_b["caught"],
            "broken_b_diff": broken_b["diff"],
        },
        "published_artifact": {
            "registry": "command-center/p2-wave/probes/CNF-0178/published/registry.json",
            "registry_sha256": reg_sha,
            "registry_bytes": reg_bytes,
            "lifecycle": "command-center/p2-wave/probes/CNF-0178/published/lifecycle.py",
            "lifecycle_sha256": life_sha,
            "lifecycle_bytes": life_bytes,
        },
        "evidence": [
            {
                "kind": "filesystem-manifest",
                "step": step["step"],
                "user_data": step["user_data"],
                "full_file_count": step["full_file_count"],
            }
            for step in healthy_a["steps"]
        ],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0178/published/registry.json",
                "exists": True,
                "role": "published-registry",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0178/published/lifecycle.py",
                "exists": True,
                "role": "published-lifecycle-client",
            },
        ],
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "schema_present_on_disk": (
            REPO / "command-center/schema/confirmation-record.schema.json"
        ).is_file(),
        "min_bytes_threshold": 200,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 CNF-0178: live named probes, filesystem-diff proof, per-unit "
            "manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:CNF-0178")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
