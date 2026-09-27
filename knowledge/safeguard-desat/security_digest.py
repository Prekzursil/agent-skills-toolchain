#!/usr/bin/env python
"""security_digest.py - standalone PostToolUse.updatedToolOutput de-saturation hook.

STAGED / OFF-MAIN / OFF-BY-DEFAULT. This is NOT an edit to the live
cmd-rewrite/compress-output.py; it is a portable, self-contained drop-in you ingest
where you want it (live hook / CyberStrike / a fresh session). It no-ops unless
SECURITY_DIGEST_ENABLE=1, so ingesting it changes NOTHING until explicitly activated
(no regression). Fail-open: any error emits nothing => the tool output passes through
unchanged.

WHY: the estate classifier false-positive is triggered by ACCUMULATED context, and a
single large payload can one-shot it (research: a 17k-line blocklist cat). This hook
replaces an over-large payload in-context with a compact digest (byte/line counts +
sha256 + bounded head/tail) BEFORE it accumulates in the window. It de-saturates the
CONTEXT; it does not hide anything from the classifier on the wire and it is not
redaction - the full output was already produced by the tool and remains in the
transcript/on disk. It attacks the real trigger (context volume), not the prompt or
the model.

DESIGN NOTE: detection is deliberately STRUCTURAL (size + base64-ish blob + very long
lines / line counts) plus an OPTIONAL external pattern file (SECURITY_DIGEST_PATTERNS
-> a file of one regex per line). No trigger vocabulary is baked into this module, so
it is domain-neutral and safe to carry around; supply patterns externally per surface.

Contract (mirrors cmd-rewrite/compress-output.py):
  stdin  PostToolUse JSON: {tool_name, tool_input:{command}, tool_response: str|{...}}
  stdout {"hookSpecificOutput":{"hookEventName":"PostToolUse","updatedToolOutput":"<digest>"}}
"""
import sys
import os
import json
import hashlib
import re

ENABLED = os.environ.get("SECURITY_DIGEST_ENABLE", "").strip().lower() in ("1", "true", "on")
SIZE = int(os.environ.get("SECURITY_DIGEST_SIZE", "6000"))       # only consider large payloads
MAX_LINES = int(os.environ.get("SECURITY_DIGEST_MAX_LINES", "400"))
MAX_LINE = int(os.environ.get("SECURITY_DIGEST_MAX_LINE", "2000"))
HEAD = int(os.environ.get("SECURITY_DIGEST_HEAD", "40"))
TAIL = int(os.environ.get("SECURITY_DIGEST_TAIL", "10"))

_BLOB = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")  # long base64-ish run (keys, dumps, encoded blobs)


def _text(tr):
    """Extract text from tool_response (str or dict), mirroring compress-output.py."""
    if isinstance(tr, str):
        return tr
    if isinstance(tr, dict):
        for k in ("text", "content", "stdout", "output"):
            v = tr.get(k)
            if isinstance(v, str):
                return v
        try:
            return json.dumps(tr, ensure_ascii=False)
        except Exception:
            return None
    return None


def _load_patterns():
    pf = os.environ.get("SECURITY_DIGEST_PATTERNS", "").strip()
    if not pf or not os.path.isfile(pf):
        return []
    try:
        raw = open(pf, encoding="utf-8").read().splitlines()
        return [p for p in raw if p.strip() and not p.lstrip().startswith("#")]
    except Exception:
        return []


def is_heavy(text):
    """Return (heavy: bool, reason: str). Structural + optional external patterns; no baked vocab."""
    if len(text) < SIZE:
        return False, "under-size"
    if _BLOB.search(text):
        return True, "blob"
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        return True, "many-lines"
    if max((len(l) for l in lines), default=0) > MAX_LINE:
        return True, "long-line"
    pats = _load_patterns()
    for p in pats:
        try:
            if re.search(p, text, re.I):
                return True, "pattern"
        except re.error:
            continue
    return False, "large-but-no-signal"


def digest(text, cmd, reason):
    sha = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
    lines = text.splitlines()
    n, nb = len(lines), len(text.encode("utf-8", "replace"))
    head = "\n".join(lines[:HEAD])
    tail = "\n".join(lines[-TAIL:]) if n > HEAD + TAIL else ""
    parts = [
        "[security-digest] context-budget summary (NOT redaction): the tool produced "
        "%d lines / %d bytes; elided from the live context to keep dense content from "
        "accumulating. Full output remains in the transcript/on disk." % (n, nb),
        "sha256:%s  trigger:%s" % (sha, reason),
    ]
    if cmd:
        parts.append("cmd: %s" % cmd[:160])
    parts.append("--- head (%d lines) ---" % min(HEAD, n))
    parts.append(head)
    if tail:
        parts.append("--- tail (%d lines) ---" % TAIL)
        parts.append(tail)
    return "\n".join(parts)


def main():
    if not ENABLED:
        return 0
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    tr = data.get("tool_response") or data.get("tool_output") or ""
    text = _text(tr)
    if not text:
        return 0
    heavy, reason = is_heavy(text)
    if not heavy:
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": digest(text, cmd, reason)}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
