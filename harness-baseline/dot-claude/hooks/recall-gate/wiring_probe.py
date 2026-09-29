#!/usr/bin/env python
"""BOTH-STATES wiring probe for hooks/recall-gate.

Answers the question the unit tests CANNOT answer: is the gate actually REACHABLE from
``~/.claude/settings.json``, and does the command that settings.json names behave correctly
in BOTH states?

It deliberately does not import gate.py. It reads the command string out of settings.json and
runs THAT, the way the harness does -- so an unwired hook, a typo'd path, a `python` that is
not on PATH, or a gate that starts blocking all fail here.

Three assertions, all fail-closed:

  1. WIRING     -- some ``hooks.UserPromptSubmit`` command mentions ``recall-gate``.
  2. FIRES      -- an absence-claim prompt makes that command print a
                   ``hookSpecificOutput.additionalContext`` payload.
  3. SILENT     -- a benign prompt makes it print NOTHING.

Plus a policy assertion: exit code is 0 in both states (inject-only; an ``exit 2`` from a
UserPromptSubmit hook would block the prompt, which this gate must never do).

Exit 0 = all pass. Exit 1 = a state is wrong, with the reason named.
Superseding: this replaces README step 2's pointer to
``~/.claude/harness-restore-20260806/_recall_bothstates.py``, which does not exist on disk.

Usage:  python wiring_probe.py [path-to-settings.json]
"""

import json
import subprocess
import sys
from pathlib import Path

DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
NEEDLE = "recall-gate"

# An absence claim naming an artifact that DOES exist in the indexed tree -> must FIND prior art.
# The noun must be a real indexed file STEM, because that is precisely the case the gate exists
# for: a prompt asserting absence of something already on disk. (A first draft of this probe said
# "there is no recall gate" -- two words, no matching stem -- and the gate correctly returned
# CLEAN/no-prior-art. That was a bad instrument, not a broken gate.)
PROMPT_FIRES = (
    "There is no observe hook for the semantic router, it does not exist, "
    "I need to build observe from scratch."
)
# No absence claim, no build intent, no indexed noun -> must stay SILENT.
PROMPT_SILENT = (
    "Please summarise tomorrow's weather forecast for Bucharest and tell me "
    "whether I should take an umbrella with me to the office."
)


def _commands(settings_path: Path) -> list[str]:
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    out: list[str] = []
    for group in (data.get("hooks") or {}).get("UserPromptSubmit") or []:
        for entry in (group or {}).get("hooks") or []:
            cmd = (entry or {}).get("command")
            if isinstance(cmd, str):
                out.append(cmd)
    return out


def _run(cmd: str, prompt: str) -> tuple[int, str, str]:
    payload = json.dumps(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "wiring-probe",
            "prompt": prompt,
        }
    )
    proc = subprocess.run(
        cmd,
        shell=True,
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _injected(stdout: str) -> str | None:
    """Return the injected additionalContext, or None if this run injected nothing."""
    if not stdout:
        return None
    try:
        obj = json.loads(stdout)
    except Exception:  # noqa: BLE001
        return None
    ctx = ((obj or {}).get("hookSpecificOutput") or {}).get("additionalContext")
    return ctx if isinstance(ctx, str) and ctx.strip() else None


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    settings = Path(argv[0]) if argv else DEFAULT_SETTINGS

    if not settings.exists():
        print(f"FAILED:recall-gate-wiring settings.json not found at {settings}")
        return 1
    try:
        cmds = _commands(settings)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:recall-gate-wiring settings.json unparseable ({type(exc).__name__})")
        return 1

    if not cmds:  # fail closed on an empty walk
        print("FAILED:recall-gate-wiring no UserPromptSubmit commands found at all")
        return 1

    wired = [c for c in cmds if NEEDLE in c]
    print(f"UserPromptSubmit commands: {len(cmds)}; mentioning '{NEEDLE}': {len(wired)}")
    if not wired:
        print("FAILED:recall-gate-wiring WIRING=ABSENT -- the gate is not reachable from settings.json")
        return 1
    cmd = wired[0]
    print(f"WIRED command: {cmd}")

    bad = []

    rc_a, out_a, err_a = _run(cmd, PROMPT_FIRES)
    ctx_a = _injected(out_a)
    if rc_a != 0:
        bad.append(f"fire-state exit={rc_a} (must be 0; inject-only)")
    if ctx_a is None:
        bad.append("fire-state injected NOTHING (expected a PRIOR ART digest)")
        if err_a:
            print(f"  fire-state stderr: {err_a[:400]}")
    else:
        first = ctx_a.strip().splitlines()[0][:160]
        print(f"STATE 1 FIRES   exit={rc_a} injected={len(ctx_a)}B first-line={first!r}")
        # The digest is only useful if the files it names actually EXIST. A "non-empty string"
        # assertion would pass on fabricated paths, so resolve every ~/ path it cites.
        cited = [
            tok.strip(" -`,;")
            for line in ctx_a.splitlines()
            for tok in line.split()
            if tok.startswith("~/")
        ]
        missing = [c for c in cited if not (Path.home() / c[2:]).exists()]
        if not cited:
            bad.append("fire-state digest cited NO ~/ path (nothing to verify)")
        elif missing:
            bad.append(f"fire-state digest cited {len(missing)} path(s) that do not exist: {missing[:3]}")
        else:
            print(f"STATE 1 PATHS   {len(cited)} cited path(s), all resolve on disk")

    rc_b, out_b, err_b = _run(cmd, PROMPT_SILENT)
    ctx_b = _injected(out_b)
    if rc_b != 0:
        bad.append(f"silent-state exit={rc_b} (must be 0; inject-only)")
    if ctx_b is not None:
        bad.append(f"silent-state INJECTED {len(ctx_b)}B on a benign prompt (false positive)")
    else:
        print(f"STATE 2 SILENT  exit={rc_b} stdout={len(out_b)}B (expected 0B)")

    if bad:
        for b in bad:
            print(f"  - {b}")
        print(f"FAILED:recall-gate-wiring {len(bad)} assertion(s) failed")
        return 1
    print("SUCCESS:recall-gate-wiring wired + fires on absence claim + silent on benign prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
