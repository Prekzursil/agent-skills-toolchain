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
  - A certainty marker present, NOT inside a hedge window, NOT in a deferred domain,
    AND co-located (±120 chars) with a technical indicator (a `code span`, a file
    path, or a technical noun).
  - No CLAIM-RELEVANT evidence this turn. Suppression is keyed to what the tools
    actually touched, not to a bare count of tool calls: an occurrence is silenced
    only when one of its distinctive ANCHORS (a `code span`, a file path, a
    snake_case/camelCase/ALL_CAPS identifier) appears in this turn's tool inputs or
    tool results. A window with no judgeable anchor keeps the old benefit-of-the-doubt
    and stays silent whenever any substantive tool ran.
    Was: "ANY real tool ran -> stay silent". That let one unrelated `Read README.md`
    silence "the `timeout` is definitely 30 seconds" — an arbitrary action counted as
    evidence for an untouched fact. Only tool inputs/results are inspected; a *failed*
    tool still contributes its text, so a red command that merely MENTIONS the anchor
    suppresses (settle by threading tool_result `is_error` through `analyze`).

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
    r"(?:`[^`]+`"  # inline code span
    r"|[\w./\\-]+\.(?:py|ts|tsx|js|jsx|mjs|go|rs|java|rb|c|cc|cpp|h|hpp|cs|kt|swift|"
    r"json|ya?ml|toml|ini|cfg|sh|ps1|sql|html|css)\b"  # a file path
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

# EVIDENCE ANCHORS — tokens distinctive enough that finding one in what the tools
# actually touched is real evidence FOR THIS claim. Plain English words are deliberately
# excluded: they occur in almost any tool output and would rebuild the blanket
# "some tool ran" suppression this replaces.
_CODE_SPAN = re.compile(r"`([^`]+)`")
_PATH_ANCHOR = re.compile(
    r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|mjs|go|rs|java|rb|c|cc|cpp|h|hpp|cs|kt|swift|"
    r"json|ya?ml|toml|ini|cfg|sh|ps1|sql|html|css)\b",
    re.IGNORECASE,
)
# snake_case | ALL_CAPS/acronym (>=3) | camelCase — i.e. it looks like code, not prose.
_IDENT_ANCHOR = re.compile(r"\b(?:\w+_\w+|[A-Z]{3,}|[a-z]+[A-Z]\w*)\b")

# Shortest token accepted as an anchor. Below this a token is too generic to be
# evidence (and a false "anchor found" only ever silences us, never nags).
_MIN_ANCHOR = 4

# Upper bound on the evidence text collected per turn. RESIDUAL (disclosed, not fixed):
# a turn whose tool traffic exceeds this AND whose anchor falls past the cut would nag
# spuriously; settle by measuring real turn evidence sizes from ~/.claude transcripts.
_EVIDENCE_CAP = 1_000_000

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
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    ):
        return False  # a tool_result is not a fresh human turn
    return True


def _assistant_text(ev: dict):
    msg = ev.get("message") or {}
    role = msg.get("role") or ev.get("role")
    if not (
        (ev.get("type") == "assistant" and msg.get("role") == "assistant")
        or role == "assistant"
    ):
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


def _blocks(ev: dict):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict)]


