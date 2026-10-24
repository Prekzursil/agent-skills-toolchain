#!/usr/bin/env python3
"""AUD-0059 NAMED PROBE 2: controlled trigger + both-states enable/disable.

Catalog evidence_requirement Probe 2:
  perform a controlled trigger and observe the effect (an injected context line,
  a blocked call, a written ledger row) - log silence alone cannot distinguish a
  hook that never fires from one that fires silently.

tests_required:
  both-states control: disable one hook in a scratch config, confirm the trigger
  produces NO effect, re-enable, and confirm it does.

Catalog reviewer_requirement: cross-vendor Codex must re-run ONLY this probe.
Never mutates live settings; all work is under TemporaryDirectory + env redirects.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-controlled-trigger.json"
RAW = PROBE / "probe2-controlled-trigger.raw.txt"
CANARY_SRC = PROBE / "fixtures" / "planted_hook" / "fire_canary.py"
STUB_RECORD = REPO / "hooks" / "stub-ledger" / "record.py"

MARKER = "AUD-0059-PLANTED-FIRE"
lines: list[str] = []


def log(msg: str) -> None:
    lines.append(msg)
    print(msg)


def payload(session_id: str, event: str = "PostToolUse") -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "cwd": str(REPO),
            "hook_event_name": event,
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/aud-0059-scratch/not-a-test.py",
                "content": "# TODO(AUD-0059): planted stub marker for stub-ledger fire path\n",
            },
            "tool_response": {"success": True},
        }
    )


def run_canary(
    canary: Path,
    ledger: Path,
    *,
    disabled: bool,
    session_id: str,
) -> dict:
    env = os.environ.copy()
    env["AUD0059_FIRE_LEDGER"] = str(ledger)
    if disabled:
        env["AUD0059_HOOK_DISABLED"] = "1"
        # also plant .disabled sibling for the code path that checks the file
        (canary.parent / ".disabled").write_text(
            "disabled-by-aud-0059\n", encoding="utf-8"
        )
    else:
        env.pop("AUD0059_HOOK_DISABLED", None)
        dis = canary.parent / ".disabled"
        if dis.is_file():
            dis.unlink()

    before = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    before_n = before.count("\n")
    try:
        r = subprocess.run(
            [sys.executable, str(canary)],
            input=payload(session_id),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(REPO),
        )
        stdout = r.stdout or ""
        stderr = r.stderr or ""
        rc = r.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "TIMEOUT", 124
    after = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    after_n = after.count("\n")
    new_rows = after_n - before_n
    marker_in_stdout = MARKER in stdout
    marker_in_ledger = MARKER in after[len(before) :]
    return {
        "disabled": disabled,
        "exit_code": rc,
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
        "new_ledger_rows": new_rows,
        "marker_in_stdout": marker_in_stdout,
        "marker_in_ledger": marker_in_ledger,
        "effect_observed": bool(marker_in_stdout or marker_in_ledger),
    }


def run_stub_ledger_sanity(scratch: Path) -> dict:
    """Secondary observable: real stub-ledger/record.py against a redirected root."""
    if not STUB_RECORD.is_file():
        return {"ok": False, "reason": "stub-ledger/record.py missing", "skipped": True}
    root = scratch / "stub-ledger-root"
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["STUB_LEDGER_ROOT"] = str(root)
    env.pop("STUB_LEDGER", None)
    # ensure not disabled via env
    session = "aud-0059-stub"
    # enabled fire
    r1 = subprocess.run(
        [sys.executable, str(STUB_RECORD)],
        input=payload(session),
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO),
    )
    files_enabled = list(root.glob("*.ndjson"))
    enabled_bytes = sum(f.stat().st_size for f in files_enabled)
    # disabled via env
    env2 = env.copy()
    env2["STUB_LEDGER"] = "off"
    # clear prior
    for f in files_enabled:
        f.unlink()
    r2 = subprocess.run(
        [sys.executable, str(STUB_RECORD)],
        input=payload(session + "-off"),
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        env=env2,
        cwd=str(REPO),
    )
    files_disabled = list(root.glob("*.ndjson"))
    disabled_bytes = sum(f.stat().st_size for f in files_disabled)
    ok = enabled_bytes > 0 and disabled_bytes == 0
    return {
        "ok": ok,
        "skipped": False,
        "enabled_exit": r1.returncode,
        "disabled_exit": r2.returncode,
        "enabled_bytes": enabled_bytes,
        "disabled_bytes": disabled_bytes,
        "description": (
            "stub-ledger/record.py writes under STUB_LEDGER_ROOT when enabled; "
            "STUB_LEDGER=off produces no file bytes after the same trigger."
        ),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud-0059-") as td:
        scratch = Path(td)
        canary_dir = scratch / "planted_hook"
        canary_dir.mkdir(parents=True)
        canary = canary_dir / "fire_canary.py"
        shutil.copy2(CANARY_SRC, canary)
        ledger = scratch / "fire-ledger.jsonl"

        log("AUD-0059 NAMED PROBE 2: controlled trigger + both-states")
        log("unit=AUD-0059")

        # State A: DISABLED — trigger must produce NO effect
        disabled_run = run_canary(
            canary, ledger, disabled=True, session_id="aud-0059-off"
        )
        log(
            f"DISABLED effect={disabled_run['effect_observed']} "
            f"new_rows={disabled_run['new_ledger_rows']} "
            f"stdout_marker={disabled_run['marker_in_stdout']} rc={disabled_run['exit_code']}"
        )

        # State B: ENABLED — trigger must produce observable effect
        enabled_run = run_canary(
            canary, ledger, disabled=False, session_id="aud-0059-on"
        )
        log(
            f"ENABLED effect={enabled_run['effect_observed']} "
            f"new_rows={enabled_run['new_ledger_rows']} "
            f"stdout_marker={enabled_run['marker_in_stdout']} "
            f"ledger_marker={enabled_run['marker_in_ledger']} rc={enabled_run['exit_code']}"
        )

        both_states = (not disabled_run["effect_observed"]) and enabled_run[
            "effect_observed"
        ]
        log(f"BOTH_STATES_PLANTED ok={both_states}")

        stub = run_stub_ledger_sanity(scratch)
        if stub.get("skipped"):
            log(f"STUB_LEDGER_SANITY skipped reason={stub.get('reason')}")
        else:
            log(
                f"STUB_LEDGER_SANITY ok={stub['ok']} "
                f"enabled_bytes={stub['enabled_bytes']} disabled_bytes={stub['disabled_bytes']}"
            )

        control = {
            "id": "AUD0059-C1",
            "kind": "mutation",
            "description": (
                "Disable planted canary (scratch .disabled + env), trigger → no ledger/"
                "context effect; re-enable, same trigger → ledger row + context marker."
            ),
            "silent_on_good_state": not disabled_run[
                "effect_observed"
            ],  # disabled = no effect
            "fired_on_bad_state": enabled_run[
                "effect_observed"
            ],  # naming: enabled fires
            "ok": both_states,
            "disabled_run": {
                "effect_observed": disabled_run["effect_observed"],
                "new_ledger_rows": disabled_run["new_ledger_rows"],
                "exit_code": disabled_run["exit_code"],
            },
            "enabled_run": {
                "effect_observed": enabled_run["effect_observed"],
                "new_ledger_rows": enabled_run["new_ledger_rows"],
                "marker_in_stdout": enabled_run["marker_in_stdout"],
                "marker_in_ledger": enabled_run["marker_in_ledger"],
                "exit_code": enabled_run["exit_code"],
            },
        }

        result = {
            "ok": both_states and (stub.get("skipped") or stub.get("ok")),
            "unit": "AUD-0059",
            "probe": 2,
            "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "both_states": both_states,
            "control": control,
            "stub_ledger_sanity": stub,
            "live_tree_mutated": False,
            "worktree_mode": "TemporaryDirectory",
            "observables": [
                "ledger_row",
                "additionalContext_marker",
                "stub_ledger_ndjson",
            ],
        }
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        lines.append(f"both_states={both_states}")
        lines.append(f"control_ok={control['ok']}")
        lines.append(
            "SUCCESS:AUD-0059-probe2" if result["ok"] else "FAILED:AUD-0059-probe2"
        )
        RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # also dump to stdout already via log()
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
