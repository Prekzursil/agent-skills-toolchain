#!/usr/bin/env python3
r"""TRUTH-VERIFY (Stop hook) — RE/factual ANCHOR verification nudge.

Catches the specific honesty gap the existing claim-guard does NOT cover: a
load-bearing reverse-engineering / low-level ANCHOR (a hex address, a `sub_XXXX`
offset, "located at 0x...", "offset 4536") asserted as FACT in the final answer
when NO verifying tool was used this turn — i.e. a value recalled from memory /
fabricated rather than freshly derived. This is the user's documented failure mode
(grinding on a wrong-but-consistent anchor; the fresh-verify skill exists for it).

NON-DUPLICATIVE BY DESIGN: tests/build/lint/coverage/"fixed"/"done"/"gates green"
are already handled by hooks/claim-guard/claim-check.py against the Bash ledger.
This hook deliberately stays OUT of that space and fires ONLY on RE anchors, so the
two never double-nag.

Verification = any RE/inspection tool used this turn: ida/ghidra/binary-ninja/frida/
cheatengine/radare2 MCP calls, a Read of a binary/offsets-like file, or a Bash with
objdump/readelf/nm/gdb/rabin2/hexdump. If such a tool ran, we stay silent.

Inject-only (exit 0, additionalContext) — an unverified claim is not dangerous/
irreversible (AGENTS.md s6), so no exit-2 block; a BLOCK stub is left disabled for
the most egregious case. FAIL-OPEN. Opt-out: TRUTH_VERIFY=off or a .disabled file.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MODE = os.environ.get("TRUTH_VERIFY_MODE", "warn").lower()

# Strong RE anchors — real addresses/offsets, not small constants like 0x1F.
_ANCHOR = re.compile(
    r"(?:"
    r"\bsub_[0-9A-Fa-f]{4,}\b"                                  # sub_8A3350
    r"|\b0x[0-9A-Fa-f]{5,}\b"                                   # 0x008A3350 (>=5 hex)
    r"|\boffset\s+(?:0x[0-9A-Fa-f]+|\d{3,})\b"                  # offset 4536 / offset 0x..
    r"|\b(?:address|VA|RVA|file[\s_-]?offset)\s*(?:is|=|:|at)?\s*0x[0-9A-Fa-f]{4,}\b"
    r")",
    re.IGNORECASE,
)

# Hedge / non-assertive context (suppresses the nudge within a window).
_HEDGE = re.compile(
    r"\b(?:might be|maybe|possibly|approximately|around|guess|not sure|unverified|"
    r"need to (?:verify|check|confirm)|should be|tentative|placeholder|example|"
    r"e\.g\.|for instance|roughly)\b",
    re.IGNORECASE,
)

# Tool signatures that count as RE/inspection verification THIS turn.
_RE_TOOL_NAME = re.compile(
    r"(ida[-_]?pro|ghidra|binary[-_]?ninja|binja|frida|cheatengine|radare2|r2mcp)",
    re.IGNORECASE,
)
_RE_BASH = re.compile(
    r"\b(objdump|readelf|\bnm\b|gdb|rabin2|\br2\b|hexdump|xxd|capstone)\b",
    re.IGNORECASE,
)
_BIN_PATH = re.compile(r"\.(so|dll|exe|bin|elf|o|a|dylib)\b|offset", re.IGNORECASE)


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
        return False
    return True


def _assistant_text(ev: dict):
    msg = ev.get("message") or {}
    role = msg.get("role") or ev.get("role")
    if not ((ev.get("type") == "assistant" and msg.get("role") == "assistant")
            or role == "assistant"):
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


def _tool_uses(ev: dict):
    """Yield (name, input_str) for tool_use blocks in an assistant event."""
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            yield str(b.get("name") or ""), json.dumps(b.get("input") or {})


def analyze(transcript_path: str):
    """Return (final_text, anchors_present, verified_this_turn)."""
    events = list(_iter_events(transcript_path))
    last_human = -1
    for i, ev in enumerate(events):
        if _is_human(ev):
            last_human = i

    final_text = None
    verified = False
    for i, ev in enumerate(events):
        txt = _assistant_text(ev)
        if txt is not None:
            final_text = txt
        if i > last_human:
            for name, inp in _tool_uses(ev):
                if _RE_TOOL_NAME.search(name):
                    verified = True
                elif name in ("Bash", "PowerShell") and _RE_BASH.search(inp):
                    verified = True
                elif name == "Read" and _BIN_PATH.search(inp):
                    verified = True
    return final_text, verified


def _has_unhedged_anchor(text: str) -> bool:
    for m in _ANCHOR.finditer(text):
        lo, hi = max(0, m.start() - 100), min(len(text), m.end() + 100)
        if not _HEDGE.search(text[lo:hi]):
            return True
    return False


def main() -> int:
    try:
        if MODE == "off" or DISABLED.exists() or os.environ.get("TRUTH_VERIFY", "").lower() in ("off", "0", "false"):
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
        final_text, verified = analyze(tp)
        if not final_text:
            return 0
        if verified:
            return 0  # an RE/inspection tool ran this turn -> trust it
        if not _has_unhedged_anchor(final_text):
            return 0
        msg = (
            "[truth-verify] You stated a load-bearing RE anchor (a hex address / "
            "sub_/ offset) as fact, but NO verifying tool ran this turn (no ida/"
            "ghidra/binary-ninja/frida/cheatengine/radare2 call, binary Read, or "
            "objdump/readelf). Re-derive it from the binary/offsets in a FRESH check "
            "before relying on it (see the fresh-verify skill) — a wrong-but-"
            "consistent anchor is the classic RE sunk-cost trap. (tests/build/coverage "
            "claims are handled separately by claim-guard.)"
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop", "additionalContext": msg}}))
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
