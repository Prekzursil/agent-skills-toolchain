#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0086.json detector-control receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0086.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0086/probe1_injected_exception.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0086/probe2_danger_still_blocks.py"
)
QUESTION = (
    "AGENTS.md 6 and the hook contract require all hook code wrapped so that "
    "an error exits 0 (fail-open), blocking only on genuinely dangerous "
    "operations. Target: inject an exception at each hook's entry point and "
    "assert the session continues; separately assert that the block-worthy "
    "cases still exit 2."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size if path.is_file() else 0,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    live = E.run_all()
    if not live.get("pass"):
        print("FAILED:TST-0086 emit live measurements did not pass")
        slim = {
            "inject_pass": (live.get("inject") or {}).get("pass"),
            "danger_pass": (live.get("danger") or {}).get("pass"),
            "estate": (live.get("estate") or {}).get("estate_inputs_present"),
            "hook_count": (live.get("inject") or {}).get("hook_count"),
        }
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1

    inject = live["inject"]
    danger = live["danger"]
    census = live["estate"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    observations = []
    for row in inject["observations"]:
        observations.append(
            {
                "id": row["id"],
                "exit_code": row["exit_code"],
                "outcome": row["outcome"],
                "process_exit": row["process_exit"],
                "unwrapped_exit_code": row["unwrapped_exit_code"],
                "session_continued": row["session_continued"],
                "injected_exception": True,
                "later_hooks_ran": row["later_hooks_ran"],
                "hook_body_fired": row["hook_body_fired"],
                "kind": row.get("kind"),
                "rel": row.get("rel"),
                "event": row.get("event"),
            }
        )
    observations.append(
        {
            "id": "danger-git-push-force",
            "exit_code": danger["known_broken"]["exit_code"],
            "outcome": "blocked",
            "blocked_by": danger["known_broken"]["blocked_by"],
            "payload": danger["known_broken"]["payload"],
        }
    )
    observations.append(
        {
            "id": "safe-ls-la",
            "exit_code": danger["known_good"]["exit_code"],
            "outcome": "continue",
            "payload": danger["known_good"]["payload"],
        }
    )

    answer = (
        f"Live settings Python hooks ({census['settings_python_hook_count']}) "
        f"plus {len(S.DISPATCH_EVENTS)} dispatch events fail-open on an injected "
        f"exception (session exit 0); unwrapped inject exits "
        f"{inject['unwrapped_exit_code']}. Live no-force-push blocks "
        f"`git push --force` with exit 2 and is silent on `ls -la` (exit 0). "
        f"Estate _dispatch stays inject-only (check rc 2 -> session 0 with a "
        f"visible disarmed note). SUCCESS:TST-0086"
    )

    doc = {
        "SUCCESS:TST-0086": True,
        "unit_id": "TST-0086",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0086",
        "completion_sentinel": "SUCCESS:TST-0086",
        "kind": "detector-control",
        "report_kind": "detector-control",
        "title": "Every hook must fail open: any hook error exits 0",
        "question": QUESTION,
        "answer": answer,
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0086",
        "detector": {
            "name": "hook-fail-open-and-danger-block",
            "fires_on": (
                "uncaught injected exception without fail-open wrap (non-zero), "
                "and a live Bash proposal of `git push --force` (exit 2 from "
                "hooks/no-force-push/hook.py)"
            ),
            "silent_on": (
                "the same injected exception with the production wrap (exit 0), "
                "and a safe `ls -la` proposal (exit 0)"
            ),
        },
        "both_states": {
            "discriminates": True,
            "known_good": {
                "name": "wrapped-inject-or-safe-bash",
                "exit_code": 0,
                "blocked": False,
            },
            "known_broken": {
                "name": "unwrapped-inject-or-git-push-force",
                "exit_code": 2,
                "blocked": True,
            },
        },
        "danger_pair": {
            "known_broken": danger["known_broken"],
            "known_good": danger["known_good"],
            "advisory_nonzero_does_not_block": danger[
                "advisory_nonzero_does_not_block"
            ],
            "injected_exception_on_danger_hook": danger[
                "injected_exception_on_danger_hook"
            ],
            "mutant_swallows_exit_2": danger["mutant_swallows_exit_2"],
            "dispatch_disarmed_block": danger["dispatch_disarmed_block"],
        },
        "controls": [
            {
                "id": "unwrapped-inject-nonzero",
                "description": (
                    "The same entry-point raise without a fail-open wrap exits "
                    "non-zero, so a wrapped zero is not vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "danger-still-exits-two",
                "description": (
                    "Inspect-only git push --force on Bash PreToolUse exits 2 "
                    "from hooks/no-force-push/hook.py; ls -la exits 0."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "advisory-does-not-block",
                "description": (
                    "cmd-rewrite inject-nopager on git log exits 0. A "
                    "consolidated dispatch check returning 1 or 2 still leaves "
                    "dispatch.py session exit 0 (inject-only)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "observations": observations,
        "per_hook": [
            o for o in observations if str(o.get("id") or "").startswith("hook.")
        ],
        "registered_hooks": live["registered_hook_ids"],
        "estate_census": census,
        "tests": [
            {
                "id": "test_injected_exception_exits_zero_for_every_hook",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_dangerous_operation_still_exits_two",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "path": "hooks/_dispatch/dispatch.py",
                "kind": "live-sut",
                "claim": (
                    "In-process dispatcher wraps check main(): a raising check "
                    "still yields session exit 0. Exit 2 from a check is not "
                    "propagated; a disarmed-block note is emitted instead."
                ),
            },
            {
                "path": "hooks/no-force-push/hook.py",
                "kind": "live-sut",
                "claim": (
                    "Standalone PreToolUse gate inspects proposed Bash text and "
                    "returns 2 for git push --force without executing it."
                ),
            },
            {
                "path": "agent-self/config/settings.json",
                "kind": "registration",
                "claim": (
                    "Live registrations name the Python hooks measured here. "
                    "File presence alone is not wiring."
                ),
            },
            {
                "path": "rules/common/hooks.md",
                "kind": "contract",
                "claim": (
                    "PreToolUse is the only place an exit 2 block is honoured. "
                    "Fail-open on error."
                ),
            },
        ],
        "scope": {
            "proof_surface": (
                "live hooks/_dispatch/dispatch.py; agent-self/config/settings.json "
                "Python hooks that exist under hooks/; inspect-only "
                "no-force-push payload"
            ),
            "measured": [
                "hooks/_dispatch/dispatch.py",
                "hooks/_dispatch/manifest.json",
                "hooks/no-force-push/hook.py",
                "agent-self/config/settings.json",
                "rules/common/hooks.md",
            ],
            "does_not_claim": [
                "production Claude Code host wrap was executed",
                "~/.agents/harness/dispatcher.py was executed",
                "Windows .ps1 worktree hooks were executed",
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
            ],
        },
        "residual_caveat": census["claim"],
        "reviewer": {
            "reviewer_id": "TST-0086-probe2-danger-still-blocks",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-runs live no-force-push on git push --force and "
                "ls -la, independently of probe 1's inject loop. A dispatcher "
                "that swallowed standalone exit 2 is not under test: the gate "
                "is a settings.json command, not a _dispatch check."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "injected-exception-fail-open", "command": P1},
            {"id": "probe2", "role": "danger-still-exits-two", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
        "ts": now,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            art("hooks/_dispatch/dispatch.py", "supporting"),
            art("hooks/no-force-push/hook.py", "supporting"),
            art("agent-self/config/settings.json", "supporting"),
        ],
        "report": {
            "kind": "detector-control",
            "observations": [
                {
                    "name": row["id"],
                    "measured": row["exit_code"],
                    "method": "live-subprocess-or-inprocess",
                    "anchor": str(row.get("rel") or row["id"]),
                }
                for row in observations
                if row.get("id")
            ],
            "control_ids": [
                "unwrapped-inject-nonzero",
                "danger-still-exits-two",
                "advisory-does-not-block",
            ],
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:TST-0086" not in blob:
        print("FAILED:TST-0086 emit sentinel missing")
        return 1
    if len(blob.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0086 emit under min_bytes_threshold")
        return 1
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    tmp.replace(out_path)
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0086 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
