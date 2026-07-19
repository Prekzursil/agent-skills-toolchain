#!/usr/bin/env python
"""PostToolUse hook — fresh-context verifier TRIGGER (the F2 wrong-but-consistent anchor residual).

The single failure mode SELF-CALIBRATION-PLAN admits nothing else catches: a VALUE (hex address /
offset) that is WRONG but reused consistently for many steps, so every downstream conclusion inherits
the error. anti-degen/fingerprint.py catches MECHANICAL spin (same call, same output); this catches a
STABLE WRONG VALUE. When a load-bearing value has appeared in >= REUSE_THRESHOLD tool-arg occurrences
and no verify has fired for it, inject a one-shot directive to invoke the `fresh-context-verify` skill
(a SEPARATE clean-context model call that JUDGES). The hook never judges.

Scoped to the RE matcher (ida / cheatengine / ghidra) where addresses are load-bearing across long
loops, so interactive / non-RE sessions are never touched. Fail-open (exit 0).

Opt-out:  FRESH_VERIFY=off  in env, or  hooks/fresh-verify/.disabled
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get("FRESH_VERIFY_ROOT", str(Path.home() / ".claude" / "fresh-verify"))
)
THIS = Path(__file__).resolve().parent
REUSE_THRESHOLD = (
    8  # a value load-bearing in >= this many tool-arg occurrences triggers a re-derive
)
# load-bearing value = a hex address/offset (the dominant reused anchor in RE loops)
VALUE_RE = re.compile(r"0x[0-9a-fA-F]{4,}")


def _file(session_id: str) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    safe = (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[:80]
        or "unknown"
    )
    return ROOT / f"{safe}.json"


def _load(session_id: str) -> dict:
    try:
        d = json.loads(_file(session_id).read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {"counts": {}, "fired": []}


def _save(session_id: str, state: dict) -> None:
    try:
        _file(session_id).write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def main() -> int:
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "FRESH_VERIFY", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        sid = str(data.get("session_id") or "unknown")
        try:
            blob = json.dumps(
                data.get("tool_input") or {}, ensure_ascii=False, default=repr
            )
        except Exception:
            blob = repr(data.get("tool_input"))
        values = set(VALUE_RE.findall(blob.lower()))
        if not values:
            return 0
        state = _load(sid)
        counts = state.setdefault("counts", {})
        fired = set(state.get("fired", []))
        hit = None
        for v in values:
            counts[v] = int(counts.get(v, 0)) + 1
            if counts[v] >= REUSE_THRESHOLD and v not in fired:
                hit = v
        if hit:
            fired.add(hit)
        _save(sid, {"counts": counts, "fired": sorted(fired)})
        if hit:
            msg = (
                f"**[fresh-context verify - F2]** The value `{hit}` has been load-bearing across "
                f">= {REUSE_THRESHOLD} tool calls with no INDEPENDENT check. If it is wrong, every "
                f"downstream step has inherited the error (the wrong-but-consistent anchor that "
                f"anti-degen cannot see). Invoke the `fresh-context-verify` skill to re-derive `{hit}` "
                f"in a CLEAN context that cannot inherit this reasoning; HALT and reconcile if it "
                f"disagrees. Do not simply re-assert it."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": msg,
                        }
                    }
                )
            )
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
