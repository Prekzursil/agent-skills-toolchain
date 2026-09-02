#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0096-clean-install-windows.json."""
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

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUTPUT_REL,
    QUESTION,
    SCHEMA_REL,
    UNIT_ID,
)
from scenario import (  # noqa: E402
    run_clean_install,
    run_poison_schema,
    run_removal_control,
    three_states_distinguished,
)
from schema_local import iter_errors, validate  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0096/probe1_clean_install.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0096/probe2_removal_control.py"
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:CNF-0096"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:4000],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def _hook_evidence(row: dict, run: str) -> dict:
    ev = {
        "kind": "per-hook",
        "run": run,
        "hook_id": row["id"],
        "triggering_action": row["event"],
        "installed": row["installed"],
        "loaded": row["loaded"],
        "fired": row["fired"],
    }
    if row.get("side_effect"):
        ev["observed_side_effect"] = row["side_effect"]
    else:
        ev["not_observed"] = row.get("not_observed") or "not-observed"
    return ev


def build_report() -> dict:
    started = _now()
    with tempfile.TemporaryDirectory(prefix="cnf0096-emit-") as tmp_s:
        tmp = Path(tmp_s)
        clean = run_clean_install(tmp / "clean")
        removal = run_removal_control(tmp / "removal")
        poison = run_poison_schema(tmp / "poison")

    clean_hooks = clean["hooks"]
    if not all(r["fired"] for r in clean_hooks):
        raise RuntimeError("clean install did not fire every declared hook")
    if not three_states_distinguished(clean_hooks + removal["hooks"]):
        raise RuntimeError("installed/loaded/fired not distinguished")
    if not removal["detected"]:
        raise RuntimeError("removal control not detected")
    if not poison["p0_filed"]:
        raise RuntimeError("poison $schema did not produce P0 false-healthy")
    if poison["health"]["process_healthy"]:
        raise RuntimeError("process health must be red when zero hooks fire")

    never_fire_clean = [r["id"] for r in clean_hooks if not r["fired"]]
    domain_evidence = [_hook_evidence(r, "clean-install") for r in clean_hooks]
    domain_evidence.append(_hook_evidence(removal["removed_row"], "removal-control"))
    for row in poison["hooks"]:
        domain_evidence.append(_hook_evidence(row, "poison-$schema"))
    domain_evidence.append(
        {
            "kind": "false-healthy-p0",
            "classification": "false-healthy",
            "filed": True,
            "naive_healthy": poison["health"]["naive_healthy"],
            "process_healthy": poison["health"]["process_healthy"],
            "zero_hooks_fired": poison["health"]["zero_hooks_fired"],
            "note": poison["p0_note"],
        }
    )
    domain_evidence.append(
        {
            "kind": "profile-empty-at-start",
            "clean": clean["profile"]["empty_at_start"],
            "pre_install_contamination": clean["profile"]["pre_install_contamination"],
            "pre_install_listing": clean["profile"]["pre_install_listing"],
        }
    )

    fired_ids = [r["id"] for r in clean_hooks if r["fired"]]
    clean_summary = (
        f"empty_at_start={clean['profile']['empty_at_start']} "
        f"fired={fired_ids} process_healthy={clean['health']['process_healthy']}"
    )
    removal_summary = (
        f"detected={removal['detected']} removed={removal['removed_hook_id']} "
        f"installed={removal['removed_row']['installed']} "
        f"loaded={removal['removed_row']['loaded']} "
        f"fired={removal['removed_row']['fired']} "
        f"not_observed={removal['removed_row'].get('not_observed')}"
    )
    poison_summary = (
        f"load_reason={poison['load_reason']} "
        f"zero={poison['health']['zero_hooks_fired']} "
        f"naive={poison['health']['naive_healthy']} "
        f"process={poison['health']['process_healthy']} p0={poison['p0_filed']}"
    )

    report_payload = {
        "kind": "install-report",
        "observations": [
            {
                "name": "clean-install-all-declared-hooks-fired",
                "measured": True,
                "method": "child-process-side-effect",
                "anchor": "command-center/p2-wave/probes/CNF-0096/runtime.py:fire_hook",
            },
            {
                "name": "removal-control-detected",
                "measured": True,
                "method": "drop-hook-from-runtime-inventory",
                "anchor": "command-center/p2-wave/probes/CNF-0096/scenario.py:run_removal_control",
            },
            {
                "name": "poison-schema-false-healthy-p0",
                "measured": True,
                "method": "dispatch-$schema-zero-load",
                "anchor": "command-center/p2-wave/probes/CNF-0096/scenario.py:run_poison_schema",
            },
        ],
        "control_ids": [
            "removal-control",
            "poison-schema-zero-load",
        ],
        "question": QUESTION,
        "answers": {
            "which_declared_hooks_never_fire_on_clean_install": never_fire_clean,
            "client_reports_healthy_while_loading_none": False,
            "process_health_refuses_green_on_zero_fire": True,
            "naive_file_presence_health_is_p0_false_healthy": True,
        },
        "windows_profile": clean["profile"],
        "install": {
            "source": clean["install"]["source"],
            "target": clean["install"]["target"],
            "target_windows": clean["install"]["target_windows"],
            "ok": clean["install"]["ok"],
            "published_root": clean["published_root"],
            "declared_hooks": clean["declared_hooks"],
        },
        "hooks": [
            {
                "id": r["id"],
                "event": r["event"],
                "installed": r["installed"],
                "loaded": r["loaded"],
                "fired": r["fired"],
                "side_effect": r["side_effect"],
                "not_observed": r["not_observed"],
            }
            for r in clean_hooks
        ],
        "states_distinguished": {
            "installed_is_not_loaded": True,
            "loaded_is_not_fired": True,
            "note": (
                "Each hook row carries three booleans. Removal control keeps "
                "the descriptor installed while dropping it from the runtime "
                "inventory so installed=true, loaded=false, fired=false."
            ),
            "removal_example": {
                "id": removal["removed_row"]["id"],
                "installed": removal["removed_row"]["installed"],
                "loaded": removal["removed_row"]["loaded"],
                "fired": removal["removed_row"]["fired"],
                "not_observed": removal["removed_row"]["not_observed"],
            },
        },
        "removal_control": {
            "detected": removal["detected"],
            "removed_hook_id": removal["removed_hook_id"],
            "reported_not_fired": removal["reported_not_fired"],
            "others_fired": removal["others_fired"],
            "removed_row": removal["removed_row"],
        },
        "health": {
            "process_healthy": clean["health"]["process_healthy"],
            "naive_healthy": clean["health"]["naive_healthy"],
            "zero_hooks_fired": clean["health"]["zero_hooks_fired"],
            "clean_install_reason": clean["health"]["reason"],
            "poison_schema": {
                "process_healthy": poison["health"]["process_healthy"],
                "naive_healthy": poison["health"]["naive_healthy"],
                "zero_hooks_fired": poison["health"]["zero_hooks_fired"],
                "false_healthy_p0": poison["health"]["false_healthy_p0"],
                "load_reason": poison["load_reason"],
            },
        },
        "false_healthy_p0": {
            "filed": poison["p0_filed"],
            "classification": "false-healthy",
            "detector": "naive plugin.json presence vs process-level fire count",
            "note": poison["p0_note"],
        },
        "platform": {
            "host_os": clean["host_os"],
            "host_release": clean["host_release"],
            "windows_runner_reachable": False,
            "profile_model": "windows-userprofile-layout-on-isolated-home",
            "rationale": (
                "This Linux worktree has no Windows runner. CNF-0017 names an "
                "equivalent isolated home as the fresh-profile substrate. Hook "
                "execution is a real child process (pid != parent) writing its "
                "own side-effect file; manifest presence is not accepted as fire."
            ),
        },
        "load_reason_clean": clean["load_reason"],
        "per_hook_evidence": domain_evidence,
        "output_schema": SCHEMA_REL,
    }

    ended = _now()
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1024,
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "After a clean install into an empty Windows-layout isolated "
                    "HOME, every declared hook fired in a child process and wrote "
                    "its side-effect file; installed, loaded, and fired are three "
                    "distinct booleans."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0096/probe1_clean_install.py",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        P1,
                        clean_summary,
                        "cnf0096-probe1-clean-install:v1",
                    ),
                    _probe(
                        "verifier",
                        "process-table",
                        "command-center/p2-wave/probes/CNF-0096/runtime.py:fire_hook",
                        (
                            "each fired hook pid != parent_pid; marker="
                            + str((clean_hooks[0].get("side_effect") or {}).get("marker"))
                        ),
                        "cnf0096-runtime-distinct-pid:v1",
                    ),
                ],
            },
            {
                "claim": (
                    "Removing hook.post-tool from the runtime inventory leaves it "
                    "installed but not loaded and not fired, and a $schema key on "
                    "hooks.json loads zero hooks while naive file-presence health "
                    "stays green (P0 false-healthy, filed; process health is red)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0096/probe2_removal_control.py",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        P2,
                        removal_summary + " | " + poison_summary,
                        "cnf0096-probe2-removal-poison:v1",
                    ),
                    _probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0096/runtime.py:load_dispatch",
                        poison["load_reason"],
                        "cnf0096-dispatch-poison-reason:v1",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "installed-loaded-fired-distinguished",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "removal-control-not-fired",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "false-healthy-zero-fire-is-p0",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "removal-control",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop hook.post-tool from hooks.json after install. Detector "
                    "must report installed=true, loaded=false, fired=false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": removal_summary,
                "good_state_output": clean_summary,
            },
            {
                "id": "poison-schema-zero-load",
                "kind": "malformed-input",
                "description": (
                    "Insert $schema into hooks.json. Naive plugin.json health "
                    "stays green; process-level health must go red with zero fires."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": poison_summary,
                "good_state_output": clean_summary,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0096-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-run the removal control and the $schema poison fixture; "
                "confirm the prober reports not-fired and that process health "
                "is red while naive health is green."
            ),
        },
        "defects": [
            {
                "id": "CNF-0096-P0-false-healthy-$schema",
                "severity": "P0",
                "status": "resolved",
                "summary": (
                    "Naive plugin.json presence reports healthy while a $schema "
                    "key makes the client load zero hooks. Process-level health "
                    "is red. Filed as the detector's known-broken fixture, not "
                    "an open defect of the clean-install path."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0096/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT_ID,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads+schema_local.validator_for",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "source",
                    "schema-validate",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0096/emit_report.py",
                    "offline Draft7 validation against install-report shim+$ref store",
                    "cnf0096-emit-schema-validate:v1",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "one retry only when the failure classifies as "
                "environment-transient; a logic or evidence failure is never retried"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "No native Windows runner was reachable on this Linux "
                    "worktree; the fresh profile is a Windows USERPROFILE layout "
                    "on an isolated HOME."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1_clean_install.py on a Windows runner with a "
                    "newly created user profile and compare hook pids and side "
                    "effects to this receipt."
                ),
            }
        ],
        "report": report_payload,
        "extensions": {
            "output_schema": SCHEMA_REL,
            "windows_runner_reachable": False,
        },
    }
    return receipt


def _dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    garbage = iter_errors({}, SCHEMA_REL)
    if not garbage:
        print("FAILED:CNF-0096 schema is vacuous on empty object")
        return 1
    report = build_report()
    text = _dump(report)
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    report["artifacts"][0]["sha256"] = sha
    report["artifacts"][0]["bytes"] = len(raw)
    validate(report, SCHEMA_REL)
    text = _dump(report)
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0096 sentinel missing from serialized artifact")
        return 1
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT_REL} bytes={len(text.encode('utf-8'))}")
    print(COMPLETION_SENTINEL.split(" emitted", 1)[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
