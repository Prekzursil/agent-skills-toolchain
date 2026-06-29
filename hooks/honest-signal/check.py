#!/usr/bin/env python3
r"""honest-signal/check.py — Stop hook. Certainty-band vs evidence mismatch lint.

Fires when the final assistant message asserts a load-bearing TECHNICAL claim with
an explicit CERTAINTY MARKER ("definitely", "guaranteed", "100%", "confirmed",
"this WILL work", "I'm certain") YET the agent ran ZERO verifying tools this turn —
i.e. a confident factual assertion produced from memory/inference with nothing to
back it. Injects: "you asserted X as VERIFIED but ran no verifying tool this turn —
mark it INFERRED/GUESSED or verify."

THE GAP IT FILLS (STRICTLY DISJOINT FROM B1 — never double-nags):
  * truth-verify/check.py fires on RE ANCHORS (hex / sub_XXXX / offset) regardless
    of certainty wording. -> honest-signal DEFERS any occurrence whose window holds
    an RE anchor.
  * claim-guard/claim-check.py fires on tests/build/lint/coverage/ci/"fixed" claims
    checked against the Bash ledger. -> honest-signal DEFERS any occurrence whose
    window holds one of those category phrases.
  * What's LEFT (the gap neither covers): confident certainty about a general
    TECHNICAL fact — "the timeout is definitely 30s", "this is absolutely
    thread-safe", "the API will definitely return JSON" — asserted with no tool run.
    This is the verbalized-confidence-band > actual-evidence mismatch (Huang ICLR'24:
    intrinsic self-confidence is unreliable; only an external check counts).

TRIGGER CONDITION (high signal, low false-positive by design):
  - ZERO substantive tool_use this turn (TodoWrite excluded). If the agent ran ANY
    real tool, we give benefit of the doubt and stay silent (the specific-mismatch
    hooks above still cover their domains).
  - A certainty marker present, NOT inside a hedge window, NOT in a deferred domain,
    AND co-located (±120 chars) with a technical indicator (a `code span`, a file
    path, or a technical noun).

HOOK LAW: inject-only (exit 0 + additionalContext); not a dangerous op -> no exit-2.
FAIL-OPEN (try/except -> exit 0). Anti-loop via stop_hook_active. Stdlib-only.

Opt-out: HONEST_SIGNAL=off in env, or a hooks/honest-signal/.disabled file.

settings.json (Stop, no matcher):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/honest-signal/check.py",
   "timeout":10,"statusMessage":"Honest-signal (certainty vs evidence lint)"}
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"

# Tools that do NOT count as verification activity.
_NON_VERIFYING = {"TodoWrite", "TodoRead"}

_CERTAINTY = re.compile(
    r"(?:"
    r"\bdefinitely\b|\bcertainly\b|\babsolutely\b|\bundoubtedly\b|\bunquestionably\b"
    r"|\bguarantee(?:d|s)?\b|\b100\s*%|\bwithout\s+(?:a\s+)?doubt\b|\bno\s+doubt\b"
    r"|\bfor\s+sure\b|\bi(?:'m|\s+am)\s+(?:certain|sure|positive)\b|\brest\s+assured\b"
    r"|\bconfirmed\b|\btrust\s+me\b|\bi\s+can\s+confirm\b"
    r"|\b(?:this|it|that|the\s+\w+)\s+will\s+(?:work|pass|succeed|fix|handle|solve|return)\b"
    r"|\bis\s+(?:definitely|certainly|guaranteed|absolutely)\b"
    r")",
    re.IGNORECASE,
)

_HEDGE = re.compile(
    r"\b(?:might|maybe|perhaps|possibly|probably|likely|i\s+think|i\s+believe|seems?|"
    r"appears?|not\s+sure|unsure|unverified|"
    r"should\s+(?:be|work|pass)|tentative|assume|assuming|guess(?:ing)?|in\s+theory|"
    r"i\s+haven'?t\s+(?:verified|checked|tested)|untested|presumably|roughly|approximately)\b"
    # "need to verify/check" is a hedge — but NOT "no need to check" (that is over-confidence).
    r"|(?<!no\s)\bneed\s+to\s+(?:verify|check|confirm|test)\b",
    re.IGNORECASE,
)

# Technical indicators — the certainty must attach to one of these to be load-bearing.
_TECH = re.compile(
    r"(?:`[^`]+`"                                   # inline code span
    r"|[\w./\\-]+\.(?:py|ts|tsx|js|jsx|mjs|go|rs|java|rb|c|cc|cpp|h|hpp|cs|kt|swift|"
    r"json|ya?ml|toml|ini|cfg|sh|ps1|sql|html|css)\b"   # a file path
    r"|\b(?:offset|address|value|function|method|class|field|config|setting|flag|"
    r"parameter|argument|variable|constant|endpoint|route|port|timeout|version|hash|"
    r"token|key|env|environment|schema|type|behaviou?r|output|result|payload|response|"
    r"request|query|module|import|dependency|build|deploy|thread[- ]safe|idempotent|"
    r"race\s+condition|root\s+cause|approach|implementation|algorithm|encoding|format)\b"
    r")",
    re.IGNORECASE,
)

# DEFER to truth-verify: RE anchors.
_RE_ANCHOR = re.compile(
    r"(?:\bsub_[0-9A-Fa-f]{4,}\b|\b0x[0-9A-Fa-f]{5,}\b"
    r"|\boffset\s+(?:0x[0-9A-Fa-f]+|\d{3,})\b)",
    re.IGNORECASE,
)

# DEFER to claim-guard: generous keyword-presence test on its domain, so that ANY
# test/build/lint/coverage/ci/"fixed" claim near the certainty is left to claim-guard
# (erring toward NOT double-nagging — over-deferral only quiets honest-signal, never
# duplicates it).
_CLAIM_GUARD = re.compile(
    r"\b(?:tests?|test\s+suite|builds?|building|compil\w*|lint\w*|coverage|"
    r"ci|gates?|pipeline|mergeable|fixed|regression)\b"
    r"|all\s+green|ready\s+to\s+merge|no\s+(?:lint\s+)?errors?",
    re.IGNORECASE,
)


def _iter_events(transcript_path: str):
    p = Path(transcript_path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _is_human(ev: dict) -> bool:
    msg = ev.get("message") or {}
    role = msg.get("role") or ev.get("role") or ev.get("type")
    if role != "user":
        return False
    content = msg.get("content")
    if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return False  # a tool_result is not a fresh human turn
    return True


def _assistant_text(ev: dict):
    msg = ev.get("message") or {}
    role = msg.get("role") or ev.get("role")
    if not ((ev.get("type") == "assistant" and msg.get("role") == "assistant") or role == "assistant"):
        return None
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    parts = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text") or ""))
    elif isinstance(content, str):
        parts.append(content)
    return " ".join(parts) if parts else None


def _tool_names(ev: dict):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            yield str(b.get("name") or "")


def analyze(transcript_path: str):
    """Return (final_text, n_verifying_tools_this_turn)."""
    events = list(_iter_events(transcript_path))
    last_human = -1
    for i, ev in enumerate(events):
        if _is_human(ev):
            last_human = i
    final_text = None
    tools = 0
    for i, ev in enumerate(events):
        txt = _assistant_text(ev)
        if txt is not None:
            final_text = txt
        if i > last_human:
            for name in _tool_names(ev):
                if name and name not in _NON_VERIFYING:
                    tools += 1
    return final_text, tools


def find_offenders(text: str) -> list[str]:
    """Return short snippets of certainty claims lacking verification & not deferred."""
    offenders = []
    for m in _CERTAINTY.finditer(text):
        lo, hi = max(0, m.start() - 120), min(len(text), m.end() + 120)
        window = text[lo:hi]
        if _HEDGE.search(window):
            continue                       # hedged -> honest already
        if _RE_ANCHOR.search(window):
            continue                       # defer to truth-verify
        if _CLAIM_GUARD.search(window):
            continue                       # defer to claim-guard
        if not _TECH.search(window):
            continue                       # not a load-bearing technical claim
        snippet = re.sub(r"\s+", " ", text[max(0, m.start() - 40):m.end() + 40]).strip()
        offenders.append(snippet)
        if len(offenders) >= 3:
            break
    return offenders


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("HONEST_SIGNAL", "").lower() in ("off", "0", "false"):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("stop_hook_active"):
            return 0  # anti-loop
        tp = str(data.get("transcript_path") or "")
        if not tp:
            return 0
        final_text, tools = analyze(tp)
        if not final_text:
            return 0
        if tools > 0:
            return 0  # the agent DID verify-by-doing something this turn -> trust it
        offenders = find_offenders(final_text)
        if not offenders:
            return 0
        shown = "; ".join(f'"...{o}..."' for o in offenders[:2])
        msg = (
            "[honest-signal] You asserted a technical claim as CERTAIN "
            f"({shown}) but ran NO verifying tool this turn. Self-confidence is not "
            "evidence — either mark it INFERRED/GUESSED (hedge it), or actually verify "
            "it (read the file / run the command / call the tool) before stating it as "
            "fact. (RE anchors -> truth-verify; test/build/coverage claims -> claim-guard.)"
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop", "additionalContext": msg}}))
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
