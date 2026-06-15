#!/usr/bin/env python3
"""Stop hook: validate the files edited during this turn, ONCE, at turn end.

This is the loop-proof successor to the old per-Edit `async-validate` hook
(which woke the main session on every transient ruff-dirty edit -> degenerate
loop in workflow sessions). Here validation runs only at the Stop boundary, so:

  * a turn with 1 edit or 1000 edits triggers exactly ONE validation pass
  * it can NEVER wake-loop on transient mid-edit WIP

LOOP-PROOFNESS (three independent guards):
  1. Fires only at Stop (once per turn), never per edit.
  2. Dedupe: a (file, error-signature) is nudged AT MOST ONCE per session
     (persisted in <session>.warned), so the same breakage never re-blocks.
  3. If `stop_hook_active` is true (we are already inside a stop-continuation),
     never block — just exit 0. This caps any chain at a single extra turn.

Behaviour: if a freshly-edited file is genuinely broken (py_compile / ruff /
node --check / json) AND that exact error hasn't been nudged this session AND
we're not already in a stop-continuation, emit a one-shot block nudging a fix.
Otherwise exit 0 (silent). FAIL-OPEN: any internal error -> exit 0.

Opt-outs: env STOP_VALIDATE=off, or a `.disabled` sentinel file in this dir.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOKDIR = os.path.dirname(os.path.abspath(__file__))


def _validate(fp):
    """Return (kind, message) if the file is broken, else None. Fail-open -> None."""
    if not os.path.isfile(fp):
        return None
    ext = os.path.splitext(fp)[1].lower()
    try:
        if ext == ".py":
            r = subprocess.run([sys.executable, "-m", "py_compile", fp],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30)
            if r.returncode != 0:
                tail = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
                return ("py_compile", tail[-1] if tail else "syntax error")
            ruff = shutil.which("ruff")
            if ruff:
                r2 = subprocess.run([ruff, "check", "--quiet", fp],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=30)
                if r2.returncode != 0:
                    out = [ln for ln in ((r2.stdout or "") + (r2.stderr or "")).splitlines() if ln.strip()]
                    return ("ruff", out[0] if out else "lint error")
        elif ext in (".js", ".mjs", ".cjs"):
            node = shutil.which("node")
            if node:
                r = subprocess.run([node, "--check", fp],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=30)
                if r.returncode != 0:
                    tail = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
                    return ("node", tail[0] if tail else "parse error")
        elif ext == ".json":
            with open(fp, encoding="utf-8", errors="replace") as fh:
                json.load(fh)
    except json.JSONDecodeError as e:
        return ("json", str(e))
    except Exception:
        return None
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        # opt-outs
        if os.environ.get("STOP_VALIDATE", "").lower() == "off":
            return 0
        if os.path.exists(os.path.join(HOOKDIR, ".disabled")):
            return 0
        # guard 3: never block during a stop-continuation
        if data.get("stop_hook_active"):
            return 0

        sid = str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")
        d = os.path.join(tempfile.gettempdir(), "edit-validate")
        edits_path = os.path.join(d, f"{sid}.edits")
        warned_path = os.path.join(d, f"{sid}.warned")
        if not os.path.isfile(edits_path):
            return 0

        with open(edits_path, encoding="utf-8", errors="replace") as f:
            files = list(dict.fromkeys(ln.strip() for ln in f if ln.strip()))
        # consume the list so the next turn starts fresh (idempotent regardless of outcome)
        try:
            os.remove(edits_path)
        except OSError:
            pass

        warned = set()
        if os.path.isfile(warned_path):
            with open(warned_path, encoding="utf-8", errors="replace") as f:
                warned = {ln.strip() for ln in f if ln.strip()}

        fresh_failures = []
        for fp in files:
            res = _validate(fp)
            if not res:
                continue
            kind, msg = res
            sig = hashlib.sha1(f"{fp}|{kind}|{msg}".encode("utf-8", "replace")).hexdigest()[:16]
            if sig in warned:
                continue  # guard 2: already nudged this exact breakage
            warned.add(sig)
            fresh_failures.append((fp, kind, msg))

        if not fresh_failures:
            return 0

        # persist the warned-set so we never re-nudge the same breakage
        try:
            with open(warned_path, "w", encoding="utf-8", errors="replace") as f:
                f.write("\n".join(sorted(warned)))
        except OSError:
            pass

        lines = [f"- {os.path.basename(fp)} [{kind}]: {msg}" for fp, kind, msg in fresh_failures]
        reason = ("[edit-validate] You left file(s) edited this turn in a broken state:\n"
                  + "\n".join(lines)
                  + "\n\nFix the source (do not weaken the check). This nudge fires at most once "
                    "per distinct error; if intentional/WIP, end again and it will not re-block.")
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
