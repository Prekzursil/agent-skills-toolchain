#!/usr/bin/env python3
"""recall-gate/gate.py — UserPromptSubmit prior-art gate over the LOCAL TREE.

What problem this actually solves
---------------------------------
On 2026-08-07 seven confident claims were wrong and NOT ONE was a detector
failure: every answer was already available and unread. The majority named a
**tree artifact** (``_shared/use_vs_mention.py``, ``ci-hygiene.md`` §4, a
benchmark script, a gate's own output) — present on disk, absent from the
basic-memory vault.

What was ALREADY built (measured, not assumed — see 31-LANE-recall.md)
----------------------------------------------------------------------
``RecallModule`` / ``bounded_recall`` (``~/.agents/harness/modules.py:1984``) is
live on UserPromptSubmit via the harness dispatcher and WORKS: an end-to-end
probe surfaced the right use-vs-mention note in 0.68 s. It serves the **vault**.
Measured against the live index (597 notes): ``.claude/hooks`` 0, ``.agents/
harness`` 0, ``.claude/rules`` 0. This gate serves that unserved half and does
NOT re-search the vault — duplicating ``bounded_recall`` would double cost for
zero new coverage.

Contract
--------
* **Inject-only. Never blocks.** Exit code is ALWAYS 0.
* **Typed silence is law.** Every run resolves to exactly one of
  ``FINDING | CLEAN | NOT-CHECKED | RAISED | DEGRADED`` and records it to a
  bounded sink. Only FINDING injects — a CLEAN must never manufacture a digest.
  A run that cannot prove it executed emits NOT-CHECKED, never nothing.
* **Hard deadline.** The four DISARMED Stop checks are O(session length) with no
  deadline. This gate is O(index) behind a content-hash cache, with a monotonic
  deadline checked between phases and inside the match loop. Blowing it yields
  NOT-CHECKED, never a partial CLEAN.
* **Fail-open.** Any exception → RAISED, exit 0, no output.

Opt-out: ``RECALL_GATE=off`` or a ``.disabled`` file in this directory.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import tree_index as ti  # noqa: E402  # local sibling; import follows sys.path setup

HOME = Path.home()
SINK_DIR = THIS / "state"
BUDGET_SEC = float(os.environ.get("RECALL_GATE_BUDGET_SEC", "2.5"))
MAX_HITS = int(os.environ.get("RECALL_GATE_MAX_HITS", "4"))
MIN_PROMPT = 30

STATE_FINDING = "FINDING"
STATE_CLEAN = "CLEAN"
STATE_NOT_CHECKED = "NOT-CHECKED"
STATE_RAISED = "RAISED"
STATE_DEGRADED = "DEGRADED"

# ── intent detection ─────────────────────────────────────────────────────────
# The precision lever. Prior art is only worth surfacing when the prompt is
# about to ASSERT ABSENCE or BUILD SOMETHING. Every other prompt stays CLEAN,
# which is what keeps the negative control silent.
_ABSENCE = re.compile(
    r"\b(?:"
    r"does(?:\s+not|n[’']t)\s+exist|do(?:es)?\s+we\s+have|is\s+there\s+(?:a|an|any)|"
    r"there\s+is\s+no|there\s+are\s+no|no\s+such|not\s+implemented|never\s+(?:built|implemented)|"
    r"nothing\s+(?:exists|there)|from\s+scratch|greenfield|unbuilt|"
    r"missing|absent|novel|brand[\s-]new"
    r")\b",
    re.I,
)
_BUILD = re.compile(
    r"\b(?:build|create|implement|write|add|design|introduce|scaffold|author)\s+"
    r"(?:a|an|the|new|our)?\s*",
    re.I,
)
_EXIST_Q = re.compile(
    r"\b(?:already\s+(?:exist|built|have|there)|prior\s+art|reuse)\b", re.I
)

# Generic words that must never trigger a lookup on their own.
_GENERIC = frozenset(
    """hook hooks check checks test tests file files path paths code line lines
    script scripts state module modules index data json main run runs gate gates
    tool tools name names time value values type types list dict text string
    error errors result results output input config setting settings report
    project session prompt agent agents claude python windows write read edit
    thing stuff work works task tasks step steps case cases part parts item
    items note notes word words rule rules guard guards fix fixes bug bugs
    function class method return import export update change changes make
    docs doc readme todo""".split()
)

_NOUN = re.compile(
    r"[A-Za-z][A-Za-z0-9]*(?:[_-][A-Za-z0-9]+)+|[A-Za-z][A-Za-z0-9_]{5,}"
)
_DOTTED = re.compile(r"\b([A-Za-z0-9_-]{3,}\.(?:py|md|json|ps1|sh))\b")
_QUOTED = re.compile(r"[`\"']([A-Za-z0-9_./-]{4,})[`\"']")


def detect_intent(prompt: str) -> str | None:
    """Return the intent kind, or None when no prior-art lookup is warranted."""
    if _ABSENCE.search(prompt):
        return "absence-claim"
    if _EXIST_Q.search(prompt):
        return "prior-art-question"
    if _BUILD.search(prompt):
        return "build-intent"
    return None


def extract_nouns(prompt: str) -> list[str]:
    """Pull distinctive artifact nouns (identifiers, filenames, quoted terms)."""
    raw: list[str] = []
    raw += [m.group(1) for m in _DOTTED.finditer(prompt)]
    raw += [m.group(1) for m in _QUOTED.finditer(prompt)]
    raw += _NOUN.findall(prompt)
    seen: set[str] = set()
    out: list[str] = []
    for r in raw:
        n = r.strip().strip(".").lower()
        n = n.rsplit("/", 1)[-1]
        base = n[:-3] if n.endswith(".py") else n
        base = base.rsplit(".", 1)[0] if "." in base else base
        if len(base) < 4 or base in _GENERIC or base in seen:
            continue
        parts = [p for p in re.split(r"[_-]", base) if p]
        if len(parts) == 1 and base in _GENERIC:
            continue
        seen.add(base)
        out.append(base)
    return out[:12]


#: A noun matching more than this many files is not distinctive enough to be
#: prior art — it is vocabulary. Measured: 'length' (from "O(session length)")
#: matched three unrelated test files and crowded the real hit out of a 4-slot
#: digest. An inverse-document-frequency cap is the cheap, deterministic fix.
MAX_DF = int(os.environ.get("RECALL_GATE_MAX_DF", "8"))


def match(nouns: list[str], entries: list[dict], deadline: float) -> list[dict]:
    """Rank tree entries against candidate nouns. Deadline-bounded.

    Two precision guards, both measured rather than guessed:

    1. **Single-word nouns qualify ONLY on an exact stem match.** Measured: the
       bare word 'length' (extracted from "O(session length)") hit three
       unrelated test files at symbol level and crowded the one real hit out of
       a 4-slot digest. A multi-part identifier (``transcript_tail``,
       ``use-vs-mention``) is artifact-shaped and may match at symbol level; a
       lone English word is vocabulary and must clear the highest bar.
    2. **A document-frequency cap** drops any noun matching > ``MAX_DF`` files.
       This is the backstop, NOT the primary guard — 'length' had DF=3 and would
       have sailed through a DF cap alone.
    """
    hits: dict[str, tuple[int, dict, str]] = {}
    for noun in nouns:
        if time.monotonic() > deadline:
            break
        parts = {p for p in re.split(r"[_-]", noun) if len(p) >= 3}
        multi = len(parts) >= 2
        noun_hits: dict[str, tuple[int, dict, str]] = {}
        for e in entries:
            keys = e.get("keys") or []
            stem = str(e.get("stem", "")).lower()
            score = 0
            if noun.replace("-", "_") == stem.replace("-", "_"):
                score = 100
            elif multi and noun in keys:
                score = 60
            elif multi and parts.issubset(set(keys)):
                score = 50
            if not score:
                continue
            noun_hits[e["path"]] = (score, e, noun)
        if len(noun_hits) > MAX_DF:
            continue  # non-distinctive noun — drop it entirely
        for path, cand in noun_hits.items():
            prev = hits.get(path)
            if prev is None or cand[0] > prev[0]:
                hits[path] = cand
    ranked = sorted(hits.values(), key=lambda x: (-x[0], x[1]["rel"]))
    return [{"score": s, "noun": n, **e} for s, e, n in ranked[:MAX_HITS]]


def vault_status() -> str:
    """Cheap liveness probe for the OTHER recall path (bounded_recall's index).

    A hook subprocess cannot call ``mcp__basic-memory__search_notes`` — MCP tools
    are invoked by the model, not by hook processes (this is why BOTH existing
    recall implementations read the vault from disk). The honest proxy is the
    servability contract ``modules.py:_recall_index_is_servable`` applies:
    schema_version int in range AND an ISO ``built_at`` inside the age limit.
    Reads only a head slice, never the full 1.4 MB document.
    """
    p = HOME / ".agents" / "state" / "harness" / "recall-index.json"
    try:
        if not p.exists():
            return "NOT-CHECKED(no-index)"
        with open(p, "rb") as fh:
            head = fh.read(400).decode("utf-8", errors="replace")
        sv = re.search(r'"schema_version"\s*:\s*(\d+)', head)
        ba = re.search(r'"built_at"\s*:\s*"([^"]+)"', head)
        if not sv or not ba:
            return "DEGRADED(undatable)"
        from datetime import datetime, timezone  # noqa: PLC0415

        stamp = datetime.fromisoformat(ba.group(1))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp).total_seconds() / 86400.0
        return "OK" if age <= 30.0 else f"DEGRADED(stale {age:.0f}d)"
    except Exception:  # noqa: BLE001
        return "NOT-CHECKED(probe-failed)"


def record(state: str, detail: dict) -> None:
    """Append one typed line to a bounded sink. Never raises."""
    try:
        SINK_DIR.mkdir(parents=True, exist_ok=True)
        day = time.strftime("%Y%m%d")
        f = SINK_DIR / f"recall-gate-{day}.jsonl"
        if f.exists() and f.stat().st_size > 2_000_000:
            return
        rec = {"ts": time.time(), "state": state, **detail}
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def format_digest(hits: list[dict], intent: str, vault: str) -> str:
    lines = [
        "PRIOR ART (recall-gate — local harness tree; these files EXIST, read "
        "before asserting absence or rebuilding):"
    ]
    for h in hits:
        summ = (h.get("summary") or "").strip()
        tail = f" — {summ[:110]}" if summ else ""
        lines.append(f"- ~/{h['rel']} (matched '{h['noun']}'){tail}")
    lines.append(f"[intent={intent} · vault-index={vault} · tree prior-art only]")
    return "\n".join(lines)


def run(data: dict, budget_sec: float = BUDGET_SEC) -> tuple[str, str | None]:
    """Core logic. Returns (typed_state, message_or_None). Never raises."""
    t0 = time.monotonic()
    deadline = t0 + max(0.2, budget_sec)
    try:
        if (THIS / ".disabled").exists():
            return STATE_CLEAN, None
        if os.environ.get("RECALL_GATE", "").strip().lower() in ("off", "0", "false"):
            return STATE_CLEAN, None

        prompt = str(data.get("prompt") or "")
        if len(prompt.strip()) < MIN_PROMPT:
            record(STATE_CLEAN, {"reason": "short-prompt"})
            return STATE_CLEAN, None

        intent = detect_intent(prompt)
        if not intent:
            record(STATE_CLEAN, {"reason": "no-intent"})
            return STATE_CLEAN, None

        nouns = extract_nouns(prompt)
        if not nouns:
            record(STATE_CLEAN, {"reason": "no-nouns", "intent": intent})
            return STATE_CLEAN, None

        remaining = deadline - time.monotonic()
        if remaining <= 0.1:
            record(
                STATE_NOT_CHECKED, {"reason": "budget-before-index", "intent": intent}
            )
            return STATE_NOT_CHECKED, None

        idx = ti.get_or_build(budget_sec=min(remaining, 2.0))
        if not idx.get("ok") or not idx.get("entries"):
            record(
                STATE_NOT_CHECKED,
                {
                    "reason": "index-unavailable",
                    "truncated": idx.get("truncated"),
                    "intent": intent,
                    "nouns": nouns,
                },
            )
            return STATE_NOT_CHECKED, None

        if time.monotonic() > deadline:
            record(
                STATE_NOT_CHECKED, {"reason": "budget-after-index", "intent": intent}
            )
            return STATE_NOT_CHECKED, None

        hits = match(nouns, idx["entries"], deadline)
        vault = vault_status()
        elapsed = time.monotonic() - t0

        if not hits:
            record(
                STATE_CLEAN,
                {
                    "reason": "no-prior-art",
                    "intent": intent,
                    "nouns": nouns,
                    "vault": vault,
                    "elapsed": round(elapsed, 4),
                },
            )
            return STATE_CLEAN, None

        record(
            STATE_FINDING,
            {
                "intent": intent,
                "nouns": nouns,
                "vault": vault,
                "hits": [h["rel"] for h in hits],
                "elapsed": round(elapsed, 4),
            },
        )
        return STATE_FINDING, format_digest(hits, intent, vault)

    except Exception as exc:  # noqa: BLE001
        record(STATE_RAISED, {"error": type(exc).__name__})
        return STATE_RAISED, None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001
        data = {}
    try:
        _state, msg = run(data)
        if msg:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": msg,
                        }
                    }
                )
            )
    except Exception:  # noqa: BLE001
        pass
    return 0  # ALWAYS 0 — inject-only, never blocks


if __name__ == "__main__":
    sys.exit(main())
