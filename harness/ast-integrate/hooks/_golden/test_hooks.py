#!/usr/bin/env python
"""Golden acceptance test for the self-calibration hooks.

Proves the wiring is NOT a silent no-op (the user's exact named failure: "reports healthy,
silently does nothing"). Uses NON-SYMMETRIC fixtures (the AXIS-GOTCHA lesson: a symmetric
fixture can pass while the logic is inverted).

Hook root: defaults to the ``hooks/`` tree THIS FILE LIVES IN -- the repo checkout, which
is the source of truth and the only tree CI has. It previously defaulted to
``~/.claude/hooks``, a DEPLOYED copy that does not exist on a CI runner (nor under WSL),
so 4 of the 5 checks failed there for a reason that had nothing to do with the hooks.
Point the same checks at a deployed tree with ``GOLDEN_HOOKS_ROOT=~/.claude/hooks``.

Run:  python test_hooks.py            (exit 0 = all pass)
  or: pytest hooks/_golden/test_hooks.py
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

H = pathlib.Path(
    os.environ.get(
        "GOLDEN_HOOKS_ROOT", str(pathlib.Path(__file__).resolve().parents[1])
    )
)
results = []


def run_hook(script, payload, env=None):
    """Run a hook script and return the CompletedProcess (``.stdout`` + ``.returncode``).

    A MISSING script raises instead of yielding empty stdout. Check 2b below is satisfied
    BY empty output, so an absent -- or crashing -- hook would otherwise be scored PASS:
    green in the broken state, which is the exact failure mode this file exists to catch.
    """
    script = pathlib.Path(script)
    if not script.is_file():
        raise FileNotFoundError("hook script not found: %s" % script)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def check(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


def main():
    """Run every golden check; return 0 if all passed, 1 otherwise."""
    results.clear()

    # 1. recall-first FIRES on a substantial prompt. Isolate HOME so this acceptance
    # probe cannot add a synthetic row to the user's calibrated-silence ledger.
    with tempfile.TemporaryDirectory(prefix="golden-recall-") as isolated_home:
        o = run_hook(
            H / "inquisitiveness" / "prompt-guard.py",
            {
                "prompt": "please reverse engineer the battle cats event scheduler and find exactly where the "
                "date gate is verified inside the binary so events render correctly"
            },
            env={
                "CALIBRATED_SILENCE": "off",
                "HOME": isolated_home,
                "USERPROFILE": isolated_home,
            },
        ).stdout
    check("recall-first injects on a substantial prompt", "Recall-first" in o)

    # 2. fingerprint. Isolate ANTI_DEGEN_ROOT for the same reason HOME is isolated above:
    # the probe must not write synthetic sessions into a real ~/.claude/anti-degen.
    fp = H / "anti-degen" / "fingerprint.py"
    with tempfile.TemporaryDirectory(prefix="golden-degen-") as degen_root:
        fp_env = {"ANTI_DEGEN_ROOT": degen_root}

        # 2a. TRIPS on 3x identical (tool,args,output) RE-tool calls
        sid = "golden-" + os.urandom(3).hex()
        pay = {
            "session_id": sid,
            "tool_name": "mcp__ida-pro-mcp__decompile",
            "tool_input": {"addr": "0x1000"},
            "tool_response": "identical output",
        }
        out3 = ""
        for _ in range(3):
            out3 = run_hook(fp, pay, env=fp_env).stdout
        check(
            "fingerprint trips on 3x identical RE-tool call", "repeated" in out3.lower()
        )

        # 2b. NON-SYMMETRIC: when the OUTPUT changes (progress), it must stay SILENT.
        # The exit code is asserted too -- silence from a CRASHED hook is not silence.
        sid2 = "golden2-" + os.urandom(3).hex()
        last = None
        for i in range(3):
            last = run_hook(
                fp,
                {**pay, "session_id": sid2, "tool_response": "different %d" % i},
                env=fp_env,
            )
    check(
        "fingerprint stays SILENT when output changes (real progress)",
        last is not None and last.returncode == 0 and last.stdout.strip() == "",
    )

    # 3. falsify-check FIRES on a write-op at the falsify cadence
    o = run_hook(
        H / "goal-reinject" / "reinject.py",
        {"tool_name": "Write", "session_id": "golden-fz", "cwd": "."},
        env={
            "GOAL_FALSIFY_INTERVAL": "1",
            "GOAL_REINJECT_COUNTER_ROOT": tempfile.mkdtemp(),
        },
    ).stdout
    check("falsify-check fires on a write-op", "FALSIFY-CHECK" in o)

    # 4. capture-writer MIRRORS a milestone into .beads/knowledge (success-gated, no CI exit needed)
    tmp = tempfile.mkdtemp()
    (pathlib.Path(tmp) / ".beads" / "knowledge").mkdir(parents=True)
    env = {"EVENT_LEDGER_ROOT": os.path.join(tmp, "ledger")}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;sys.path.insert(0,r'%s');import ledger;"
            "ledger.append(r'%s','milestone',text='cracked the date gate at sub_525AB0')"
            % (str(H / "event-ledger"), tmp),
        ],
        env={**os.environ, **env},
    )
    run_hook(H / "event-ledger" / "stop-hook.py", {"cwd": tmp}, env=env)
    dec = pathlib.Path(tmp) / ".beads" / "knowledge" / "decisions.jsonl"
    got = dec.read_text(encoding="utf-8") if dec.exists() else ""
    check(
        "capture-writer mirrors a milestone into .beads/knowledge",
        "cracked the date gate" in got,
    )

    print("\n%d/%d PASS" % (sum(results), len(results)))
    return 0 if all(results) else 1


def test_golden_hooks():
    """pytest entry point -- identical checks, no module-level sys.exit to abort collection."""
    assert main() == 0, (
        "golden hook acceptance checks failed (see the PASS/FAIL lines above)"
    )


if __name__ == "__main__":
    sys.exit(main())