def _stringify(value) -> str:
    """Flatten a tool input/result payload to searchable text. Never raises."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _anchors(window: str) -> set[str]:
    """Distinctive tokens from a claim window (see _CODE_SPAN/_PATH_ANCHOR/_IDENT)."""
    found: set[str] = set()
    raw = (
        _CODE_SPAN.findall(window)
        + _PATH_ANCHOR.findall(window)
        + _IDENT_ANCHOR.findall(window)
    )
    for item in raw:
        token = item.strip().lower()
        if len(token) >= _MIN_ANCHOR:
            found.add(token)
        for part in re.split(r"[^0-9a-z]+", token):
            if len(part) >= _MIN_ANCHOR:
                found.add(part)
    return found


def analyze(transcript_path: str):
    """Return (final_text, n_verifying_tools_this_turn, evidence_text).

    `evidence_text` is the lowercased text of what this turn's substantive tools
    actually touched — each tool_use's name + input, plus the matching tool_result
    payloads. It is what makes suppression CLAIM-RELEVANT rather than a bare
    "some tool ran" count. TodoWrite/TodoRead contribute neither a count nor
    evidence (their results are dropped by tool_use_id).
    """
    events = list(_iter_events(transcript_path))
    last_human = -1
    for i, ev in enumerate(events):
        if _is_human(ev):
            last_human = i
    final_text = None
    tools = 0
    skip_ids: set[str] = set()
    chunks: list[str] = []
    size = 0
    for i, ev in enumerate(events):
        txt = _assistant_text(ev)
        if txt is not None:
            final_text = txt
        if i <= last_human:
            continue
        for b in _blocks(ev):
            kind = b.get("type")
            if kind == "tool_use":
                name = str(b.get("name") or "")
                if not name:
                    continue
                if name in _NON_VERIFYING:
                    skip_ids.add(str(b.get("id") or ""))
                    continue
                tools += 1
                if size >= _EVIDENCE_CAP:
                    continue  # keep counting, but stop paying to serialise
                piece = name + " " + _stringify(b.get("input"))
            elif kind == "tool_result":
                if size >= _EVIDENCE_CAP:
                    continue
                if str(b.get("tool_use_id") or "") in skip_ids:
                    continue
                piece = _stringify(b.get("content"))
            else:
                continue
            piece = piece[: _EVIDENCE_CAP - size]
            chunks.append(piece)
            size += len(piece)
    return final_text, tools, " ".join(chunks).lower()


def find_offenders(text: str, evidence: str = "") -> list[str]:
    """Return short snippets of certainty claims lacking verification & not deferred.

    `evidence` is `analyze()`'s third value — the text this turn's tools touched. Empty
    means no substantive tool ran, so every qualifying occurrence is an offender. When
    it is non-empty an occurrence is SUPPRESSED if the evidence touched the claim (an
    anchor appears in it) or if the window yields no judgeable anchor at all.
    """
    offenders = []
    for m in _CERTAINTY.finditer(text):
        lo, hi = max(0, m.start() - 120), min(len(text), m.end() + 120)
        window = text[lo:hi]
        if _HEDGE.search(window):
            continue  # hedged -> honest already
        if _RE_ANCHOR.search(window):
            continue  # defer to truth-verify
        if _CLAIM_GUARD.search(window):
            continue  # defer to claim-guard
        if not _TECH.search(window):
            continue  # not a load-bearing technical claim
        if evidence:
            anchors = _anchors(window)
            if not anchors or any(a in evidence for a in anchors):
                continue  # tools touched this claim (or it has no judgeable anchor)
        snippet = re.sub(
            r"\s+", " ", text[max(0, m.start() - 40) : m.end() + 40]
        ).strip()
        offenders.append(snippet)
        if len(offenders) >= 3:
            break
    return offenders


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("HONEST_SIGNAL", "").lower() in (
            "off",
            "0",
            "false",
        ):
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
        final_text, tools, evidence = analyze(tp)
        if not final_text:
            return 0
        offenders = find_offenders(final_text, evidence)
        if not offenders:
            return 0
        shown = "; ".join(f'"...{o}..."' for o in offenders[:2])
        ran = (
            "ran NO verifying tool this turn"
            if tools == 0
            else f"none of the {tools} tool call(s) you ran this turn touched it"
        )
        msg = (
            "[honest-signal] You asserted a technical claim as CERTAIN "
            f"({shown}) but {ran}. Self-confidence is not "
            "evidence — either mark it INFERRED/GUESSED (hedge it), or actually verify "
            "it (read the file / run the command / call the tool) before stating it as "
            "fact. (RE anchors -> truth-verify; test/build/coverage claims -> claim-guard.)"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": msg,
                    }
                }
            )
        )
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
