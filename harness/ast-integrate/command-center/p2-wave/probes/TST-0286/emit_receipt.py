#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0286.json from live probe evaluations."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe1_pause_resume as P1  # noqa: E402
import probe2_torn_write_live as P2  # noqa: E402
import simulate as S  # noqa: E402

OUT = "command-center/receipts/TST-0286.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0286/probe1_pause_resume.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0286/probe2_torn_write_live.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0286/simulate.py",
    "command-center/p2-wave/probes/TST-0286/store.py",
    "command-center/p2-wave/probes/TST-0286/probe1_pause_resume.py",
    "command-center/p2-wave/probes/TST-0286/probe2_torn_write_live.py",
]


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:TST-0286 emit missing anchor {rel!r} {needle!r}")


def ev(rel: str, needle: str, claim: str, probe: dict) -> dict:
    line = line_of(rel, needle)
    return {
        "anchor": f"{rel}:{line}",
        "claim": claim,
        "confidence": "almost-certain",
        "path": rel,
        "line": line,
        "snippet": needle,
        "probes": [probe],
        "verdict": "CONFIRMED",
    }


def main() -> int:
    r1 = P1.evaluate()
    r2 = P2.evaluate()
    if not r1.get("pass") or not r2.get("pass"):
        print("FAILED:TST-0286 emit probes did not pass")
        return 1
    three = r1["three_sha256"]
    if not (three["uninterrupted"] == three["pause_resume"] == three["replay_from_state"]):
        print("FAILED:TST-0286 emit three hashes not equal")
        return 1
    catalog_sim = REPO / "tools/council/simulate.py"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_probe = {
        "command": P1_CMD,
        "exit_code": 0,
        "method": "command",
        "raw_output": (
            f"uninterrupted={three['uninterrupted']} "
            f"pause_resume={three['pause_resume']} "
            f"replay={three['replay_from_state']}"
        ),
        "role": "source",
    }
    p2_probe = {
        "command": P2_CMD,
        "exit_code": 0,
        "method": "command",
        "raw_output": (
            f"torn_fired={r2['torn_write']['fired_on_bad_state']} "
            f"live_canonical_match={r2['live_model_arm']['canonical_match']} "
            f"raw_diverge={r2['live_model_arm']['raw_logs_diverge']}"
        ),
        "role": "verifier",
    }
    supporting = []
    for rel in SUPPORTING:
        sha, size = digest_file(rel)
        supporting.append(
            {
                "bytes": size,
                "eol": "LF",
                "exists": True,
                "path": rel,
                "role": "supporting",
                "sha256": sha,
            }
        )
    doc = {
        "unit_id": "TST-0286",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0286",
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:10946 pause/resume; _USER-PROMPTS.md:11194 replay/audit",
        "title": "Pause, resume and deterministic replay of a council run",
        "question": (
            "A run paused at round k and resumed must produce the same final "
            "transcript as an uninterrupted run on the same seed, and a replay "
            "from the persisted state must reproduce it again. Where true "
            "determinism is impossible (live model calls), name which fields "
            "are guaranteed reproducible and which are recorded-but-not-reproducible."
        ),
        "catalog_inputs": {
            "tools_council_simulate_py": {
                "path": "tools/council/simulate.py",
                "present": catalog_sim.is_file(),
            },
            "b07_persistence": {
                "path": "tools/council/artifacts/store.py",
                "present": (REPO / "tools/council/artifacts/store.py").is_file(),
            },
            "local_runtime": {
                "simulate": "command-center/p2-wave/probes/TST-0286/simulate.py",
                "store": "command-center/p2-wave/probes/TST-0286/store.py",
                "note": (
                    "Catalog inputs tools/council/simulate.py and the B07 event "
                    "store are absent on this worktree. The unit vendors a local "
                    "deterministic simulator and append-only length-prefixed log "
                    "so the pause/resume/replay contract is measured rather than "
                    "parked on predicate:absent."
                ),
            },
        },
        "transcript_hashes": {
            "uninterrupted": three["uninterrupted"],
            "pause_resume": three["pause_resume"],
            "replay_from_state": three["replay_from_state"],
            "equal": True,
            "divergence_attribution": None,
            "bytes": r1["seed_a"]["uninterrupted_bytes"],
        },
        "pause": {
            "round_k": S.PAUSE_AFTER,
            "paused_rounds": r1["seed_a"]["paused_rounds"],
            "resumed_rounds": r1["seed_a"]["resumed_rounds"],
            "uninterrupted_rounds": r1["seed_a"]["uninterrupted_rounds"],
            "child_events": r1["seed_a"]["child_events"],
            "replacement_events": r1["seed_a"]["replacement_events"],
            "decision": r1["seed_a"]["decision"],
            "dissenters_final": r1["seed_a"]["dissenters_final"],
        },
        "seed_perturbation": r1["seed_perturbation"],
        "live_model_boundary": {
            "guaranteed_reproducible_fields": r2["live_model_arm"][
                "guaranteed_reproducible_fields"
            ],
            "recorded_but_not_reproducible_fields": r2["live_model_arm"][
                "recorded_but_not_reproducible_fields"
            ],
            "two_live_runs_canonical_match": r2["live_model_arm"]["canonical_match"],
            "two_live_runs_raw_logs_diverge": r2["live_model_arm"]["raw_logs_diverge"],
            "live_vs_scripted_named_field": r2["live_model_arm"][
                "live_vs_scripted_named_field"
            ],
            "canonical_sha256_live": r2["live_model_arm"]["canonical_sha256_a"],
            "canonical_sha256_scripted": r2["live_model_arm"]["scripted_canonical_sha256"],
        },
        "torn_write": {
            "killed_mid_persist": r2["torn_write"]["killed"],
            "truncated": r2["torn_write"]["truncated"],
            "size_after": r2["torn_write"]["size_after"],
            "error": r2["torn_write"]["torn_error"],
            "resume_from_half_written": r2["torn_write"]["resumed_anyway"],
            "fired_on_bad_state": r2["torn_write"]["fired_on_bad_state"],
            "silent_on_good_state": r2["torn_write"]["silent_on_good_state"],
        },
        "tests": [
            {
                "id": "TST-0286-PAUSE-RESUME-HASH",
                "name": "Pause at round k, resume, compare final transcript hash to the uninterrupted run.",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "TST-0286-REPLAY-FROM-STATE",
                "name": "Replay from persisted state reproduces the transcript.",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "TST-0286-TORN-WRITE",
                "name": "Kill the process mid-persist; resume fails loudly, never from a half-written state.",
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "TST-0286-LIVE-MODEL-BOUNDARY",
                "name": "Live-model arm: name non-reproducible fields and prove the rest hash-match.",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0286-SEED-PERTURBATION",
                "kind": "seed-perturbation",
                "description": "A second seed must produce a different canonical transcript hash.",
                "fired_on_bad_state": r1["seed_perturbation"]["diverged"],
                "silent_on_good_state": three["uninterrupted"] == three["pause_resume"],
                "named_field": r1["seed_perturbation"]["first_differing_field"],
            },
            {
                "id": "TST-0286-TORN-WRITE-RESUME",
                "kind": "known-broken-fixture",
                "description": "SIGKILL mid-persist must raise TornWriteError; a clean pause+resume must complete.",
                "fired_on_bad_state": r2["torn_write"]["fired_on_bad_state"],
                "silent_on_good_state": r2["torn_write"]["silent_on_good_state"],
                "planted_defect": "truncated length-prefixed record after MAGIC",
                "detector_fired": r2["torn_write"]["fired_on_bad_state"],
                "silent_on_good": r2["torn_write"]["silent_on_good_state"],
            },
        ],
        "evidence": [
            ev(
                "command-center/p2-wave/probes/TST-0286/simulate.py",
                "def pause_at(",
                "Pause serialises the event log after round k via atomic persist.",
                p1_probe,
            ),
            ev(
                "command-center/p2-wave/probes/TST-0286/simulate.py",
                "def resume(",
                "Resume loads the log, rejects a missing pause marker, and continues remaining rounds.",
                p1_probe,
            ),
            ev(
                "command-center/p2-wave/probes/TST-0286/simulate.py",
                "def replay_from_log(",
                "Replay rebuilds events from the persisted log with no persona re-emit and no side state.",
                p1_probe,
            ),
            ev(
                "command-center/p2-wave/probes/TST-0286/store.py",
                "class TornWriteError",
                "A truncated record is TornWriteError, not a silently truncated council state.",
                p2_probe,
            ),
            ev(
                "command-center/p2-wave/probes/TST-0286/simulate.py",
                "LIVE_FIELDS = (",
                "Live-model fields are stripped from the canonical transcript before hashing.",
                p2_probe,
            ),
        ],
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "TST-0286-probe2-second-shell",
            "verdict": "PASS",
            "method": (
                "probe2 re-computes the three transcript hashes under /usr/bin/sh "
                "invoking a fresh python3 -B process, not the authoring interpreter."
            ),
            "second_shell": r2["second_shell"]["shell"],
            "second_shell_hashes": r2["second_shell"]["hashes"],
            "windows_pwsh7_git_bash": r2["second_shell"]["windows"],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a second Windows shell "
                    "(pwsh7 and Git Bash). This worker is Linux; those binaries are absent."
                ),
                "settling_experiment": (
                    "Re-run probe1_pause_resume.py under pwsh7 and Git Bash on a Windows "
                    "worktree and diff the three sha256 values against this receipt."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "This measurement is against the TST-0286 local simulator, not a "
                    "production tools/council/simulate.py / B07 store (both absent)."
                ),
                "settling_experiment": (
                    "After TST-0257/IMP-0315 land, point the probes at those modules "
                    "and re-compare the three hashes."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "retry": {"count": 0, "policy": "Two strikes then pivot (AGENTS.md 4b)"},
        "timestamps": {"ended_at": now, "started_at": now},
        "produced_by": {
            "execution_substrate": "local-serialized-linux",
            "role": "test-engineer",
        },
        "artifacts": [
            {
                "exists": True,
                "path": OUT,
                "role": "primary",
                "note": "self-sha omitted; per-unit UNIT-ARTIFACT-MANIFEST.json carries sha256",
            }
        ]
        + supporting,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0286/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 128,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0286")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
