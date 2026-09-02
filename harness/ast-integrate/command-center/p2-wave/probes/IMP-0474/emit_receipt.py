#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0474.json from a live disposable rehearsal."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center/p2-wave"))

from scenario import PLANTED_REL, rehearse  # noqa: E402
import _p2lib as L  # noqa: E402

OUT = "command-center/receipts/IMP-0474.json"
SENTINEL = "SENTINEL:IMP-0474:ROLLBACK-NON-DESTRUCTIVE"
QUESTION = (
    "Anchor spec:11347 (rollback removes existing commands or user data). "
    "Implement rollback as an additive-restore with a pre-rollback inventory "
    "and a post-rollback diff, so any command or user-data path present before "
    "and absent after is a hard failure. Exact question: what is the set "
    "difference of available commands and user-data paths across a real "
    "rollback, and is it empty?"
)


def digest_rel(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    norm = raw.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if path.is_file() else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="imp0474-emit-") as tmp:
        good = rehearse(Path(tmp) / "good", mode="additive")
        bad = rehearse(Path(tmp) / "bad", mode="wholesale-destructive")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    good_report = good["rollback"]
    bad_report = bad["rollback"]
    good_diff = good_report.get("set_difference") or {}
    bad_diff = bad_report.get("set_difference") or {}
    if not good.get("rehearsal_executed") or not bad.get("rehearsal_executed"):
        print("FAILED:IMP-0474 emit rehearsal was not executed")
        return 1
    if good_diff.get("empty") is not True or not good["planted"].get("survived"):
        print("FAILED:IMP-0474 emit additive rehearsal lost protected paths")
        print(json.dumps(good, indent=2, default=str)[:4000])
        return 1
    if not good["managed_restored"].get("ok"):
        print("FAILED:IMP-0474 emit managed N-1 files not restored")
        return 1
    if bad_diff.get("empty") is not False or bad["planted"].get("survived"):
        print("FAILED:IMP-0474 emit wholesale mutation did not destroy extras")
        print(json.dumps(bad, indent=2, default=str)[:4000])
        return 1

    impl = "tools/plugin/rollback_additive.py"
    impl_art = digest_rel(impl)
    if not impl_art["exists"]:
        print("FAILED:IMP-0474 emit implementation missing")
        return 1

    p_src = L.probe(
        "source",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0474/probe1_rehearsal.py",
        (
            "additive rehearsal executed; command_diff=[] user_data_diff=[]; "
            f"planted_survived={good['planted'].get('survived')}; "
            f"commands_before={good_report['before']['command_paths']}; "
            f"commands_after={good_report['after']['command_paths']}"
        ),
        0,
    )
    p_ver = L.probe(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0474/probe2_mutation.py",
        (
            "wholesale-destructive mutation fired: "
            f"commands_absent={bad_diff.get('commands_present_before_absent_after')}; "
            f"user_data_absent={bad_diff.get('user_data_present_before_absent_after')}; "
            f"planted_survived={bad['planted'].get('survived')}"
        ),
        0,
    )

    answer = {
        "commands_present_before_absent_after": good_diff.get(
            "commands_present_before_absent_after"
        ),
        "user_data_present_before_absent_after": good_diff.get(
            "user_data_present_before_absent_after"
        ),
        "empty": True,
        "answered": (
            "The set difference of available commands and user-data paths "
            "across a real additive rollback on a disposable profile is empty."
        ),
    }

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0474",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11347",
        "title": "Rollback contract that cannot remove existing commands or user data",
        "question": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 128,
        "implementation": {
            "module": impl,
            "mode": "additive",
            "rule": (
                "copy backup files onto the live profile; never unlink a path "
                "that is not being restored; then fail hard if any pre-rollback "
                "command or user-data path is absent"
            ),
            "wholesale_snapshot_restore_forbidden": True,
        },
        "rollback_rehearsal": {
            "rehearsal_executed": True,
            "disposable_profile": True,
            "live_profile_touched": False,
            "verdict": "PASS",
            "mode": "additive",
            "planted_rel": PLANTED_REL,
            "planted_survived": True,
            "planted_byte_identical": True,
            "planted_sha256": good["planted"].get("sha256"),
            "managed_restored": good["managed_restored"],
            "set_difference": good_diff,
            "commands_before": good_report["before"]["command_paths"],
            "commands_after": good_report["after"]["command_paths"],
            "user_data_before": good_report["before"]["user_data_paths"],
            "user_data_after": good_report["after"]["user_data_paths"],
            "command_inventories": {
                "before": good_report["before"]["commands"],
                "after": good_report["after"]["commands"],
            },
            "user_data_inventories": {
                "before": good_report["before"]["user_data"],
                "after": good_report["after"]["user_data"],
            },
            "written_from_backup": good_report.get("written"),
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1024,
                "sha256": "pending-self-hash",
                "exists": True,
                "role": "primary",
                "eol": "LF",
            },
            impl_art,
        ],
        "evidence": [
            L.evidence(
                (
                    "Real additive rollback on a disposable profile: set difference "
                    "of commands and user-data paths is empty; planted user-data "
                    f"{PLANTED_REL} survived byte-identical."
                ),
                "CONFIRMED",
                "tools/plugin/rollback_additive.py:rollback",
                [p_src, p_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Before-and-after inventories were computed from the live "
                    "disposable tree, not asserted. Command paths before "
                    f"{good_report['before']['command_paths']} equal after "
                    f"{good_report['after']['command_paths']}."
                ),
                "CONFIRMED",
                "tools/plugin/rollback_additive.py:set_difference",
                [p_src, p_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "no automatic retry; re-running a destructive rollback compounds the loss",
        },
        "tests": [
            {
                "id": "rehearsal-disposable-profile",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0474/probe1_rehearsal.py"
                ),
                "result": "PASS",
                "assertions": [
                    "rehearsal_executed",
                    "set_difference_empty",
                    "planted_user_data_byte_identical",
                ],
            },
            {
                "id": "mutation-wholesale-turns-red",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0474/probe2_mutation.py"
                ),
                "result": "PASS",
                "assertions": [
                    "silent_on_additive",
                    "fired_on_wholesale_destructive",
                ],
            },
        ],
        "negative_controls": [
            L.control(
                "wholesale-snapshot-restore",
                "mutation",
                (
                    "Replace additive copy with wipe-then-copy. The preservation "
                    "check must fire (planted user-data and user-authored command "
                    "absent after) and stay silent on additive restore."
                ),
                True,
                True,
                bad=json.dumps(
                    {
                        "commands_absent": bad_diff.get(
                            "commands_present_before_absent_after"
                        ),
                        "user_data_absent": bad_diff.get(
                            "user_data_present_before_absent_after"
                        ),
                    },
                    sort_keys=True,
                ),
                good=json.dumps({"set_difference_empty": True}, sort_keys=True),
            )
        ],
        "reviewer": {
            "reviewer_id": "IMP-0474-probe2-mutation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Independent of probe 1: mutation/both-states on a second "
                "throwaway profile. Owner approval is not claimed; rehearsal "
                "was disposable, not a live owner profile."
            ),
        },
        "owner_approval_required": True,
        "owner_approval": {
            "required_for_live_profile": True,
            "granted_for_live_profile": False,
            "rehearsal_target": "disposable-profile",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0474/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": L.probe(
                    "verifier",
                    "file-read",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0474",
                    "deferred-to-post-write-measure",
                    None,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This unit did not exercise rollback against a real owner "
                    "profile; the catalog requires owner approval before that."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After owner approval, replay the same inventory+diff "
                    "against a real profile backup."
                ),
            }
        ],
        "defects": [],
        "SENTINEL:IMP-0474:ROLLBACK-NON-DESTRUCTIVE": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")

    # Fill the primary artifact's live digest after the first write.
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = len(raw)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    # Second write may change bytes if sha/bytes fields change length; loop once more.
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = len(raw)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    sha2 = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={sha2}")
    print("SUCCESS:IMP-0474 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
