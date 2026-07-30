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
  opt-outs still work individually). Pure stdlib. Never blocks (exit 0 only).

  Two things are deliberately NOT fail-open, because failing open there means running
  the wrong code or losing a gate silently:

  * PATH CONTAINMENT. `manifest.json` is data. A `script` that resolves outside
    `hooks_root` ("../outside.py", "/abs/outside.py") is DROPPED, not imported —
    `_load_module` calls `exec_module`, so accepting such a path executes code from
    outside the configured hook tree at import time, before any per-check timeout.
  * BLOCK REQUESTS ARE NOT SWALLOWED. A consolidated check is supposed to be
    inject-only, but the manifest can (and does) list checks with a mode that returns
    a non-zero would-be exit code — journey-coverage/check.py returns 2 under
    JOURNEY_COVERAGE_MODE=block. The dispatcher cannot honour exit 2, so instead of
    discarding the result it appends an explicit note to additionalContext naming the
    check and its status. A disarmed gate must be visible, never silent.
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


def _resolve_script(root: str, script: str) -> str | None:
    """Resolve a manifest ``script`` under ``root``; return None if it escapes.

    ``manifest.json`` is DATA, and ``_load_module`` executes whatever path it is
    handed. ``os.path.join(root, "../outside.py")`` and
    ``os.path.join(root, "/abs/outside.py")`` both leave the configured hook tree,
    so they are rejected here rather than imported.
    """
    try:
        root_p = Path(root).resolve()
        candidate = (root_p / script).resolve()
    except (OSError, ValueError):
        return None
    if candidate == root_p or root_p not in candidate.parents:
        return None
    return str(candidate)


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


def _call_main(mod, args):
    """Invoke the module's main(), passing argv only if it accepts a parameter.

    Returns whatever ``main()`` returned — for a hook script that is its would-be
    process exit code, which the caller needs to detect a disarmed block request.
    """
    fn = getattr(mod, "main", None)
    if fn is None:
        return None
    try:
        nparams = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        nparams = 0
    return fn(list(args)) if nparams >= 1 else fn()


def _worker(mod, args, buf: io.StringIO, payload_json: str, rc_sink: list) -> None:
    """Run one check in its own thread: route I/O thread-locally, call main(), fail-open."""
    try:
        _tls.out = buf
        _tls.inp = io.StringIO(payload_json)
        rc_sink.append(_call_main(mod, args))
    except BaseException:
        pass  # fail-open: a check must never crash the dispatcher


def _blocking_status(rc: object) -> int | None:
    """The would-be non-zero exit code a check returned, or None if it did not."""
    if isinstance(rc, bool) or not isinstance(rc, int) or rc == 0:
        return None
    return rc


def _disarmed_note(name: str, rc: int) -> str:
    """Explain a block request the inject-only dispatcher could not honour."""
    return (
        f"[_dispatch] check {name!r} returned exit status {rc} — a BLOCK request. "
        "The dispatcher is inject-only, so nothing was blocked. Treat the check's "
        "own message above as its finding and act on it; to restore real blocking, "
        "move the check out of _dispatch/manifest.json into a standalone "
        "settings.json entry."
    )


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


RECEIPT_PREFIX = "[_dispatch]"


def _receipt(event: str, name: str, status: str) -> None:
    """Attest on stderr that a SELECTED check did not deliver (fail-open).

    C33 D-l02: every non-delivery path below (`_resolve_script` rejection, import
    failure, deadline overrun, unreadable buffer) used to be a bare ``continue``, so
    a matched-but-broken check was byte-identical on every observable channel to a
    healthy event that simply had nothing to say. Static registration plus a green
    direct-invocation test therefore never attested that the dispatcher actually
    selected, loaded, ran and delivered anything.

    Deliberately stderr, not stdout: stdout is the additionalContext channel the
    host parses as JSON, so a diagnostic there would corrupt the aggregate. Emitted
    ONLY for a check that was selected and then lost — never for a quiet healthy
    event, or the receipt becomes noise instead of signal (pinned by
    ``test_no_selected_check_is_silent``).

    SCOPE: dispatcher-side observability only. It does not prove the host invoked
    or delivered the hook; that needs a live Stop canary on the Windows host.
    """
    try:
        sys.stderr.write(
            f"{RECEIPT_PREFIX} event={event} check={name} status={status}\n"
        )
        sys.stderr.flush()
    except BaseException:
        pass  # attestation must never break a dispatch that is otherwise fine


def _check_label(chk: dict) -> str:
    """A stable identifier for a check in a receipt line."""
    return str(chk.get("name") or chk.get("script") or "?")


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
    loaded = []  # (chk, module, buffer, rc_sink)
    for chk in matched:
        try:
            path = _resolve_script(root, chk["script"])
            if path is None:
                # escapes hooks_root -> never imported (see module docstring)
                _receipt(event, _check_label(chk), "out-of-root")
                continue
            uniq = "dispq_" + re.sub(r"\W", "_", str(chk.get("name") or chk["script"]))
            mod = _load_module(path, uniq)
            if mod is not None:
                loaded.append((chk, mod, io.StringIO(), []))
            else:
                _receipt(event, _check_label(chk), "load-failed")
        except BaseException:
            _receipt(event, _check_label(chk), "load-failed")
            continue
    if not loaded:
        return None

    # Concurrent execution: thread-per-check, per-check deadline join.
    threads = []
    for chk, mod, buf, rc_sink in loaded:
        t = threading.Thread(
            target=_worker,
            args=(mod, chk.get("args") or [], buf, raw_payload, rc_sink),
            daemon=True,
        )
        t.start()
        threads.append(t)

    start = time.monotonic()
    pieces: list[str] = []
    for (chk, _mod, buf, rc_sink), t in zip(loaded, threads):
        try:
            budget = float(chk.get("timeout") or 8)
        except (TypeError, ValueError):
            budget = 8.0
        remaining = max(0.0, budget - (time.monotonic() - start))
        t.join(timeout=remaining)
        if t.is_alive():
            # timed out -> fail-open, drop this check's (incomplete) output
            _receipt(event, _check_label(chk), "timeout")
            continue
        try:
            pieces.extend(_extract_ctx(buf.getvalue()))
        except BaseException:
            _receipt(event, _check_label(chk), "output-unreadable")
            continue
        try:
            rc = _blocking_status(rc_sink[0] if rc_sink else None)
            if rc is not None:
                pieces.append(
                    _disarmed_note(str(chk.get("name") or chk.get("script")), rc)
                )
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
            real_out.write(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": event,
                            "additionalContext": agg,
                        }
                    }
                )
                + "\n"
            )
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
