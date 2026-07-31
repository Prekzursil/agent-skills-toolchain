#!/usr/bin/env python3
"""Direct-invocation tests for honest-signal/check.py.

Builds throwaway JSONL transcripts and pipes Stop-hook stdin to prove the hook
FIRES on certain-but-unverified technical claims and stays SILENT when hedged,
when a CLAIM-RELEVANT tool ran, or when the claim belongs to truth-verify/claim-guard.

Two entry points, one scenario table (`collect_cases`):
  * `pytest hooks/honest-signal/` — `test_honest_signal_scenarios` asserts it. This is
    the one CI executes, via the `hooks/` regression-harness step in quality.yml. The
    file previously exposed only `main()`, so pytest collected ZERO tests from it and
    every case below was dead weight in CI (measured: "no tests collected").
  * `python test_honest_signal.py` — prints a per-case PASS/FAIL table + samples.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "check.py")


def _human(text):
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def _assistant_text(text):
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _assistant_tool(name, inp=None, tool_id="tu1"):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_id, "name": name, "input": inp or {}}
            ],
        },
    }


def _tool_result(content, tool_id="tu1"):
    """A tool_result turn. Carries role=user but is NOT a fresh human turn."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content}
            ],
        },
    }


def make_transcript(events) -> str:
    d = Path(tempfile.gettempdir()) / f"hs-test-{uuid.uuid4().hex}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "transcript.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return str(p)


def run(events) -> str:
    tp = make_transcript(events)
    payload = {"session_id": "hs-" + uuid.uuid4().hex[:8], "transcript_path": tp}
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert p.returncode == 0, f"must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def collect_cases():
    """Return [(name, fired, expected, raw_output)] for every scenario."""
    cases = []

    # 1. Certain technical claim + NO tool this turn -> FIRES
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_text(
                "The connection `timeout` is definitely 30 seconds — no need to check."
            ),
        ]
    )
    cases.append(("certain technical claim, no tool -> fires", fired(out), True, out))

    # 2. Same claim but HEDGED -> SILENT
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_text(
                "The `timeout` is definitely 30 seconds, but I haven't verified it — need to check."
            ),
        ]
    )
    cases.append(("hedged certainty -> silent", fired(out), False, out))

    # 3. Same claim but a CLAIM-RELEVANT tool ran this turn -> SILENT.
    #    The anchor `timeout` is in the tool INPUT. This is the mutation guard on the
    #    D-m04 fix: deleting the suppression outright (instead of scoping it to
    #    claim-relevant evidence) turns this case red.
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_tool("Bash", {"command": "grep timeout config.py"}),
            _assistant_text("The `timeout` is definitely 30 seconds."),
        ]
    )
    cases.append(
        ("certain claim, relevant tool INPUT -> silent", fired(out), False, out)
    )

    # 4. Certain claim about an RE anchor -> DEFER to truth-verify -> SILENT
    out = run(
        [
            _human("where is it?"),
            _assistant_text(
                "The function is definitely at offset 0x8A3350 in the binary."
            ),
        ]
    )
    cases.append(("certain RE anchor -> deferred (silent)", fired(out), False, out))

    # 5. Certain claim about tests -> DEFER to claim-guard -> SILENT
    out = run(
        [
            _human("done?"),
            _assistant_text("Yes, the tests definitely pass and the build is green."),
        ]
    )
    cases.append(
        ("certain test/build claim -> deferred (silent)", fired(out), False, out)
    )

    # 6. Confident but NON-technical chit-chat -> SILENT (no technical indicator)
    out = run(
        [
            _human("can you help?"),
            _assistant_text(
                "Absolutely, I will definitely help you with that. For sure."
            ),
        ]
    )
    cases.append(("non-technical certainty -> silent", fired(out), False, out))

    # 7. "I can confirm" a config value with no tool -> FIRES
    out = run(
        [
            _human("is debug on?"),
            _assistant_text(
                "I can confirm the `DEBUG` config flag is set to true in production."
            ),
        ]
    )
    cases.append(("'I can confirm' config, no tool -> fires", fired(out), True, out))

    # 8. Only TodoWrite ran (non-verifying) + certain claim -> FIRES
    out = run(
        [
            _human("status?"),
            _assistant_tool("TodoWrite", {"todos": []}),
            _assistant_text("The `payload` schema is guaranteed to be valid JSON."),
        ]
    )
    cases.append(("only TodoWrite + certain claim -> fires", fired(out), True, out))

    # 9. REGRESSION D-m04: a substantive but UNRELATED tool ran -> still FIRES.
    #    Before the fix, check.py returned at `if tools > 0` before find_offenders, so
    #    one `Read README.md` silenced an unsupported claim about `timeout`. Measured
    #    on 27fb388 pre-fix: fired=False. The claim's anchor ("timeout") appears in
    #    neither the tool input nor its result, so nothing here is evidence for it.
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_tool("Read", {"file_path": "README.md"}),
            _tool_result("# Project readme\nSome prose about the project."),
            _assistant_text("The `timeout` is definitely 30 seconds."),
        ]
    )
    cases.append(("unrelated tool + certain claim -> fires", fired(out), True, out))

    # 10. Counterpart to 9: the anchor is in the tool RESULT, not the input -> SILENT.
    #     Reading the right file IS claim-relevant evidence even though the input is
    #     only a path. Keeps the fix from degenerating into "fire whenever tools ran".
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_tool("Read", {"file_path": "settings.py"}),
            _tool_result("retries = 3\ntimeout = 30  # seconds\n"),
            _assistant_text("The `timeout` is definitely 30 seconds."),
        ]
    )
    cases.append(("relevant tool RESULT -> silent", fired(out), False, out))

    # 11. A TodoWrite RESULT must not launder itself into evidence: it is dropped by
    #     tool_use_id, so a matching anchor inside it cannot suppress. Still FIRES.
    out = run(
        [
            _human("what's the timeout?"),
            _assistant_tool("TodoWrite", {"todos": []}, tool_id="td1"),
            _tool_result("timeout todo recorded", tool_id="td1"),
            _assistant_text("The `timeout` is definitely 30 seconds."),
        ]
    )
    cases.append(("TodoWrite result is not evidence -> fires", fired(out), True, out))

    return cases


def test_honest_signal_scenarios():
    """pytest entry point — every scenario in collect_cases() must match expectation."""
    failures = [
        f"{name}: fired={got} expected={want} output={out!r}"
        for name, got, want, out in collect_cases()
        if got != want
    ]
    assert not failures, "\n".join(failures)


def main() -> int:
    cases = collect_cases()
    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")
    print("\nFIRED-sample (case 1):")
    print(
        run(
            [
                _human("q"),
                _assistant_text("The `timeout` value is definitely 30 seconds."),
            ]
        )
    )
    print(
        "SILENT-sample (case 2): "
        + repr(
            run(
                [
                    _human("q"),
                    _assistant_text(
                        "The `timeout` might be 30 seconds — I need to check."
                    ),
                ]
            )
        )
    )
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
