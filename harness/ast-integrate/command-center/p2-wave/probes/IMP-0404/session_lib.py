"""Shared session-smoke helpers for IMP-0404 probes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "IMP-0404.json"
SENTINEL = "SENTINEL:IMP-0404:ROUTER-HOOK-FAIL-OPEN"
PROMPT_HOOK = REPO / "hooks" / "_dispatch" / "prompt_submit.py"
PRETOOL_HOOK = REPO / "hooks" / "_dispatch" / "pre_tool.py"
EVENTS = HERE / "fixtures" / "session_events.json"
MUTANT_DIR = HERE / "fixtures" / "deployed-mutant" / "hooks" / "_dispatch"
# Hook surface only. select.py is the fault seam and may raise SystemExit(2)
# so the wrapper can catch it; that raise must not appear in these files.
PRODUCTION_PY = (
    REPO / "tools" / "router" / "hook_contract.py",
    REPO / "hooks" / "_dispatch" / "run.py",
    REPO / "hooks" / "_dispatch" / "prompt_submit.py",
    REPO / "hooks" / "_dispatch" / "pre_tool.py",
)
SELECT_PY = REPO / "tools" / "router" / "select.py"


def require_receipt() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0404 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0404 sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0404 self-declared:{st}")
    return doc


def load_events() -> list[dict[str, Any]]:
    data = json.loads(EVENTS.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) < 2:
        raise SystemExit("FAILED:IMP-0404 session fixture missing")
    return data


def hook_for(event: dict[str, Any]) -> Path:
    name = str(event.get("hook_event_name") or "")
    if "Prompt" in name or "prompt" in name:
        return PROMPT_HOOK
    return PRETOOL_HOOK


def run_hook(
    script: Path,
    event: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy() if env is None else dict(env)
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        merged.update(extra_env)
    return subprocess.run(
        [sys.executable, "-B", str(script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=merged,
        timeout=30,
    )


def parse_stdout(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        doc = json.loads(text.splitlines()[-1])
    except json.JSONDecodeError:
        return {"_unparsed": text[:400]}
    return doc if isinstance(doc, dict) else {"_unparsed": text[:400]}


def read_log(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def smoke_session(
    *,
    fault: str = "",
    log_path: Path,
    home: Path | None = None,
    canary: Path | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["IMP0404_HOOK_LOG"] = str(log_path)
    if fault:
        env["IMP0404_ROUTER_FAULT"] = fault
    else:
        env.pop("IMP0404_ROUTER_FAULT", None)
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
    if canary is not None:
        env["IMP0404_DEPLOYED_CANARY"] = str(canary)
    if log_path.exists():
        log_path.unlink()
    events = load_events()
    runs = []
    for ev in events:
        proc = run_hook(hook_for(ev), ev, env=env)
        payload = parse_stdout(proc.stdout)
        runs.append(
            {
                "event": ev.get("hook_event_name"),
                "tool_name": ev.get("tool_name"),
                "returncode": proc.returncode,
                "payload": payload,
                "stderr_tail": (proc.stderr or "")[-400:],
            }
        )
    log_rows = read_log(log_path)
    exit_codes = [r["returncode"] for r in runs]
    log_exits = [int(r.get("exit_code") or 0) for r in log_rows]
    deny = []
    for r in runs:
        p = r["payload"]
        for key in ("permissionDecision", "decision"):
            if str(p.get(key) or "").lower() in {"deny", "block"}:
                deny.append(r)
        hso = (
            p.get("hookSpecificOutput")
            if isinstance(p.get("hookSpecificOutput"), dict)
            else {}
        )
        if str(hso.get("permissionDecision") or "").lower() in {"deny", "block"}:
            deny.append(r)
    return {
        "runs": runs,
        "log_rows": log_rows,
        "exit_codes": exit_codes,
        "log_exits": log_exits,
        "all_exit_zero": all(c == 0 for c in exit_codes) and len(exit_codes) == len(events),
        "zero_exit2_process": all(c != 2 for c in exit_codes),
        "zero_exit2_log": all(c != 2 for c in log_exits),
        "no_deny": not deny,
        "n_events": len(events),
        "canary_present": bool(canary and canary.is_file()),
    }


def leaky_twin_exit() -> int:
    """Known-bad twin: a router raise becomes exit 2. Detector must fire here."""
    script = (
        "import sys\n"
        "try:\n"
        "    raise RuntimeError('forced-router-exception')\n"
        "except Exception:\n"
        "    sys.exit(2)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode
