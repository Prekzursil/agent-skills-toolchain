#!/usr/bin/env python3
r"""_dispatch/dispatch.py — per-event hook DISPATCHER (latency consolidation).

ONE invocation per event replaces N separate `python <hook>.py` spawns. Claude Code
calls:  python C:/Users/Prekzursil/.claude/hooks/_dispatch/dispatch.py <event>
where <event> is one of: sessionstart | stop | posttooluse | pretooluse  (aliases
posttool/pretool accepted; case-insensitive).

WHAT IT DOES
  1. Reads the hook JSON on stdin ONCE.
  2. Looks up the event's checks in manifest.json (the single place checks are listed —
     adding a future check = one manifest line).
  3. Runs each check whose `matcher` (regex on tool_name; absent/None = always) matches,
     IN-PROCESS, each in its own daemon thread with a per-check timeout (thread-join), so
     one slow check (wire-check's ripgrep) cannot block the rest. Every check is wrapped
     try/except -> FAIL-OPEN.
  4. AGGREGATES every check's hookSpecificOutput.additionalContext into ONE
     hookSpecificOutput.additionalContext for the event (newline-joined, manifest order),
     emitted on real stdout. If nothing was produced, prints nothing.

HOW IN-PROCESS EXECUTION STAYS EQUIVALENT TO THE STANDALONE HOOKS
  Each consolidated hook is a stdin->JSON-out script with a `main()` (a few take a mode
  argv like ["sessionstart"]). The dispatcher imports the module and calls its EXACT
  `main()` with:
    * sys.stdin  routed (per-thread) to a fresh StringIO of the original payload, and
    * sys.stdout routed (per-thread) to a private buffer it then parses.
  This re-runs the shipped code path verbatim (its own .disabled / env opt-out, its
  stop_hook_active anti-loop, its internal tool_name gate, its file side-effects) — only
  the I/O is plumbed. Per-thread routing (threading.local) means concurrent checks — and
  any timed-out/abandoned daemon thread — never clobber each other's stdout.

ISOLATION
  bg-registry/* and memory-spool/* each import a DIR-LOCAL `_common`; stub-ledger/* import
  a sibling `stubscan`. These collide by bare name across dirs. Before importing each
  module we pop those names from sys.modules; the module's own top-level
  `sys.path.insert(0, THIS)` (which every such module does BEFORE its `import _common`)
  then re-resolves the name against its own directory. Each module is loaded under a
  unique synthetic name so filename collisions (wire-check/check.py vs honest-signal/
  check.py) don't clash.

SAFETY
  FAIL-OPEN at every level (try/except -> exit 0). Master opt-out: HOOK_DISPATCH=off in
  env, or a _dispatch/.disabled file (disables the whole consolidated set; per-check
  opt-outs still work individually). Pure stdlib. Never blocks (exit 0 only) — the
  consolidated checks are all inject-only; none ever returned exit 2.
"""
from __future__ import annotations

import importlib.util
import inspect
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MANIFEST = THIS / "manifest.json"

# Dir-local shared module names that collide across hook dirs; popped before each import
# so every module re-binds its own dir's copy.
_SHARED_NAMES = ("_common", "stubscan")

# Canonical Claude Code event names keyed by the CLI token (and its aliases).
_EVENT_ALIASES = {
    "sessionstart": "SessionStart",
    "stop": "Stop",
    "posttooluse": "PostToolUse",
    "posttool": "PostToolUse",
    "pretooluse": "PreToolUse",
    "pretool": "PreToolUse",
}

# Per-thread I/O routing so concurrent checks don't share global sys.stdin/sys.stdout.
_tls = threading.local()


class _ThreadStdout:
    """sys.stdout proxy: route writes to the current thread's buffer if it set one,
    else to the real stdout. Lets concurrent (and abandoned) check threads each keep
    their own output without a race on the process-global stream."""

    def __init__(self, real):
        self._real = real

    def _target(self):
        buf = getattr(_tls, "out", None)
        return buf if buf is not None else self._real

    def write(self, s):
        return self._target().write(s)

    def flush(self):
        try:
            self._target().flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._target(), name)


class _ThreadStdin:
    """sys.stdin proxy: route reads to the current thread's payload buffer if set."""

    def __init__(self, real):
        self._real = real

    def _target(self):
        buf = getattr(_tls, "inp", None)
        return buf if buf is not None else self._real

    def read(self, *a):
        return self._target().read(*a)

    def readline(self, *a):
        return self._target().readline(*a)

    def readlines(self, *a):
        return self._target().readlines(*a)

    def __iter__(self):
        return iter(self._target())

    def __getattr__(self, name):
        return getattr(self._target(), name)


def _disabled() -> bool:
    try:
        if DISABLED.exists():
            return True
    except Exception:
        pass
    return os.environ.get("HOOK_DISPATCH", "").lower() in ("off", "0", "false")


def _canon_event(token: str) -> str | None:
    return _EVENT_ALIASES.get(str(token or "").strip().lower())


def _load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_module(script_path: str, uniq_name: str):
    """Import a hook module fresh under a unique name, isolating dir-local shared names."""
    for shared in _SHARED_NAMES:
        sys.modules.pop(shared, None)
    spec = importlib.util.spec_from_file_location(uniq_name, script_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uniq_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _call_main(mod, args) -> None:
    """Invoke the module's main(), passing argv only if it accepts a parameter."""
    fn = getattr(mod, "main", None)
    if fn is None:
        return
    try:
        nparams = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        nparams = 0
    if nparams >= 1:
        fn(list(args))
    else:
        fn()


def _worker(mod, args, buf: io.StringIO, payload_json: str) -> None:
    """Run one check in its own thread: route I/O thread-locally, call main(), fail-open."""
    try:
        _tls.out = buf
        _tls.inp = io.StringIO(payload_json)
        _call_main(mod, args)
    except BaseException:
        pass  # fail-open: a check must never crash the dispatcher


def _extract_ctx(text: str) -> list[str]:
    """Pull additionalContext strings out of a check's captured stdout (tolerant)."""
    out: list[str] = []
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        hso = obj.get("hookSpecificOutput")
        if isinstance(hso, dict) and hso.get("additionalContext"):
            out.append(str(hso["additionalContext"]))
        elif obj.get("additionalContext"):  # tolerate a flat shape
            out.append(str(obj["additionalContext"]))
    return out


def _select(checks: list, tool_name: str) -> list:
    """Keep checks whose matcher (regex on tool_name; absent/None = always) matches."""
    sel = []
    for chk in checks or []:
        mt = chk.get("matcher")
        if mt and not re.search(mt, tool_name or ""):
            continue
        sel.append(chk)
    return sel


def run(event: str, raw_payload: str, manifest: dict) -> str | None:
    """Core: returns the aggregated additionalContext for the event (or None)."""
    ev = (manifest.get("events") or {}).get(event)
    if not ev:
        return None
    try:
        payload = json.loads(raw_payload or "{}")
    except Exception:
        payload = {}
    tool = str((payload or {}).get("tool_name") or "")
    matched = _select(ev.get("checks") or [], tool)
    if not matched:
        return None

    root = manifest.get("hooks_root") or str(THIS.parent)

    # Serial imports (cheap; keeps the _common/stubscan sys.modules pop race-free).
    loaded = []  # (chk, module, buffer)
    for chk in matched:
        try:
            path = os.path.join(root, chk["script"])
            uniq = "dispq_" + re.sub(r"\W", "_", str(chk.get("name") or chk["script"]))
            mod = _load_module(path, uniq)
            if mod is not None:
                loaded.append((chk, mod, io.StringIO()))
        except BaseException:
            continue
    if not loaded:
        return None

    # Concurrent execution: thread-per-check, per-check deadline join.
    threads = []
    for chk, mod, buf in loaded:
        t = threading.Thread(
            target=_worker, args=(mod, chk.get("args") or [], buf, raw_payload), daemon=True)
        t.start()
        threads.append(t)

    start = time.monotonic()
    pieces: list[str] = []
    for (chk, _mod, buf), t in zip(loaded, threads):
        try:
            budget = float(chk.get("timeout") or 8)
        except (TypeError, ValueError):
            budget = 8.0
        remaining = max(0.0, budget - (time.monotonic() - start))
        t.join(timeout=remaining)
        if t.is_alive():
            continue  # timed out -> fail-open, drop this check's (incomplete) output
        try:
            pieces.extend(_extract_ctx(buf.getvalue()))
        except BaseException:
            continue

    return "\n".join(pieces) if pieces else None


def main(argv) -> int:
    real_out = sys.stdout
    try:
        if _disabled():
            return 0
        event = _canon_event(argv[0] if argv else "")
        if not event:
            return 0
        try:
            raw = sys.stdin.read() or "{}"
        except Exception:
            raw = "{}"
        manifest = _load_manifest()

        # Install per-thread I/O routing for the duration of check execution. The final
        # aggregate is written to real_out directly, so an abandoned daemon thread (which
        # keeps its own _tls.out buffer) can never corrupt it.
        sys.stdout = _ThreadStdout(real_out)
        sys.stdin = _ThreadStdin(sys.stdin)

        agg = run(event, raw, manifest)
        if agg:
            # ensure_ascii=True mirrors every consolidated hook's own json.dumps default
            # (pure-ASCII \uXXXX escaping) -> encoding-safe on any Windows console codepage.
            real_out.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": event, "additionalContext": agg}}) + "\n")
            real_out.flush()
    except BaseException:
        pass  # fail-open: never crash a session
    finally:
        try:
            sys.stdout = real_out
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
