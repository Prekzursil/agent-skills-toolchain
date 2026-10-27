#!/usr/bin/env python3
r"""chaos_todo_surfacer.py - CHAOS / GameDay self-test for the todo-surfacer inject hook.

Fault-injects against the REAL hook process (its own stdin, its own exit code) to
PROVE three properties - the discipline is not "installed" until all three hold:

  1. FIRES   : a payload matching the trigger -> emits hookSpecificOutput.
  2. SILENT  : a non-matching payload         -> emits nothing (exit 0).
  3. FAILOPEN: garbage stdin / opt-out         -> exit 0, no traceback, no output.

The GameDay lesson: an untested safety net fails exactly when you need it.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "hook.py"
FIX = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
_FAILS: list[str] = []
_TMP: list[str] = []


@atexit.register
def _cleanup_tmp() -> None:
    for p in _TMP:
        try:
            path = Path(p)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        except Exception:
            pass


def _set(d: dict, path: str, val) -> None:
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val


def _payload(value: str) -> dict:
    kind = FIX["kind"]
    p = dict(FIX.get("extra_payload") or {})
    p.setdefault("session_id", "chaos")
    if kind == "response":
        tf = tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tf.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": value}],
                    },
                }
            )
            + "\n"
        )
        tf.close()
        _TMP.append(tf.name)
        p["transcript_path"] = tf.name
    elif kind == "prompt":
        p["prompt"] = value
    elif kind == "command":
        p.setdefault("tool_input", {})["command"] = value
    elif kind == "tool":
        p["tool_name"] = value
    elif kind == "field":
        _set(p, FIX["field"], value)
    return p


def _run(stdin_text: str, env_extra: dict | None = None):
    env = dict(os.environ)
    env.pop("FORGE_TODO_SURFACER_OFF", None)
    _sr = tempfile.mkdtemp(prefix="forge-state-chaos-")
    _TMP.append(_sr)
    env["FORGE_STATE_ROOT"] = _sr
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    res = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        cwd=str(HERE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    return res.returncode, (res.stdout or ""), (res.stderr or "")


def _emitted(stdout: str):
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        hso = obj.get("hookSpecificOutput") if isinstance(obj, dict) else None
        if isinstance(hso, dict) and hso.get("additionalContext"):
            return str(hso["additionalContext"])
    return None


def check(label: str, ok: bool, detail: str = "") -> None:
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}"
        + (f" - {detail}" if detail and not ok else "")
    )
    if not ok:
        _FAILS.append(f"{label}: {detail}")


def main() -> int:
    print(f"CHAOS self-test: {FIX['name']} (inject / {FIX['event']})")

    # 1. FIRES
    rc, out, err = _run(json.dumps(_payload(FIX["fire_value"])))
    msg = _emitted(out)
    check(
        "fires on trigger",
        rc == 0 and bool(msg),
        f"rc={rc} emitted={msg!r} err={err.strip()!r}",
    )

    # 2. SILENT
    if FIX["has_silent"]:
        rc, out, err = _run(json.dumps(_payload(FIX["silent_value"])))
        check(
            "silent on non-trigger",
            rc == 0 and _emitted(out) is None,
            f"rc={rc} emitted={_emitted(out)!r}",
        )

    # 3. FAIL-OPEN on garbage
    for i, junk in enumerate(FIX["garbage"]):
        rc, out, err = _run(junk)
        check(
            f"fail-open on garbage[{i}]",
            rc == 0 and "Traceback" not in err,
            f"rc={rc} err={err.strip()!r}",
        )

    # 4. opt-out is honoured (env disables -> silent even on the fire payload)
    rc, out, err = _run(
        json.dumps(_payload(FIX["fire_value"])),
        env_extra={"FORGE_TODO_SURFACER_OFF": "1"},
    )
    check(
        "opt-out env silences it",
        rc == 0 and _emitted(out) is None,
        f"rc={rc} emitted={_emitted(out)!r}",
    )

    if _FAILS:
        print(f"\nCHAOS-FAIL: {len(_FAILS)} property/properties unproven")
        return 1
    print("\nCHAOS-PASS: hook fires on trigger, stays silent otherwise, and fails open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
