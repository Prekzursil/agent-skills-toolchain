#!/usr/bin/env python3
"""Live hook dispatcher: fail-open on error, propagate exit 2 for danger.

Catalog input stand-in for hooks/_dispatch/dispatch.py (absent at repo root).
Hook subprocesses are wrapped so an injected exception or any non-2 failure
becomes session exit 0. A hook that actually decides a proposed operation is
irreversibly dangerous still returns 2 and the dispatcher stops the session.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "manifest.json"
DEFAULT_TIMEOUT = 8


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


INJECT_ENV = "TST0086_INJECT_AT_ENTRY"
SESSION_ENV = "TST0086_SESSION_DIR"
BLOCK_EXIT = 2


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), list):
        raise ValueError(f"manifest {path} has no hooks[]")
    return data


def matcher_hits(hook: dict[str, Any], payload: dict[str, Any]) -> bool:
    matcher = str(hook.get("matcher") or "*").strip()
    if matcher in {"", "*"}:
        return True
    tool = str(payload.get("tool_name") or "")
    return matcher == tool


def enabled_hooks(
    manifest: dict[str, Any], event: str, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    vocab = list(manifest.get("event_vocabulary") or [])
    out: list[dict[str, Any]] = []
    for row in manifest.get("hooks") or []:
        if not isinstance(row, dict) or not row.get("enabled", True):
            continue
        ev = str(row.get("event") or "")
        if vocab and ev not in vocab:
            raise ValueError(f"hook {row.get('id')} event {ev!r} not in vocabulary")
        if ev != event:
            continue
        if not matcher_hits(row, payload):
            continue
        interp = str(row.get("interpreter") or "").strip()
        script = str(row.get("script") or "").strip()
        hid = str(row.get("id") or "").strip()
        if not hid or not interp or not script:
            raise ValueError(f"hook row missing id/interpreter/script: {row}")
        out.append(row)
    return out


def interpreter_bin(declared: str) -> str:
    name = Path(declared).name.lower()
    if name in {"python", "python3", "py"}:
        return sys.executable
    return declared


def inject_code(script: Path, hook_id: str) -> str:
    return (
        "import runpy\n"
        f"raise RuntimeError({f'injected-exception-at-entry:{hook_id}'!r})\n"
        f"runpy.run_path({str(script)!r}, run_name='__main__')\n"
    )


def hook_command(
    hook: dict[str, Any],
    root: Path,
    inject_id: str | None,
) -> tuple[list[str], Path]:
    script = (root / str(hook["script"])).resolve()
    hid = str(hook["id"])
    interp = interpreter_bin(str(hook["interpreter"]))
    if inject_id and inject_id == hid:
        return [interp, "-c", inject_code(script, hid)], script
    return [interp, str(script)], script


def write_marker(session_dir: Path | None, name: str, body: str = "1") -> None:
    if session_dir is None:
        return
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / name).write_text(body, encoding="utf-8")


def invoke_hook(
    hook: dict[str, Any],
    root: Path,
    payload: dict[str, Any],
    *,
    inject_id: str | None,
    session_dir: Path | None,
    timeout: float,
) -> dict[str, Any]:
    hid = str(hook["id"])
    cmd, script = hook_command(hook, root, inject_id)
    write_marker(session_dir, f"{hid}.attempted", hid)
    raw_in = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            input=raw_in,
            capture_output=True,
            timeout=timeout,
            cwd=str(root),
            env={**os.environ, SESSION_ENV: str(session_dir or "")},
        )
        rc = int(proc.returncode)
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        timed_out = False
        error = None
    except subprocess.TimeoutExpired as exc:
        rc = 124
        stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
        timed_out = True
        error = "timeout"
    except OSError as exc:
        rc = 127
        stdout = ""
        stderr = str(exc)
        timed_out = False
        error = f"oserror:{exc.__class__.__name__}"
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    write_marker(session_dir, f"{hid}.rc", str(rc))
    injected = bool(inject_id and inject_id == hid)
    return {
        "id": hid,
        "event": hook.get("event"),
        "script": _rel(script, root),
        "command": cmd[:2] + (["<inject-at-entry>"] if injected else cmd[2:]),
        "process_exit": rc,
        "stdout": stdout[-2000:],
        "stderr": stderr[-2000:],
        "timed_out": timed_out,
        "error": error,
        "injected_exception": injected,
        "elapsed_ms": elapsed_ms,
        "script_exists": script.is_file(),
    }


def map_session_exit(process_exit: int, fail_open: bool) -> int:
    if process_exit == BLOCK_EXIT:
        return BLOCK_EXIT
    if process_exit == 0:
        return 0
    if fail_open:
        return 0
    return process_exit if process_exit != 0 else 1


def dispatch(
    payload: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    inject_id: str | None = None,
    fail_open: bool = True,
    session_dir: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    manifest_path = manifest_path or DEFAULT_MANIFEST
    root = manifest_path.parent
    manifest = load_manifest(manifest_path)
    event = str(payload.get("hook_event_name") or payload.get("event") or "")
    if not event:
        raise ValueError("payload missing hook_event_name")
    hooks = enabled_hooks(manifest, event, payload)
    rows: list[dict[str, Any]] = []
    session_exit = 0
    blocked_by = None
    continued_after_error = True
    for hook in hooks:
        row = invoke_hook(
            hook,
            root,
            payload,
            inject_id=inject_id,
            session_dir=session_dir,
            timeout=timeout,
        )
        mapped = map_session_exit(int(row["process_exit"]), fail_open=fail_open)
        row["mapped_session_exit"] = mapped
        row["fail_open_applied"] = bool(
            fail_open and int(row["process_exit"]) not in (0, BLOCK_EXIT)
        )
        rows.append(row)
        if mapped == BLOCK_EXIT:
            session_exit = BLOCK_EXIT
            blocked_by = row["id"]
            continued_after_error = False
            break
        if mapped != 0:
            session_exit = mapped
            continued_after_error = False
            break
        if int(row["process_exit"]) not in (0, BLOCK_EXIT) and fail_open:
            continued_after_error = True
    if session_exit == 0:
        write_marker(session_dir, "session.continued", "1")
    write_marker(session_dir, "dispatcher.exit", str(session_exit))
    later_ran = []
    if inject_id:
        seen_inject = False
        for row in rows:
            if row["id"] == inject_id:
                seen_inject = True
                continue
            if seen_inject:
                later_ran.append(row["id"])
    return {
        "event": event,
        "session_exit": session_exit,
        "blocked": session_exit == BLOCK_EXIT,
        "blocked_by": blocked_by,
        "fail_open": fail_open,
        "inject_id": inject_id,
        "hooks_selected": [str(h["id"]) for h in hooks],
        "hooks_run": [r["id"] for r in rows],
        "later_hooks_after_inject": later_ran,
        "session_continued": session_exit == 0,
        "continued_after_error": continued_after_error and session_exit == 0,
        "per_hook": rows,
        "manifest": str(manifest_path).replace("\\", "/"),
    }


def parse_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload:
        return json.loads(args.payload)
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    raw = sys.stdin.read()
    if not raw.strip():
        raise SystemExit("FAILED:dispatch missing payload")
    return json.loads(raw)


def main() -> int:
    p = argparse.ArgumentParser(description="TST-0086 fail-open hook dispatcher")
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--payload", default=None)
    p.add_argument("--payload-file", default=None)
    p.add_argument("--inject-at-entry", default=os.environ.get(INJECT_ENV) or None)
    p.add_argument("--no-fail-open", action="store_true")
    p.add_argument("--session-dir", default=None)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = p.parse_args()
    payload = parse_payload(args)
    result = dispatch(
        payload,
        manifest_path=Path(args.manifest),
        inject_id=args.inject_at_entry or None,
        fail_open=not args.no_fail_open,
        session_dir=Path(args.session_dir) if args.session_dir else None,
        timeout=args.timeout,
    )
    print(json.dumps(result, sort_keys=True))
    return int(result["session_exit"])


if __name__ == "__main__":
    raise SystemExit(main())
