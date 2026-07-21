#!/usr/bin/env python3
"""
profile-capture - a Stop hook that notices when the owner says something about HIMSELF.

WHY THIS EXISTS (decision G-4, 2026-07-21)
The owner's own framing of the problem: "i dont specifically tell info to you about me
without having scope at that (not just chatting about me sessions)". Measured and confirmed:
a detector-verified scan of 1,552 owner-authored text blocks across 136 Claude Code
transcripts found FOUR first-person biographical statements, and all four were false
positives ("my units", "my agents"). He talks to this tool about WORK, never about himself.

So a profile built only from what he says here rots. This hook catches the rare moment he
does say something, and queues it for HIS review. It never writes to the profile itself.

DESIGN CONSTRAINTS, each from a decision or a measured failure:
  * G-3 chose ON-DEMAND storage - so this must cost ZERO context. A hook runs outside the
    model, which is exactly why this mechanism is compatible with that choice.
  * NOTHING AUTO-WRITES. Candidates land in a queue; the owner approves in batches. An
    assistant silently promoting an inference to a fact is how the padded profile happened.
  * Never nag. Surface only at >= THRESHOLD candidates, or on demand via /profile-review.
  * Fail OPEN. Any exception exits 0 - a hook that breaks the session to protect a
    nice-to-have is a bad trade (AGENTS.md 6).
  * Never capture SENSITIVE-tier content unprompted. Health, finance, relationships and
    substance topics are excluded by pattern; the owner adds those deliberately or not at all.

Install: Stop hook in ~/.claude/settings.json ->
    python "C:/Users/Prekzursil/.claude/hooks/profile-capture/capture.py"
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = HERE / "capture-queue.jsonl"
SEEN = HERE / "seen.txt"
THRESHOLD = 5          # surface only at this many pending candidates
MAX_QUEUE = 500        # bounded sink; never grows without limit
MIN_LEN, MAX_LEN = 25, 600

# --- what counts as the owner saying something about himself -------------------------------
# v2, REWRITTEN after the v1 detector shipped and scored ~0/20 precision in production.
#
# WHY v1 FAILED: it matched `i (am|'m) (a|an|the|now|currently|still|not)`, and in these
# transcripts "I am now ..." / "I am not ..." is overwhelmingly ASSISTANT PROGRESS NARRATION.
# The owner routinely pastes assistant output, reports and templates into his own turns, so
# all of that arrives tagged role="user". v1's both-states test passed only because the
# fixtures were hand-written to match v1's own assumptions - fixture-green proved internal
# consistency, not fit to the real distribution (the trap named in my_writing/RUNBOOK.md 6).
#
# v2 requires a BIOGRAPHICAL OBJECT, not merely a first-person verb.
BIO_NOUN = (r"student|teaching assistant|ta\b|assistant|developer|engineer|researcher|"
            r"programmer|freelancer|intern|phd|msc|bsc|master'?s|bachelor'?s|undergrad|"
            r"graduate|romanian|english|based in|from\b")
PATTERNS = [
    # "I am a student", "I'm a teaching assistant" - a first-person COPULA plus a role noun
    rf"\bi(?:'m| am)\s+(?:an?\s+|the\s+)?(?:{BIO_NOUN})",
    # life verbs that are almost never narration
    r"\bi\s+(?:live|was born|grew up|graduated|enrolled|study at|studied at|"
    r"teach at|work at|moved to|come from)\b",
    r"\bi\s+(?:speak|am fluent in)\s+\w+",
    # possessive + a biographical noun (never "my agents"/"my repo")
    r"\bmy\s+(?:name|birthday|birth date|age|phone|e-?mail|address|university|faculty|"
    r"degree|thesis|dissertation|supervisor|professor|employer|company|job title|orcid|"
    r"linkedin|scholar|girlfriend|partner|parents|father|mother|brother|sister)\b",
    r"\bmy\s+phd\b|\bphd\s+(?:direction|topic|proposal|application|supervisor)\b",
    # Romanian
    r"\bsunt\s+(?:un\s+|o\s+)?(?:student|inginer|profesor|asistent)\b",
    r"\blocuiesc\b|\bm[aă] numesc\b|\bam terminat\b|\bam absolvit\b|\bm-am n[aă]scut\b",

    # v3: LABEL:VALUE. Measured on real transcripts - v2 caught ZERO across 72 MB, including
    # a session where he stated his name, birth date, phones, role and ORCID, because he
    # answers direct questions in terse labelled form and never in first person:
    #     "birth day: 8 june 2002"   "phone number: +40740935228"
    #     "3: Student and teaching assistent at University Of Bucharest"
    # A first-person detector structurally cannot see that shape. Closed label set only -
    # an open one would fire on every config file and API response he pastes.
    # NOT bare "name:" - measured false positive on `name: 'my-workflow',` in a JS config.
    # "name" is among the commonest keys in YAML/JSON/JS, so it must be qualified.
    r"^\s*(?:full|legal|my)\s+name\s*[:=]\s*\S",
    r"^\s*(?:birth\s*day|birthday|birth\s*date|date of birth|dob)\s*[:=]\s*\S",
    r"^\s*(?:phone|phone\s*number|mobile|tel)\s*[:=]\s*\+?\d",
    r"^\s*orcid\s*[:=]\s*\d{4}-\d{4}-\d{4}-\d{3}[\dX]",
    r"^\s*(?:university|faculty|affiliation|institution|employer|job\s*title|role)\s*[:=]\s*\S",
    r"^\s*(?:linkedin|scholar|orcid|website|homepage)\s*[:=]\s*\S*\w",
]

# Narration shapes that v1 swallowed. Checked BEFORE the biographical patterns.
NARRATION = re.compile(
    r"\bi(?:'m| am)\s+(?:now|not|also|still|going to|about to|already|currently)\s+\w+ing\b"
    r"|\bi(?:'m| am)\s+not\s+(?:choosing|applying|theori|relaunch|going)"
    r"|\bi\s+(?:will|would|can|could|should|shall)\b"
    r"|\blet me\b|\bi'?ll\b", re.I)

# Pasted structured content - a bullet, heading, table row, quote, code or template slot is
# not somebody talking about themselves.
PASTED = re.compile(r"^\s*(?:[-*+•>#|]|\d+\.\s|```|\[|\{)|\[(?:role|action|benefit|name)\]"
                    r"|^\s*(?:As a|Example:|STATUS|VENUE)\b", re.I)

# Code/config shapes. A label:value line that carries quotes, a trailing comma, a comment
# marker or braces is a config key, not a person answering a question. Measured: the v3
# label set fired on `name: 'my-workflow',   // the /slash name` in a workflow script.
CODEISH = re.compile(r"""['"`]|,\s*$|//|/\*|=>|[{}\[\]]|\bself\.|\bdef\s|\bconst\s|\bvar\s""")

# Never capture these unprompted. G-2 keeps a full-fidelity PRIVATE tier, but it is the
# owner's to populate - a hook harvesting health or relationship detail is not acceptable.
EXCLUDE = [
    r"\b(?:depress|anxiet|diagnos|therapy|medication|dose|dosage|mg\b|withdrawal|"
    r"addict|overdose|symptom|prescription|clinic|hospital)\w*",
    r"\b(?:salary|debt|loan|rent|broke|afford|overdraft|chargeback|refund|invoice)\w*",
    r"\b(?:girlfriend|breakup|broke up|divorce|dating|relationship problem)\w*",
]

# Work-shaped false friends: "my agents", "my units", "my repo" - the measured 4/4.
FALSE_FRIENDS = re.compile(
    r"\bmy\s+(?:agents?|units?|repos?|branch|commits?|tests?|files?|scripts?|hooks?|"
    r"workflow|session|corpus|tools?|servers?|configs?|prompts?)\b", re.I)

PAT = [re.compile(p, re.I) for p in PATTERNS]
EXC = [re.compile(p, re.I) for p in EXCLUDE]


def load_seen() -> set[str]:
    if not SEEN.exists():
        return set()
    return set(SEEN.read_text(encoding="utf-8", errors="replace").split("\n"))


def transcript_path(payload: dict) -> Path | None:
    p = payload.get("transcript_path") or payload.get("transcriptPath")
    return Path(p) if p and Path(p).exists() else None


def owner_turns(path: Path):
    """Yield this session's user-authored text. Assistant text is not self-disclosure."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") or {}
                if msg.get("role") != "user":
                    continue
                c = msg.get("content")
                if isinstance(c, str):
                    yield c
                elif isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "text":
                            yield b.get("text", "")
    except Exception:
        return


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tp = transcript_path(payload)
    if not tp:
        return 0

    seen = load_seen()
    new = []
    for text in owner_turns(tp):
        for raw in re.split(r"(?<=[.!?\n])\s+", text or ""):
            s = raw.strip()
            if not (MIN_LEN <= len(s) <= MAX_LEN):
                continue
            # a slash-command or a pasted block is not self-disclosure
            if s.startswith(("/", "```", "http")):
                continue
            if PASTED.search(s):          # v2: bullets, headings, templates, quoted blocks
                continue
            # v3: config keys are not self-disclosure. Scope this to the FIRST LINE only -
            # scanning the whole segment killed a genuine "birth day: ... / phone number: ..."
            # capture because the segment ran on into pasted hook output containing a quote.
            if CODEISH.search(s.split("\n", 1)[0]):
                continue
            if NARRATION.search(s):       # v2: "I am now ...ing" is progress, not biography
                continue
            if FALSE_FRIENDS.search(s):
                continue
            if any(e.search(s) for e in EXC):
                continue
            if not any(p.search(s) for p in PAT):
                continue
            key = re.sub(r"\W+", "", s.lower())[:120]
            if key in seen:
                continue
            seen.add(key)
            new.append({
                "captured": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": payload.get("session_id", ""),
                "text": s,
                "status": "pending",
            })

    if new:
        HERE.mkdir(parents=True, exist_ok=True)
        with open(QUEUE, "a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        SEEN.write_text("\n".join(sorted(seen))[:400_000], encoding="utf-8")

    # bounded sink
    if QUEUE.exists():
        lines = QUEUE.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > MAX_QUEUE:
            QUEUE.write_text("\n".join(lines[-MAX_QUEUE:]) + "\n", encoding="utf-8")
        pending = sum(1 for x in lines if '"status": "pending"' in x)
    else:
        pending = 0

    # Surface ONLY at the threshold. Never nag.
    if pending >= THRESHOLD:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": (
                    f"[profile-capture] {pending} unreviewed statements you made about "
                    f"yourself are queued at {QUEUE}. Run /profile-review to approve or "
                    f"discard them. Nothing has been written to your profile."
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # fail OPEN, always (AGENTS.md 6)
        sys.exit(0)
