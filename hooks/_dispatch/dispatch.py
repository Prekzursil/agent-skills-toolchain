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

2026-10-18 review-thread hardening (PR #374 Codex review):
  * exec-mode children are TREE-KILLED on timeout (`taskkill /T /F` on Windows,
    `killpg` on POSIX) — `subprocess.run`'s leaf-only kill left orphaned guard
    children behind on Windows, and repeated calls accumulated processes.
  * a successful `blocking_rc` check's stderr is forwarded (break-glass bypass
    notices, e.g. no-force-push under FORGE_NO_FORCE_PUSH_OFF, stay visible).
  * a forwarded/denied decision JSON now CARRIES the aggregated advisory context
    of the other selected checks instead of discarding it.
  * a non-timeout exec launch failure (OSError etc.) emits a `launch-failed`
    receipt instead of silently failing open with rc=None.
"""

from __future__ import annotations

import importlib.util
import inspect
import io
import json
import os
import re
import subprocess
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


def _tree_kill(pid: int | None) -> None:
    """Kill a subprocess AND its whole descendant tree (best effort, 2026-10-18 P1).

    ``Popen.kill``/``subprocess.run``'s timeout kill terminate only the leaf
    process. The exec-mode guards spawn their own children (git scans, monitors),
    and on Windows those children survive the leaf's death as orphans — measured
    with a sleeping guard whose grandchild outlived the dispatcher. Windows has no
    process groups for arbitrary trees, so `taskkill /T /F` walks the PID tree;
    POSIX children are placed in their own session (``start_new_session``) and
    killed by group. Fails soft: a process that already exited is not an error.
    """
    if not isinstance(pid, int) or pid <= 0:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=10,
            )
        except BaseException:
            pass
        return
    try:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    except BaseException:
        pass


def _exec_worker(path: str, args, payload_json: str, buf: io.StringIO,
                 err_buf: io.StringIO, rc_sink: list, budget: float,
                 pid_sink: list | None = None) -> None:
    """Run one check as a SUBPROCESS in its own thread (2026-10-17 blocking-mode wave).

    WHY exec mode exists: the blocking guards (no-force-push, test-tamper-guard,
    ulysses, deny-credential-reads, estate-deny-guard) are standalone hook scripts
    with bare top-level ``sys.exit(main())`` and their own stdin/exit-code contract;
    importing them in-process would fire main() at import time under the wrong argv.
    A subprocess preserves their exact standalone semantics (own interpreter, own
    stdin/stdout/stderr, real exit code) while still collapsing N settings.json
    hook entries into ONE dispatcher invocation.

    2026-10-18 P1/P2 hardening:
    * The child is started detached into its own session/process context and its
      PID is published to ``pid_sink`` immediately, so BOTH the worker's own
      ``communicate(timeout=...)`` expiry AND an abandoned-worker join in
      ``run()`` can TREE-KILL it (see ``_tree_kill``). A leaf-only kill left
      orphaned guard children behind on Windows.
    * A non-timeout launch failure (``OSError`` starting the child, decode
      errors) records the ``LAUNCH-FAILED`` sentinel instead of leaving
      ``rc_sink`` empty — the empty state previously produced a silent rc=None
      fail-open with no receipt (the P2 "unattested launch failure" thread).
    """
    proc = None
    try:
        popen_kwargs: dict = {}
        if os.name == "nt":
            # A fresh process group keeps CTRL_C/CTRL_BREAK delivery to the
            # dispatcher itself from reaching the child; the tree kill uses
            # taskkill /T (PID-tree walk), which needs no group.
            popen_kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            # Own session => killpg can take the whole tree down synchronously.
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            [sys.executable, path, *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(Path(path).parent), **popen_kwargs,
        )
        if pid_sink is not None:
            pid_sink.append(proc.pid)
        out, err = proc.communicate(input=payload_json, timeout=max(1.0, budget))
        buf.write(out or "")
        err_buf.write(err or "")
        rc_sink.append(proc.returncode)
    except subprocess.TimeoutExpired:
        if proc is not None:
            _tree_kill(proc.pid)
            try:
                proc.wait(timeout=10)  # reap; never leave a zombie behind
            except BaseException:
                pass
        rc_sink.append("TIMEOUT")
    except BaseException:
        # Launch/read failure (OSError, decode): fail open but LEAVE A TRACE.
        # An empty rc_sink reads as rc=None downstream with no receipt, which
        # is indistinguishable from a healthy quiet check (P2 review thread).
        if proc is not None:
            _tree_kill(proc.pid)
            try:
                proc.wait(timeout=10)
            except BaseException:
                pass
        rc_sink.append("LAUNCH-FAILED")


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


def run(event: str, raw_payload: str, manifest: dict, collect: list | None = None) -> str | None:
    """Core: returns the aggregated additionalContext for the event (or None).

    ``collect``, when a list is passed, receives one record per finished check:
    ``{"chk": <manifest check>, "rc": <would-be exit code or None>,
    "out": <captured stdout>, "err": <captured stderr, exec-mode checks only>}``.
    main() uses the records to propagate BLOCK/decision results (2026-10-17
    blocking mode); passing nothing keeps the historical inject-only contract.
    """
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
    # exec-mode checks (chk["exec"] is truthy) need no import: they run as subprocesses.
    loaded = []  # entry dicts: chk, mod (None for exec), buf, err, rc_sink, path, pid_sink
    for chk in matched:
        try:
            if chk.get("exec"):
                if chk.get("exec_path"):
                    # Explicit absolute target (owner-reviewed): same power as a
                    # settings.json hook command, just consolidated behind dispatch.
                    path = str(chk["exec_path"])
                    if not Path(path).is_file():
                        _receipt(event, _check_label(chk), "load-failed")
                        continue
                else:
                    path = _resolve_script(root, chk["script"])
                    if path is None:
                        _receipt(event, _check_label(chk), "out-of-root")
                        continue
                loaded.append({"chk": chk, "mod": None, "buf": io.StringIO(),
                               "err": io.StringIO(), "rc": [], "path": path,
                               "pid": []})
                continue
            path = _resolve_script(root, chk["script"])
            if path is None:
                # escapes hooks_root -> never imported (see module docstring)
                _receipt(event, _check_label(chk), "out-of-root")
                continue
            uniq = "dispq_" + re.sub(r"\W", "_", str(chk.get("name") or chk["script"]))
            mod = _load_module(path, uniq)
            if mod is not None:
                loaded.append({"chk": chk, "mod": mod, "buf": io.StringIO(),
                               "err": io.StringIO(), "rc": [], "path": None})
            else:
                _receipt(event, _check_label(chk), "load-failed")
        except BaseException:
            _receipt(event, _check_label(chk), "load-failed")
            continue
    if not loaded:
        return None

    # Concurrent execution: thread-per-check, per-check deadline join.
    threads = []
    for entry in loaded:
        try:
            budget = float(entry["chk"].get("timeout") or 8)
        except (TypeError, ValueError):
            budget = 8.0
        if entry["path"] is not None:
            t = threading.Thread(
                target=_exec_worker,
                args=(entry["path"], entry["chk"].get("args") or [], raw_payload,
                      entry["buf"], entry["err"], entry["rc"], budget,
                      entry["pid"]),
                daemon=True,
            )
        else:
            t = threading.Thread(
                target=_worker,
                args=(entry["mod"], entry["chk"].get("args") or [],
                      entry["buf"], raw_payload, entry["rc"]),
                daemon=True,
            )
        t.start()
        threads.append(t)

    start = time.monotonic()
    pieces: list[str] = []
    for entry, t in zip(loaded, threads):
        chk = entry["chk"]
        try:
            budget = float(chk.get("timeout") or 8)
        except (TypeError, ValueError):
            budget = 8.0
        remaining = max(0.0, budget - (time.monotonic() - start))
        t.join(timeout=remaining)
        if t.is_alive():
            # timed out -> fail-open, drop this check's (incomplete) output
            _receipt(event, _check_label(chk), "timeout")
            if entry["path"] is not None:
                # The daemon worker may be abandoned before its own cleanup runs
                # (outer join and the worker's communicate() share the deadline).
                # Tree-kill the published PID here so an orphaned exec guard
                # cannot outlive the dispatcher (2026-10-18 P1 thread).
                if entry.get("pid"):
                    _tree_kill(entry["pid"][0])
            continue
        rc_val = entry["rc"][0] if entry["rc"] else None
        if rc_val == "TIMEOUT":
            # exec-mode child was killed by subprocess timeout -> fail-open, attest loss
            _receipt(event, _check_label(chk), "timeout")
            continue
        if rc_val == "LAUNCH-FAILED":
            # exec-mode child could not be started / read (OSError etc.) ->
            # fail-open, but ATTEST it (2026-10-18 P2 thread: rc=None used to be
            # indistinguishable from a healthy quiet check).
            _receipt(event, _check_label(chk), "launch-failed")
            continue
        rec_ctx: list[str] = []
        try:
            rec_ctx = _extract_ctx(entry["buf"].getvalue())
            pieces.extend(rec_ctx)
        except BaseException:
            _receipt(event, _check_label(chk), "output-unreadable")
            continue
        try:
            rc = _blocking_status(rc_val)
            if rc is not None and not chk.get("blocking_rc"):
                note = _disarmed_note(
                    str(chk.get("name") or chk.get("script")), rc
                )
                pieces.append(note)
                rec_ctx.append(note)
        except BaseException:
            pass
        if collect is not None:
            try:
                # "ctx" carries this check's own contribution to the aggregate
                # (context pieces + any disarmed-gate note) so main() can merge
                # the OTHER checks' context into a forwarded decision without
                # re-parsing stdout and without duplicating the decision check's
                # own output (2026-10-18 P1b/MEDIUM threads).
                collect.append({"chk": chk, "rc": rc_val,
                                "out": entry["buf"].getvalue(),
                                "err": entry["err"].getvalue(),
                                "ctx": rec_ctx})
            except BaseException:
                pass

    return "\n".join(pieces) if pieces else None


def _merged_decision(obj: dict, extra_ctx: str | None) -> dict:
    """Fold ``extra_ctx`` into a decision JSON's additionalContext (2026-10-18).

    The standalone hooks each delivered their own output; consolidation must not
    make advisory context (Ulysses nudges, loop-recovery warnings) vanish just
    because a decision JSON wins the output slot. ``additionalContext`` is a
    generic hookSpecificOutput field the host accepts alongside a
    permissionDecision/updatedInput, so the aggregate rides in the same object.
    Appends to (never replaces) any additionalContext the decision itself carries.
    """
    if not extra_ctx:
        return obj
    hso = obj.get("hookSpecificOutput")
    if not isinstance(hso, dict):
        return obj
    existing = hso.get("additionalContext")
    if isinstance(existing, str) and existing.strip():
        hso["additionalContext"] = f"{existing}\n{extra_ctx}"
    else:
        hso["additionalContext"] = extra_ctx
    return obj


def _other_checks_context(records: list, exclude_chk: object) -> str | None:
    """The aggregated context of every check EXCEPT ``exclude_chk``.

    Excluding the decision's own check prevents its context from being merged
    back on top of itself (its additionalContext already lives in the decision
    object being forwarded).
    """
    parts: list[str] = []
    for r in records or []:
        chk = r.get("chk") or {}
        if chk is exclude_chk:
            continue
        parts.extend(r.get("ctx") or [])
    return "\n".join(parts) if parts else None


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

        records: list = []
        agg = run(event, raw, manifest, collect=records)

        # 2026-10-17 blocking mode: propagate BLOCK/decision results instead of
        # disarming them. Precedence mirrors Claude Code's own multi-hook merge:
        # exit-code BLOCK (rc!=0 + stderr) > JSON deny > JSON allow/rewrite > context.
        block = None    # (rc, stderr_text, name)
        deny = None     # decision JSON object (permissionDecision: deny)
        deny_chk = None
        forward = None  # first allow/ask/rewrite decision JSON
        forward_chk = None
        for r in records:
            chk = r.get("chk") or {}
            rc = r.get("rc")
            out, err = r.get("out") or "", r.get("err") or ""
            if chk.get("blocking_rc") and isinstance(rc, int) and rc != 0 and block is None:
                block = (rc, err, str(chk.get("name") or chk.get("script")))
            if chk.get("decision"):
                for line in out.splitlines():
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
                    if not isinstance(hso, dict):
                        continue
                    d = hso.get("permissionDecision")
                    if d == "deny" and deny is None:
                        deny = obj
                        deny_chk = chk
                    elif forward is None and (d in ("allow", "ask")
                                              or hso.get("updatedInput") is not None
                                              or hso.get("updatedCommand") is not None):
                        forward = obj
                        forward_chk = chk
                    break  # first decision JSON on this check's stdout wins

        # 2026-10-18 P1 (bypass-notice thread): a SUCCESSFUL blocking_rc check
        # may still have something to say on stderr — no-force-push under
        # FORGE_NO_FORCE_PUSH_OFF / .disabled writes its break-glass notice to
        # both streams and exits 0, and the plaintext stdout is dropped by
        # _extract_ctx, so without this pass the allowed force-push would be
        # completely silent. stderr is the diagnostic channel; the stdout JSON
        # contract is untouched. (The rc!=0 block path below forwards its own
        # stderr, and rc==0 records never feed it, so nothing is sent twice.)
        for r in records:
            chk = r.get("chk") or {}
            rc = r.get("rc")
            err = r.get("err") or ""
            if (chk.get("exec") and chk.get("blocking_rc")
                    and isinstance(rc, int) and rc == 0 and err.strip()):
                try:
                    sys.stderr.write(err if err.endswith("\n") else err + "\n")
                    sys.stderr.flush()
                except Exception:
                    pass

        if block is not None:
            # exit-code blocking protocol: stderr reason is fed back by the host
            if block[1]:
                try:
                    sys.stderr.write(block[1] if block[1].endswith("\n") else block[1] + "\n")
                    sys.stderr.flush()
                except Exception:
                    pass
            return block[0]
        if deny is not None:
            # 2026-10-18: the aggregate rides WITH the decision instead of
            # being discarded by the early return (MEDIUM early-return thread).
            real_out.write(json.dumps(
                _merged_decision(deny, _other_checks_context(records, deny_chk))
            ) + "\n")
            real_out.flush()
            return 0
        if forward is not None:
            # 2026-10-18: same merge for allow/ask/rewrite forwards — an
            # inject-nopager rewrite must not silence the advisory context the
            # standalone hooks used to deliver alongside it (P1b thread).
            real_out.write(json.dumps(
                _merged_decision(forward, _other_checks_context(records, forward_chk))
            ) + "\n")
            real_out.flush()
            return 0
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
