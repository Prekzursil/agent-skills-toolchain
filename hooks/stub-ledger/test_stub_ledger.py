#!/usr/bin/env python3
"""Direct-invocation tests for stub-ledger record.py + report.py.

Proves: a Write with a TODO is RECORDED; a Stop with no completion claim SURFACES it;
a completion claim DEFERS to dark-surface (silent); a resolved stub drops out.

Run:  python test_stub_ledger.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

DIR = Path(__file__).resolve().parent
RECORD = str(DIR / "record.py")
REPORT = str(DIR / "report.py")


def run(hook, payload, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    p = subprocess.run(
        [sys.executable, hook],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert p.returncode == 0, f"{hook} must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def make_transcript(final_text: str) -> str:
    d = Path(tempfile.gettempdir()) / f"sl-tx-{uuid.uuid4().hex}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "t.jsonl"
    p.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "go"}],
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": final_text}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(p)


def find_stubs_precision_cases():
    """Unit cases for stubscan.find_stubs — the pragma exemption + reach-forward fix."""
    sys.path.insert(0, str(DIR))
    import stubscan  # noqa: PLC0415

    def flagged(text: str, needle: str) -> bool:
        return any(needle in sn for _, _, sn in stubscan.find_stubs(text))

    proto = (
        "class B(Protocol):\n"
        "    def analyze(self, p: str) -> int:\n"
        '        """doc."""\n'
        "        ...  # pragma: no cover - Protocol stub\n"
        "    def release(self) -> None:\n"
        "        ...  # pragma: no cover - Protocol stub\n"
    )
    # A complete multi-line-signature fn must NOT reach forward to a later stub body.
    reach = (
        "def merge(\n"
        "    a: int,\n"
        "    b: int,\n"
        ") -> tuple[int, ...]:\n"
        '    """doc."""\n'
        "    if a <= 0:\n"
        '        raise ValueError("x")\n'
        "    return (a, b)\n"
        "\n"
        "class B(Protocol):\n"
        "    def analyze(self) -> int:\n"
        "        ...  # pragma: no cover - Protocol stub\n"
    )
    out = [
        (
            "Protocol ...-body w/ pragma -> not flagged",
            flagged(proto, "analyze") or flagged(proto, "release"),
            False,
        ),
        (
            "complete multi-line fn not reach-flagged",
            flagged(reach, "def merge("),
            False,
        ),
        (
            "real pass-only body still flagged",
            flagged("def todo_impl(x):\n    pass\n", "todo_impl"),
            True,
        ),
        (
            "real ...-only body (no pragma) still flagged",
            flagged("def not_done(x):\n    ...\n", "not_done"),
            True,
        ),
        ("bare TODO still flags", flagged("x = 1  # TODO: fix\n", "TODO"), True),
    ]
    return [(n, got, want, "") for (n, got, want) in out]


def main() -> int:
    cases = list(find_stubs_precision_cases())
    workdir = Path(tempfile.gettempdir()) / f"sl-work-{uuid.uuid4().hex}"
    workdir.mkdir(parents=True, exist_ok=True)
    ledroot = str(workdir / "ledger")
    env = {"STUB_LEDGER_ROOT": ledroot}

    # Write a real source file containing a TODO + a pass-only body.
    src = workdir / "feature.py"
    src.write_text(
        "def handler(req):\n    pass  # TODO: implement the handler later\n",
        encoding="utf-8",
    )
    sid = "sl-1"

    # 1. record.py on a Write -> ledger entry created
    run(
        RECORD,
        {
            "session_id": sid,
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(src),
                "content": src.read_text(encoding="utf-8"),
            },
        },
        env,
    )
    ledger = Path(ledroot) / f"{sid}.ndjson"
    recorded = ledger.exists() and ledger.read_text(encoding="utf-8").strip() != ""
    cases.append(
        (
            "Write with TODO -> recorded to ndjson",
            recorded,
            True,
            ledger.read_text(encoding="utf-8")[:200] if ledger.exists() else "<none>",
        )
    )

    # 2. Stop, NO completion claim -> surfaced
    out = run(
        REPORT,
        {
            "session_id": sid,
            "transcript_path": make_transcript(
                "I added a handler skeleton; moving on to the next file."
            ),
        },
        env,
    )
    cases.append(("Stop, no completion claim -> surfaced", fired(out), True, out))

    # 3. Stop, WITH completion claim -> deferred to dark-surface (silent)
    out = run(
        REPORT,
        {
            "session_id": sid,
            "transcript_path": make_transcript(
                "The handler is now fully implemented and wired up."
            ),
        },
        env,
    )
    cases.append(
        ("Stop, completion claim -> deferred (silent)", fired(out), False, out)
    )

    # 4. Resolve the stub in the file -> report drops it (silent)
    src.write_text("def handler(req):\n    return process(req)\n", encoding="utf-8")
    out = run(
        REPORT, {"session_id": sid, "transcript_path": make_transcript("next.")}, env
    )
    cases.append(("resolved stub -> not surfaced (silent)", fired(out), False, out))

    # 5. STUB_LEDGER=off -> record + report both silent/no-op
    sid2 = "sl-2"
    run(
        RECORD,
        {
            "session_id": sid2,
            "tool_name": "Write",
            "tool_input": {"file_path": str(src), "content": "# FIXME: broken\n"},
        },
        {"STUB_LEDGER": "off", **env},
    )
    led2 = Path(ledroot) / f"{sid2}.ndjson"
    cases.append(
        (
            "STUB_LEDGER=off -> no ledger write",
            not led2.exists(),
            True,
            str(led2.exists()),
        )
    )

    # 6. STUB_LEDGER_ALWAYS=1 surfaces even WITH a completion claim
    out = run(
        REPORT,
        {
            "session_id": sid,
            "transcript_path": make_transcript("fully implemented and wired up."),
        },
        {"STUB_LEDGER_ALWAYS": "1", **env},
    )
    # (sid's only stub was resolved in step 4, so re-add one for this case)
    sid3 = "sl-3"
    run(
        RECORD,
        {
            "session_id": sid3,
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(workdir / "x.py"),
                "content": "x = 1  # TODO later\n",
            },
        },
        env,
    )
    (workdir / "x.py").write_text("x = 1  # TODO later\n", encoding="utf-8")
    out = run(
        REPORT,
        {
            "session_id": sid3,
            "transcript_path": make_transcript("feature is complete."),
        },
        {"STUB_LEDGER_ALWAYS": "1", **env},
    )
    cases.append(("STUB_LEDGER_ALWAYS=1 surfaces despite claim", fired(out), True, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: got={got} expected={want}")
        if got != want:
            print(f"         detail={out!r}")
    print("\nFIRED-sample (case 2):")
    src.write_text(
        "def handler(req):\n    pass  # TODO: implement later\n", encoding="utf-8"
    )
    run(
        RECORD,
        {
            "session_id": "demo",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(src),
                "content": src.read_text(encoding="utf-8"),
            },
        },
        env,
    )
    print(
        run(
            REPORT,
            {"session_id": "demo", "transcript_path": make_transcript("moving on.")},
            env,
        )
    )
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
