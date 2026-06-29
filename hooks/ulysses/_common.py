#!/usr/bin/env python3
r"""ulysses/_common.py — shared layer for the Ulysses-tripwire pair (arm.py / enforce.py).

ULYSSES CONTRACT (self-binding): at task-start, while COLD/clear-headed, the agent
authors abort criteria ("tripwires"). The harness then enforces them against the LATER,
rationalizing self — operationalizing SELF-CALIBRATION-PLAN's law that self-correction
needs an EXTERNAL signal. The signal here is the transcript + the upcoming tool call,
which the in-context model cannot retroactively rewrite.

Store: ~/.claude/ulysses/tripwires.json
  {task, armed_ts, ttl_hours, predicates: [ {id, type, action, desc, ...params} ]}
  action ∈ ASK (inject) | HALT (exit-2 block) | SNAPSHOT (inject: checkpoint-first)

Predicate types (all CHEAP, stdlib-only, evaluated each PreToolUse):
  tool_match        pattern        upcoming tool_name matches  (e.g. live-game write)
  path_match        pattern        upcoming file_path / bash command matches
  path_reedit       threshold      about to edit a file for the Nth time this task
  calls_since_test  threshold      > N tool-calls since tests last PASSED (transcript)

Disarm guard: a direct Edit/Write/MultiEdit (or destructive shell op) on tripwires.json
is BLOCKED unless a fresh override was logged via `arm.py --override "<reason>"` — so the
agent cannot quietly weaken its own commitment mid-task. arm.py is the sanctioned mutator
and is exempt.

Honest limits: "passed" is a heuristic over the test command's transcript result text;
PreToolUse cannot run tests. True runtime coverage-drop is not cheaply knowable pre-call,
so coverage tripwires are expressed as path_match on the gate file (lowering the gate).

Pure stdlib. Every helper is fail-soft (safe default) so callers stay FAIL-OPEN.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path.home()
ULY_DIR = Path(os.environ.get("ULYSSES_DIR", str(HOME / ".claude" / "ulysses")))
TRIPWIRES_FILE = ULY_DIR / "tripwires.json"
OVERRIDES_FILE = ULY_DIR / "overrides.jsonl"

OVERRIDE_WINDOW_SEC = float(os.environ.get("ULYSSES_OVERRIDE_WINDOW_SEC", "600"))
TRANSCRIPT_TAIL_LINES = int(os.environ.get("ULYSSES_TRANSCRIPT_TAIL", "6000"))

EDIT_TOOLS = ("Edit", "Write", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
ACTIONS = ("ASK", "HALT", "SNAPSHOT")
PRED_TYPES = ("tool_match", "path_match", "path_reedit", "calls_since_test")

# Default "write to live game memory" pattern (cheatengine writes/patches + frida code
# injection). The user's RE work flagged forcing unverified fields into a live process as
# the canonical irreversible mistake (broke the Aku altar).
LIVE_WRITE_DEFAULT = (
    r"mcp__cheatengine__(write_memory|write_integer|write_string|auto_assemble)"
    r"|mcp__frida-mcp__(execute_in_session|create_simple_hook)"
)

_TEST_CMD = re.compile(
    r"\b(pytest|jest|vitest|mocha|rspec|phpunit|nose2|tox|ctest|"
    r"go\s+test|cargo\s+test|dotnet\s+test|gradle\s+test|mvn\s+test|"
    r"npm\s+(?:run\s+)?test|npx\s+jest|python\s+-m\s+(?:pytest|unittest)|"
    r"python\s+\S*test\S*\.py)\b",
    re.IGNORECASE,
)
_PASS_RX = re.compile(
    r"(\b\d+\s+passed\b|all tests? passed|\bALL PASS\b|\b0 failed\b|"
    r"\bPASS\b|build succeeded|\bSUCCESS\b|✓)",
    re.IGNORECASE,
)
_FAIL_RX = re.compile(
    r"(\b\d+\s+failed\b|\bFAILED\b|\bFAIL\b|\berrors?\b|assertionerror|"
    r"traceback|✗|exit\s*code\s*[1-9])",
    re.IGNORECASE,
)
_DESTRUCTIVE = re.compile(
    r"(\brm\b|\bdel\b|Remove-Item|\bmv\b|\bmove\b|Clear-Content|Set-Content|"
    r"Out-File|\btruncate\b|sed\s+-i|>\s*\"?[^>]*tripwires\.json|>\s*tripwires)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
def now() -> float:
    return time.time()


def emit(event_name: str, msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": msg}}))


def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def _norm(s) -> str:
    return str(s or "").replace("\\", "/").lower().strip()


# ---------------------------------------------------------------------------
# Store I/O
# ---------------------------------------------------------------------------
def load_tripwires():
    """Return the active tripwire store dict, or None when absent/expired/garbage.

    Expiry: armed_ts + ttl_hours has elapsed -> treated as disarmed (None). ttl_hours
    <= 0 means never expire. FAIL-SOFT: any read/parse error -> None (-> enforce silent)."""
    try:
        if not TRIPWIRES_FILE.exists():
            return None
        obj = json.loads(TRIPWIRES_FILE.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return None
        preds = obj.get("predicates")
        if not isinstance(preds, list):
            return None
        ttl = float(obj.get("ttl_hours") or 0)
        if ttl > 0:
            armed = float(obj.get("armed_ts") or 0)
            if armed and (armed + ttl * 3600.0) < now():
                return None  # expired -> disarmed
        return obj
    except Exception:
        return None


def save_tripwires(store: dict) -> bool:
    try:
        ULY_DIR.mkdir(parents=True, exist_ok=True)
        tmp = TRIPWIRES_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, TRIPWIRES_FILE)
        return True
    except Exception:
        return False


def log_override(reason: str) -> bool:
    try:
        ULY_DIR.mkdir(parents=True, exist_ok=True)
        with OVERRIDES_FILE.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps({"ts": now(), "reason": str(reason or "")}) + "\n")
        return True
    except Exception:
        return False


def override_active(window_sec: float = OVERRIDE_WINDOW_SEC) -> bool:
    """True if an override was logged within the recent window."""
    try:
        if not OVERRIDES_FILE.exists():
            return False
        cutoff = now() - window_sec
        for line in OVERRIDES_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if float(rec.get("ts") or 0) >= cutoff:
                return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# Transcript scanning (the external signal)
# ---------------------------------------------------------------------------
def _iso_to_epoch(ts) -> float:
    try:
        s = str(ts).replace("Z", "+00:00")
        from datetime import datetime
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def scan_transcript(transcript_path: str, since_ts: float | None = None) -> dict:
    """Fold the transcript into the counters enforce.py needs.

    Returns {tool_calls, edit_counts{path:n}, last_test_pass_idx, last_run_failed,
    calls_since_test}. since_ts (epoch) optionally scopes to events at/after arm time
    (best-effort: only applied when an event carries a parseable timestamp)."""
    res = {"tool_calls": 0, "edit_counts": {}, "last_test_pass_idx": None,
           "last_run_failed": False, "calls_since_test": 0}
    try:
        p = Path(transcript_path or "")
        if not transcript_path or not p.exists():
            return res
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-TRANSCRIPT_TAIL_LINES:]

        events = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                events.append(json.loads(ln))
            except Exception:
                continue

        # Map tool_use_id -> result text (from user tool_result blocks).
        result_text: dict[str, str] = {}
        for ev in events:
            msg = ev.get("message") or {}
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    tid = b.get("tool_use_id") or b.get("id")
                    if not tid:
                        continue
                    c = b.get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in c)
                    result_text[str(tid)] = str(c or "")

        idx = 0
        for ev in events:
            if since_ts:
                ets = _iso_to_epoch(ev.get("timestamp"))
                if ets and ets < since_ts:
                    continue
            msg = ev.get("message") or {}
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                idx += 1
                name = str(b.get("name") or "")
                inp = b.get("input") or {}
                if name in EDIT_TOOLS:
                    fp = _norm(inp.get("file_path"))
                    if fp:
                        res["edit_counts"][fp] = res["edit_counts"].get(fp, 0) + 1
                if name in SHELL_TOOLS:
                    cmd = str(inp.get("command") or "")
                    if _TEST_CMD.search(cmd):
                        rtext = result_text.get(str(b.get("id")), "")
                        passed = bool(_PASS_RX.search(rtext)) and not _FAIL_RX.search(rtext)
                        if passed:
                            res["last_test_pass_idx"] = idx
                            res["last_run_failed"] = False
                        else:
                            res["last_run_failed"] = True
        res["tool_calls"] = idx
        base = res["last_test_pass_idx"] or 0
        res["calls_since_test"] = idx - base
    except Exception:
        return res
    return res


# ---------------------------------------------------------------------------
# Disarm detection
# ---------------------------------------------------------------------------
def is_disarm_attempt(tool: str, tool_input: dict, command: str) -> bool:
    try:
        if tool in EDIT_TOOLS:
            fp = _norm((tool_input or {}).get("file_path"))
            return fp.endswith("ulysses/tripwires.json") or fp.endswith("/tripwires.json")
        if tool in SHELL_TOOLS:
            c = command or ""
            if "tripwires.json" not in c.lower():
                return False
            if "arm.py" in c.lower():
                return False  # the sanctioned mutator
            return bool(_DESTRUCTIVE.search(c))
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# The pure decision function (fully unit-testable)
# ---------------------------------------------------------------------------
def _trip_msg(pred: dict, extra: str = "") -> str:
    desc = pred.get("desc") or pred.get("type")
    return f"{desc}{(' — ' + extra) if extra else ''}"


def decide(store: dict, ctx: dict) -> dict:
    """Pure: given the tripwire store + a context dict, return a verdict.

    verdict ∈ allow | ask | snapshot | halt . ctx keys: tool, file_path, command,
    edit_counts, calls_since_test, last_run_failed, is_disarm, override_active."""
    if not store:
        return {"verdict": "allow", "message": "", "predicate": None}

    # Structural guard: disarming tripwires without a logged override is blocked.
    if ctx.get("is_disarm") and not ctx.get("override_active"):
        return {
            "verdict": "halt", "predicate": "_disarm",
            "message": ("ULYSSES tripwire: you are about to edit/remove your own "
                        "tripwires.json mid-task. That is exactly the rationalizing-self "
                        "move the tripwires exist to stop. To proceed deliberately, log "
                        "an override first:\n  python ~/.claude/hooks/ulysses/arm.py "
                        "--override \"<why weakening is correct>\"\nthen retry (valid for "
                        f"{int(OVERRIDE_WINDOW_SEC // 60)} min). Or edit via arm.py."),
        }

    trips: list[tuple[str, dict, str]] = []  # (action, pred, extra)
    tool = str(ctx.get("tool") or "")
    fp = _norm(ctx.get("file_path"))
    cmd = str(ctx.get("command") or "")
    for pred in store.get("predicates") or []:
        try:
            typ = pred.get("type")
            action = str(pred.get("action") or "ASK").upper()
            if action not in ACTIONS:
                action = "ASK"
            if typ == "tool_match":
                if pred.get("pattern") and re.search(pred["pattern"], tool):
                    trips.append((action, pred, f"tool '{tool}'"))
            elif typ == "path_match":
                hay = fp + " " + cmd
                if pred.get("pattern") and re.search(pred["pattern"], hay, re.IGNORECASE):
                    trips.append((action, pred, "target matches"))
            elif typ == "path_reedit":
                if tool in EDIT_TOOLS and fp:
                    thr = int(pred.get("threshold") or 4)
                    prior = int((ctx.get("edit_counts") or {}).get(fp, 0))
                    if prior + 1 >= thr:
                        trips.append((action, pred, f"edit #{prior + 1} of {fp.split('/')[-1]}"))
            elif typ == "calls_since_test":
                thr = int(pred.get("threshold") or 25)
                cst = int(ctx.get("calls_since_test") or 0)
                if cst > thr:
                    note = f"{cst} tool-calls since tests last passed"
                    if ctx.get("last_run_failed"):
                        note += " (last test run FAILED)"
                    trips.append((action, pred, note))
        except Exception:
            continue

    if not trips:
        return {"verdict": "allow", "message": "", "predicate": None}

    # Priority: HALT > ASK > SNAPSHOT.
    for want, verdict, lead in (
        ("HALT", "halt", "ULYSSES HALT — you committed to NOT do this:"),
        ("ASK", "ask", "ULYSSES tripwire (ASK) — you committed to ask first:"),
        ("SNAPSHOT", "snapshot", "ULYSSES tripwire (SNAPSHOT) — checkpoint before this:"),
    ):
        hits = [(p, x) for a, p, x in trips if a == want]
        if not hits:
            continue
        body = "; ".join(_trip_msg(p, x) for p, x in hits)
        if verdict == "halt":
            msg = (f"{lead} {body}. This tool call is BLOCKED. If proceeding is genuinely "
                   f"correct, log an override (arm.py --override \"<reason>\") and retry; "
                   f"otherwise choose a reversible path (verify the field / save-edit, not "
                   f"a live write).")
        elif verdict == "snapshot":
            msg = (f"{lead} {body}. Create a restore point now (git stash/commit, or "
                   f"note.py milestone) before proceeding.")
        else:
            msg = (f"{lead} {body}. Confirm with the user (or your own cold-start "
                   f"reasoning) before this action; do not rationalize past it.")
        return {"verdict": verdict, "message": msg, "predicate": hits[0][0].get("id")}

    return {"verdict": "allow", "message": "", "predicate": None}


# ---------------------------------------------------------------------------
# Context build (reads the transcript; used by enforce.py)
# ---------------------------------------------------------------------------
def build_ctx(payload: dict, store: dict) -> dict:
    tool = str((payload or {}).get("tool_name") or "")
    tinput = (payload or {}).get("tool_input") or {}
    command = str(tinput.get("command") or "") if tool in SHELL_TOOLS else ""
    fp = tinput.get("file_path") or ""
    cwd = str((payload or {}).get("cwd") or os.getcwd())
    if fp and not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    since = None
    try:
        if store and float(store.get("armed_ts") or 0) > 0:
            since = float(store["armed_ts"])
    except Exception:
        since = None
    scan = scan_transcript(str((payload or {}).get("transcript_path") or ""), since_ts=since)
    return {
        "tool": tool, "file_path": fp, "command": command,
        "edit_counts": scan["edit_counts"], "calls_since_test": scan["calls_since_test"],
        "last_run_failed": scan["last_run_failed"],
        "is_disarm": is_disarm_attempt(tool, tinput, command),
        "override_active": override_active(),
    }
