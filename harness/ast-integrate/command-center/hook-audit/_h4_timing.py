r"""H4 — time EVERY wired dispatcher check against its own budget, plus the
whole-event dispatch against the settings.json budget.

TWO independent measurements (single-signal-verification §1):
  A. per-check, in-process, mirroring dispatch.py's exact call path
     (_load_module -> thread-local stdin/stdout -> main()). Split into
     LOAD ms (import, paid serially by the dispatcher BEFORE any per-check
     deadline starts) and RUN ms (what the per-check timeout actually guards).
  B. whole-event, as a real subprocess: `python dispatch.py <event> < payload`.
     This is the number the settings.json timeout guards, and it is the only
     one that includes interpreter startup.

Measurement A cannot see interpreter startup; measurement B cannot attribute
cost to a check. Neither alone answers "is this hook near its budget".

Runs against the LIVE hook tree by default (that is what actually executes);
pass --repo to time the repo tree instead.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import io
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path("C:/Users/Prekzursil/.claude/hooks")
OUT = REPO / "command-center" / "hook-audit"
_SHARED = ("_common", "stubscan")
_tls = threading.local()

# Payloads shaped like the real hook input for each event. transcript_path is
# deliberately absent/empty so nothing tries to parse a foreign session.
PAYLOADS = {
    "SessionStart": {"session_id": "hookaudit", "cwd": str(REPO), "source": "startup"},
    "Stop": {"session_id": "hookaudit", "cwd": str(REPO), "stop_hook_active": False},
    "PostToolUse": {
        "session_id": "hookaudit",
        "cwd": str(REPO),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(OUT / "_timing_scratch.txt")},
        "tool_response": {"success": True},
    },
    "PreToolUse": {
        "session_id": "hookaudit",
        "cwd": str(REPO),
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(OUT / "_timing_scratch.txt"),
            "old_string": "a",
            "new_string": "b",
        },
    },
}


class _TOut:
    def __init__(self, real):
        self._real = real

    def _t(self):
        b = getattr(_tls, "out", None)
        return b if b is not None else self._real

    def write(self, s):
        return self._t().write(s)

    def flush(self):
        try:
            self._t().flush()
        except Exception:
            pass

    def __getattr__(self, n):
        return getattr(self._t(), n)


class _TIn:
    def __init__(self, real):
        self._real = real

    def _t(self):
        b = getattr(_tls, "inp", None)
        return b if b is not None else self._real

    def read(self, *a):
        return self._t().read(*a)

    def readline(self, *a):
        return self._t().readline(*a)

    def readlines(self, *a):
        return self._t().readlines(*a)

    def __iter__(self):
        return iter(self._t())

    def __getattr__(self, n):
        return getattr(self._t(), n)


def load(path: Path, uniq: str):
    for s in _SHARED:
        sys.modules.pop(s, None)
    spec = importlib.util.spec_from_file_location(uniq, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uniq] = mod
    spec.loader.exec_module(mod)
    return mod


def call_main(mod, args):
    fn = getattr(mod, "main", None)
    if fn is None:
        return "NO-MAIN"
    try:
        n = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        n = 0
    return fn(list(args)) if n >= 1 else fn()


def time_checks(root: Path, tree_tag: str) -> list[dict]:
    man = json.loads((root / "_dispatch" / "manifest.json").read_text(encoding="utf-8"))
    hooks_root = Path(man.get("hooks_root") or root)
    rows = []
    real_out, real_in = sys.stdout, sys.stdin
    sys.stdout, sys.stdin = _TOut(real_out), _TIn(real_in)
    try:
        for event, blob in (man.get("events") or {}).items():
            payload = json.dumps(PAYLOADS.get(event, {"cwd": str(REPO)}))
            tool = json.loads(payload).get("tool_name") or ""
            for chk in (blob or {}).get("checks") or []:
                mt = chk.get("matcher")
                selected = not (mt and not re.search(mt, tool))
                name = chk.get("name") or chk.get("script")
                sp = (hooks_root / chk["script"]).resolve()
                row = {
                    "tree": tree_tag,
                    "event": event,
                    "name": name,
                    "script": chk["script"],
                    "budget_s": chk.get("timeout"),
                    "matcher": mt,
                    "selected_for_probe_tool": selected,
                    "exists": sp.is_file(),
                }
                if not sp.is_file():
                    row.update(load_ms=None, run_ms=None, rc="MISSING-SCRIPT")
                    rows.append(row)
                    continue
                t0 = time.perf_counter()
                try:
                    mod = load(sp, "tq_" + re.sub(r"\W", "_", str(name)))
                    lms = (time.perf_counter() - t0) * 1000
                except BaseException as e:
                    row.update(
                        load_ms=(time.perf_counter() - t0) * 1000,
                        run_ms=None,
                        rc=f"LOAD-FAIL:{type(e).__name__}",
                    )
                    rows.append(row)
                    continue
                buf = io.StringIO()
                _tls.out, _tls.inp = buf, io.StringIO(payload)
                t1 = time.perf_counter()
                try:
                    rc = call_main(mod, chk.get("args") or [])
                except BaseException as e:
                    rc = f"RUN-FAIL:{type(e).__name__}"
                rms = (time.perf_counter() - t1) * 1000
                _tls.out = _tls.inp = None
                emitted = buf.getvalue()
                row.update(
                    load_ms=round(lms, 1),
                    run_ms=round(rms, 1),
                    rc=rc if isinstance(rc, str) else repr(rc),
                    emitted_bytes=len(emitted),
                    emitted_ctx=bool(re.search(r"additionalContext", emitted)),
                )
                b = chk.get("timeout")
                row["pct_of_budget"] = (
                    round(100.0 * (rms / 1000.0) / b, 1) if b else None
                )
                rows.append(row)
    finally:
        sys.stdout, sys.stdin = real_out, real_in
    return rows


def time_events_subprocess(root: Path, tree_tag: str) -> list[dict]:
    man = json.loads((root / "_dispatch" / "manifest.json").read_text(encoding="utf-8"))
    disp = root / "_dispatch" / "dispatch.py"
    out = []
    for event, blob in (man.get("events") or {}).items():
        payload = json.dumps(PAYLOADS.get(event, {}))
        budget = (blob or {}).get("settings_timeout")
        t0 = time.perf_counter()
        p = subprocess.run(
            [sys.executable, str(disp), event.lower()],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=300,
        )
        ms = (time.perf_counter() - t0) * 1000
        so = p.stdout.decode("utf-8", "replace")
        se = p.stderr.decode("utf-8", "replace")
        out.append(
            {
                "tree": tree_tag,
                "event": event,
                "wall_ms": round(ms, 1),
                "settings_budget_s": budget,
                "pct_of_budget": round(100.0 * (ms / 1000.0) / budget, 1)
                if budget
                else None,
                "exit": p.returncode,
                "stdout_bytes": len(p.stdout),
                "stderr_bytes": len(p.stderr),
                "stderr_tail": se[-600:],
                "stdout_head": so[:400],
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="store_true")
    ap.add_argument("--subprocess-only", action="store_true")
    a = ap.parse_args()
    root, tag = (REPO / "hooks", "repo") if a.repo else (LIVE, "live")
    OUT.mkdir(parents=True, exist_ok=True)

    ev = time_events_subprocess(root, tag)
    print(
        f"== WHOLE-EVENT dispatch, {tag} tree (subprocess, includes interpreter start)"
    )
    for r in ev:
        flag = "!!" if (r["pct_of_budget"] or 0) > 60 else "  "
        print(
            f"{flag} {r['event']:14s} {r['wall_ms']:9.1f} ms / {str(r['settings_budget_s']):>4}s"
            f"  = {str(r['pct_of_budget']):>6}%  exit={r['exit']} out={r['stdout_bytes']}B"
            f" err={r['stderr_bytes']}B"
        )
        if r["stderr_tail"].strip():
            for ln in r["stderr_tail"].strip().splitlines()[-6:]:
                print(f"       stderr| {ln[:150]}")

    rows = [] if a.subprocess_only else time_checks(root, tag)
    if rows:
        print(f"\n== PER-CHECK, {tag} tree (in-process, mirrors dispatch.py)")
        for r in sorted(rows, key=lambda x: -(x.get("run_ms") or 0)):
            pct = r.get("pct_of_budget")
            flag = (
                "!!"
                if (pct or 0) > 50
                else ("SK" if not r["selected_for_probe_tool"] else "  ")
            )
            print(
                f"{flag} {r['event']:13s} {str(r['name'])[:30]:30s} "
                f"load={str(r.get('load_ms')):>8} run={str(r.get('run_ms')):>9} ms "
                f"/{str(r['budget_s']):>3}s = {str(pct):>6}%  rc={str(r.get('rc'))[:16]:16s} "
                f"ctx={r.get('emitted_ctx')}"
            )
    (OUT / f"H4-TIMING-{tag}.json").write_text(
        json.dumps({"events": ev, "checks": rows}, indent=2), encoding="utf-8"
    )
    print(f"\nSUCCESS:h4-timing-{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
