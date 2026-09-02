"""Controlled trigger: invoke registered hook scripts and observe side effects.

Log silence is not a fire. A fire requires (1) the dispatcher's own record
AND (2) an on-disk effect written by the hook process (inject line, deny
file, or ledger row).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

REGISTERED = HERE / "fixtures" / "registered"
SCRATCH = HERE / "scratch"

EVENT_PAYLOADS = {
    "PreToolUse": {"event": "PreToolUse", "tool": "Bash", "command": "echo aud-0059"},
    "PostToolUse": {"event": "PostToolUse", "tool": "Read", "path": "README.md"},
    "Stop": {"event": "Stop", "reason": "session-stop"},
}


def new_session(name: str) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    sess = SCRATCH / name
    if sess.exists():
        shutil.rmtree(sess)
    sess.mkdir(parents=True)
    (sess / "effects").mkdir()
    return sess


def _run_hook(hook: dict[str, Any], payload: dict[str, Any], session: Path) -> dict[str, Any]:
    script = REGISTERED / str(hook["script"])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AUD0059_ROOT"] = str(HERE)
    env["AUD0059_SESSION"] = str(session)
    env["AUD0059_HOOK_ID"] = str(hook["id"])
    env["AUD0059_EVENT"] = str(hook["event"])
    py = sys.executable or "python3"
    try:
        proc = subprocess.run(
            [py, "-B", str(script)],
            input=json.dumps(payload),
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        rc, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        rc, out, err = 124, "", "TIMEOUT"
    except OSError as exc:
        rc, out, err = 127, "", f"{type(exc).__name__}: {exc}"
    effect_path = session / "effects" / f"{hook['id']}.json"
    effect_doc: dict[str, Any] | None = None
    if effect_path.is_file():
        try:
            effect_doc = json.loads(effect_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            effect_doc = None
    inject_path = session / "context_inject.txt"
    block_path = session / "blocked.json"
    hook_ledger = session / "hook-ledger.jsonl"
    dispatcher_row = {
        "hook_id": hook["id"],
        "event": hook["event"],
        "enabled": True,
        "exit_code": rc,
        "stdout_tail": out.strip()[-500:],
        "stderr_tail": err.strip()[-300:],
        "effect_file_present": effect_path.is_file(),
        "inject_present": inject_path.is_file(),
        "block_present": block_path.is_file(),
        "hook_ledger_present": hook_ledger.is_file(),
        "effect": (effect_doc or {}).get("effect") if effect_doc else None,
    }
    disp = session / "dispatcher-ledger.jsonl"
    with disp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dispatcher_row, sort_keys=True) + "\n")
    two_signals = bool(dispatcher_row["effect_file_present"] and rc == 0)
    if hook.get("effect") == "inject-context":
        two_signals = two_signals and dispatcher_row["inject_present"]
    if hook.get("effect") == "blocked-call":
        two_signals = two_signals and dispatcher_row["block_present"]
    if hook.get("effect") == "ledger-row":
        two_signals = two_signals and dispatcher_row["hook_ledger_present"]
    dispatcher_row["two_signals"] = two_signals
    dispatcher_row["observable_effect"] = two_signals
    return dispatcher_row


def trigger_event(
    manifest: dict[str, Any], event: str, session: Path
) -> list[dict[str, Any]]:
    payload = dict(EVENT_PAYLOADS.get(event) or {"event": event})
    rows: list[dict[str, Any]] = []
    for hook in manifest.get("hooks") or []:
        if not isinstance(hook, dict):
            continue
        if hook.get("event") != event:
            continue
        if hook.get("enabled") is False:
            skip = {
                "hook_id": hook.get("id"),
                "event": event,
                "enabled": False,
                "skipped": True,
                "effect_file_present": False,
                "observable_effect": False,
                "two_signals": False,
            }
            disp = session / "dispatcher-ledger.jsonl"
            with disp.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(skip, sort_keys=True) + "\n")
            rows.append(skip)
            continue
        rows.append(_run_hook(hook, payload, session))
    return rows


def trigger_all(manifest: dict[str, Any] | None = None, session_name: str = "enabled") -> dict[str, Any]:
    man = manifest if manifest is not None else I.load_registered_manifest()
    session = new_session(session_name)
    events = []
    for hook in man.get("hooks") or []:
        ev = hook.get("event")
        if ev and ev not in events:
            events.append(ev)
    by_hook: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []
    for ev in events:
        rows = trigger_event(man, ev, session)
        all_rows.extend(rows)
        for row in rows:
            hid = str(row.get("hook_id") or "")
            if hid:
                by_hook[hid] = row
    return {
        "session": str(session.relative_to(HERE)),
        "events": events,
        "rows": all_rows,
        "by_hook": by_hook,
        "all_observable": all(
            (by_hook.get(h["id"]) or {}).get("observable_effect") is True
            for h in man.get("hooks") or []
            if h.get("enabled") is not False
        ),
    }


def both_states(target_id: str = "pre-tool") -> dict[str, Any]:
    man = I.load_registered_manifest()
    disabled = copy.deepcopy(man)
    found = False
    sibling_id = None
    for hook in disabled["hooks"]:
        if hook["id"] == target_id:
            hook["enabled"] = False
            found = True
        elif hook.get("event") == "PreToolUse" and hook["id"] != target_id:
            sibling_id = str(hook["id"])
    if not found:
        return {
            "pass": False,
            "disabled_produced_no_effect": False,
            "enabled_produced_effect": False,
            "verbatim_disabled": f"target {target_id} not in manifest",
            "verbatim_enabled": "",
        }
    off = trigger_all(disabled, session_name="disabled")
    on = trigger_all(man, session_name="enabled")
    off_row = off["by_hook"].get(target_id) or {}
    on_row = on["by_hook"].get(target_id) or {}
    off_effect = bool(off_row.get("observable_effect"))
    on_effect = bool(on_row.get("observable_effect"))
    off_file = (HERE / "scratch" / "disabled" / "effects" / f"{target_id}.json").is_file()
    on_file = (HERE / "scratch" / "enabled" / "effects" / f"{target_id}.json").is_file()
    sibling_off = True
    if sibling_id:
        sibling_off = bool((off["by_hook"].get(sibling_id) or {}).get("observable_effect"))
    disabled_ok = (not off_effect) and (not off_file)
    enabled_ok = on_effect and on_file
    verbatim_disabled = (
        f"disabled {target_id}: skipped={off_row.get('skipped')} "
        f"observable={off_effect} effect_file={off_file} "
        f"sibling={sibling_id} sibling_observable={sibling_off}"
    )
    verbatim_enabled = (
        f"enabled {target_id}: observable={on_effect} effect_file={on_file} "
        f"two_signals={on_row.get('two_signals')} effect={on_row.get('effect')}"
    )
    return {
        "target_id": target_id,
        "sibling_id": sibling_id,
        "sibling_still_fired_while_target_disabled": sibling_off,
        "disabled": off,
        "enabled": on,
        "disabled_produced_no_effect": disabled_ok,
        "enabled_produced_effect": enabled_ok,
        "verbatim_disabled": verbatim_disabled,
        "verbatim_enabled": verbatim_enabled,
        "pass": disabled_ok and enabled_ok and sibling_off,
    }


def run_trigger() -> dict[str, Any]:
    ctrl = both_states("pre-tool")
    # Re-use the enabled session from both_states for per-hook rows.
    by_hook = (ctrl.get("enabled") or {}).get("by_hook") or {}
    subjects = []
    for hook in I.load_registered_manifest().get("hooks") or []:
        row = by_hook.get(hook["id"]) or {}
        subjects.append(
            {
                "id": hook["id"],
                "event": hook["event"],
                "effect_kind": hook.get("effect"),
                "registered": True,
                "controlled_trigger": {
                    "ran": True,
                    "observable_effect": bool(row.get("observable_effect")),
                    "two_signals": bool(row.get("two_signals")),
                    "effect": row.get("effect"),
                },
            }
        )
    unknown = trigger_event(
        I.load_registered_manifest(),
        "SessionStart",
        new_session("unknown-event"),
    )
    return {
        "both_states": {
            "pass": ctrl["pass"],
            "disabled_produced_no_effect": ctrl["disabled_produced_no_effect"],
            "enabled_produced_effect": ctrl["enabled_produced_effect"],
            "verbatim_disabled": ctrl["verbatim_disabled"],
            "verbatim_enabled": ctrl["verbatim_enabled"],
            "target_id": ctrl["target_id"],
            "sibling_id": ctrl["sibling_id"],
            "sibling_still_fired_while_target_disabled": ctrl[
                "sibling_still_fired_while_target_disabled"
            ],
        },
        "subjects": subjects,
        "unknown_event_rows": unknown,
        "unknown_event_silent": unknown == [],
        "all_hooks_observable": all(
            s["controlled_trigger"]["observable_effect"] for s in subjects
        ),
        "pass": ctrl["pass"]
        and all(s["controlled_trigger"]["observable_effect"] for s in subjects)
        and unknown == [],
    }
