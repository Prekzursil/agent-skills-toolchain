#!/usr/bin/env python3
"""Direct-invocation tests for honest-signal/check.py.

Builds throwaway JSONL transcripts and pipes Stop-hook stdin to prove the hook
FIRES on certain-but-unverified technical claims and stays SILENT when hedged,
when a verifying tool ran, or when the claim belongs to truth-verify/claim-guard.

Run:  python test_honest_signal.py
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
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def _assistant_text(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _assistant_tool(name, inp=None):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": inp or {}}]}}


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
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, f"must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def main() -> int:
    cases = []

    # 1. Certain technical claim + NO tool this turn -> FIRES
    out = run([_human("what's the timeout?"),
               _assistant_text("The connection `timeout` is definitely 30 seconds — no need to check.")])
    cases.append(("certain technical claim, no tool -> fires", fired(out), True, out))

    # 2. Same claim but HEDGED -> SILENT
    out = run([_human("what's the timeout?"),
               _assistant_text("The `timeout` is definitely 30 seconds, but I haven't verified it — need to check.")])
    cases.append(("hedged certainty -> silent", fired(out), False, out))

    # 3. Same claim but a verifying TOOL ran this turn -> SILENT
    out = run([_human("what's the timeout?"),
               _assistant_tool("Bash", {"command": "grep timeout config.py"}),
               _assistant_text("The `timeout` is definitely 30 seconds.")])
    cases.append(("certain claim but a tool ran -> silent", fired(out), False, out))

    # 4. Certain claim about an RE anchor -> DEFER to truth-verify -> SILENT
    out = run([_human("where is it?"),
               _assistant_text("The function is definitely at offset 0x8A3350 in the binary.")])
    cases.append(("certain RE anchor -> deferred (silent)", fired(out), False, out))

    # 5. Certain claim about tests -> DEFER to claim-guard -> SILENT
    out = run([_human("done?"),
               _assistant_text("Yes, the tests definitely pass and the build is green.")])
    cases.append(("certain test/build claim -> deferred (silent)", fired(out), False, out))

    # 6. Confident but NON-technical chit-chat -> SILENT (no technical indicator)
    out = run([_human("can you help?"),
               _assistant_text("Absolutely, I will definitely help you with that. For sure.")])
    cases.append(("non-technical certainty -> silent", fired(out), False, out))

    # 7. "I can confirm" a config value with no tool -> FIRES
    out = run([_human("is debug on?"),
               _assistant_text("I can confirm the `DEBUG` config flag is set to true in production.")])
    cases.append(("'I can confirm' config, no tool -> fires", fired(out), True, out))

    # 8. Only TodoWrite ran (non-verifying) + certain claim -> FIRES
    out = run([_human("status?"),
               _assistant_tool("TodoWrite", {"todos": []}),
               _assistant_text("The `payload` schema is guaranteed to be valid JSON.")])
    cases.append(("only TodoWrite + certain claim -> fires", fired(out), True, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")
    print("\nFIRED-sample (case 1):")
    print(run([_human("q"), _assistant_text("The `timeout` value is definitely 30 seconds.")]))
    print("SILENT-sample (case 2): " + repr(run([_human("q"),
          _assistant_text("The `timeout` might be 30 seconds — I need to check.")])))
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
