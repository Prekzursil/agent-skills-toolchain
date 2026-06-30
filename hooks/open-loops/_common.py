#!/usr/bin/env python3
r"""open-loops/_common.py — shared data layer for the open-loops + prospective-memory trio
(add.py / resurface.py / trigger_match.py).

WHAT THIS IMPLEMENTS (Zeigarnik / prospective memory — the user's #1 felt pain =
forgotten threads):

  1. A durable trigger store  ~/.claude/open-loops/triggers.jsonl  of "when X happens,
     do Y" intentions. Each line:
        {id, condition, action, created_ts, ttl_days, fired, fired_ts,
         recurring, source, raw}
     `condition` = {"mode": "any"|"all", "preds": [<pred>, ...]} where each <pred> is a
     CHEAP, stdlib-only predicate evaluated against the current turn context:
        cwd_glob | branch_glob | branch_regex | file_exists | prompt_regex | keyword | always
  2. Open loops DERIVED from the event-ledger (unresolved failures + a dangling goal)
     are folded in by resurface.py — distinct from sessionstart-replay (see below).

ISOLATION NOTE (dispatcher): resurface.py is folded into the SessionStart dispatcher
(_dispatch/manifest.json). The dispatcher pops the dir-local shared name `_common`
before importing each check and the check re-inserts its own dir on sys.path[0], so
this module re-resolves to THIS dir even though bg-registry/ and memory-spool/ also
ship a `_common.py`. That is exactly why this file is named `_common.py` (it is in the
dispatcher's hardcoded _SHARED_NAMES tuple) — mirrors the proven bg-registry pattern.

Pure stdlib. Every public helper swallows its own errors (safe default) so callers stay
simple and FAIL-OPEN.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

HOME = Path.home()
OL_DIR = Path(os.environ.get("OPEN_LOOPS_DIR", str(HOME / ".claude" / "open-loops")))
TRIGGERS_FILE = OL_DIR / "triggers.jsonl"
LEDGER_DIR = str(Path(__file__).resolve().parent.parent / "event-ledger")

DEFAULT_TTL_DAYS = int(os.environ.get("OPEN_LOOPS_TTL_DAYS", "30"))
# Recurring triggers re-fire at most once per this window (anti-nag).
RECUR_THROTTLE_SEC = float(os.environ.get("OPEN_LOOPS_RECUR_SEC", str(6 * 3600)))

PRED_TYPES = (
    "cwd_glob",
    "branch_glob",
    "branch_regex",
    "file_exists",
    "prompt_regex",
    "keyword",
    "always",
)

# Words dropped when deriving keyword predicates from plain language.
_STOP = frozenset(
    """
a an the to of and or but if when whenever while is are be been being it its this that
these those your you i me my we our us on in at for with about under over into onto from
as do does did done so then than will would should could can may might must re-assert
path paths dir dirs directory directories folder folders branch branches file files cwd
matches matching match touch touching touched about-to about next time whenever am pm
""".split()
)


# ---------------------------------------------------------------------------
# Tiny stdlib helpers (mirror the B1 emit / read_stdin conventions)
# ---------------------------------------------------------------------------
def now() -> float:
    return time.time()


def emit(event_name: str, msg: str) -> None:
    """Inject additionalContext (the shared hookSpecificOutput shape)."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": msg,
                }
            }
        )
    )


def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def _norm(s) -> str:
    """Lowercase + forward-slash a path/string for stable cross-platform matching."""
    return str(s or "").replace("\\", "/").lower().strip()


def short_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Store I/O — append-only triggers.jsonl with lazy TTL garbage-collection.
# ---------------------------------------------------------------------------
def _is_expired(rec: dict, ref_ts: float | None = None) -> bool:
    """True when created_ts + ttl_days has elapsed. ttl_days <= 0 -> never expires."""
    try:
        ttl = float(rec.get("ttl_days") or 0)
        if ttl <= 0:
            return False
        created = float(rec.get("created_ts") or 0)
        ref = now() if ref_ts is None else ref_ts
        return (created + ttl * 86400.0) < ref
    except Exception:
        return False


def load_triggers(gc: bool = True) -> list[dict]:
    """Read every trigger; drop (and, when gc, rewrite without) TTL-expired ones.

    Returns the surviving (non-expired) records, oldest->newest. FAIL-OPEN: a corrupt
    line is skipped; a totally unreadable store yields []."""
    recs: list[dict] = []
    try:
        if not TRIGGERS_FILE.exists():
            return []
        with TRIGGERS_FILE.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and obj.get("id"):
                    recs.append(obj)
    except Exception:
        return []
    alive = [r for r in recs if not _is_expired(r)]
    if gc and len(alive) != len(recs):
        save_triggers(alive)
    return alive


def save_triggers(recs: list[dict]) -> bool:
    """Atomically rewrite the whole store (used by GC / --close). FAIL-OPEN -> bool."""
    try:
        OL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = TRIGGERS_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8", errors="replace") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, TRIGGERS_FILE)
        return True
    except Exception:
        return False


def append_trigger(rec: dict) -> bool:
    """Append one trigger record. FAIL-OPEN -> bool."""
    try:
        OL_DIR.mkdir(parents=True, exist_ok=True)
        with TRIGGERS_FILE.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def make_trigger(
    condition: dict,
    action: str,
    *,
    ttl_days: int | None = None,
    recurring: bool = False,
    source: str = "manual",
    raw: str = "",
) -> dict:
    return {
        "id": short_id(),
        "condition": condition or {"mode": "any", "preds": []},
        "action": str(action or "").strip(),
        "created_ts": now(),
        "ttl_days": int(DEFAULT_TTL_DAYS if ttl_days is None else ttl_days),
        "fired": False,
        "fired_ts": None,
        "recurring": bool(recurring),
        "source": str(source or "manual"),
        "raw": str(raw or "").strip(),
    }


# ---------------------------------------------------------------------------
# Plain-language parsing (best-effort; explicit preds are the precise path).
# ---------------------------------------------------------------------------
_PATH_TOKEN = re.compile(
    r"""["'`]?((?:[a-zA-Z]:[\\/]|\.{0,2}[\\/])[^\s"'`]+|[^\s"'`]*[\\/][^\s"'`]+)["'`]?"""
)
_GLOB_TOKEN = re.compile(
    r"""["'`]?([A-Za-z0-9_.\-]*[*?\[][A-Za-z0-9_.\-*?\[\]/]*)["'`]?"""
)


def _path_core(token: str) -> str:
    """Last meaningful path segment of a path token -> a portable *core* glob.

    D:\\WSA -> wsa ; D:/WSA/_analysis -> _analysis ; ./src/foo -> foo
    Drive letters and empty segments are dropped (drive-portable)."""
    parts = [p for p in _norm(token).split("/") if p and not re.fullmatch(r"[a-z]:", p)]
    return parts[-1] if parts else _norm(token)


def _keywords(text: str, limit: int = 4) -> list[str]:
    out: list[str] = []
    for raw in re.split(r"[^A-Za-z0-9_./\\-]+", text or ""):
        w = raw.strip("-._/\\").lower()
        if len(w) < 3 or w in _STOP or w.isdigit():
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _clause_to_pred(clause: str) -> dict | None:
    """Turn one natural-language clause into a single cheap predicate."""
    c = clause.strip()
    if not c:
        return None
    low = c.lower()

    # branch matcher: "branch matches feat/*", "branch feat/*", "on branch main"
    if "branch" in low:
        m = _GLOB_TOKEN.search(c) or re.search(
            r"(?:branch|matches|matching|is|=|on)\s+([A-Za-z0-9_./*?\-]+)", c, re.I
        )
        if m:
            tok = m.group(1).strip("\"'`")
            if any(ch in tok for ch in "*?["):
                return {"type": "branch_glob", "value": tok}
            return {"type": "branch_regex", "value": tok}

    # explicit file existence: "file <path> exists"
    if "file" in low and ("exist" in low or _PATH_TOKEN.search(c)):
        pm = _PATH_TOKEN.search(c)
        if pm:
            return {"type": "file_exists", "value": pm.group(1).strip("\"'`")}

    # path / cwd matcher: any path-like token -> portable core glob
    pm = _PATH_TOKEN.search(c)
    if (
        pm
        and any(
            k in low
            for k in ("cwd", "under", "path", "dir", "directory", "folder", "in ")
        )
        or (pm and ("/" in pm.group(1) or "\\" in pm.group(1)))
    ):
        core = _path_core(pm.group(1))
        if core:
            return {"type": "cwd_glob", "value": f"*{core}*"}

    # bare glob token (e.g. feat/*) with no "branch" word -> treat as cwd glob
    gm = _GLOB_TOKEN.search(c)
    if gm and "branch" not in low:
        return {"type": "cwd_glob", "value": _norm(gm.group(1).strip("\"'`"))}

    # fallback: significant keywords (match against cwd+branch+prompt+recent-files)
    kws = _keywords(c)
    if kws:
        # one keyword pred per word, OR-combined inside; represent as multiple preds upstream
        return {"type": "keyword", "value": kws[0], "_extra": kws[1:]}
    return None


def parse_plain(text: str) -> tuple[dict, str]:
    """Parse 'when <cond> -> <action>' into (condition, action).

    Heuristic. Returns ({mode, preds}, action). No condition -> an `always` loop
    (a standing reminder surfaced at SessionStart, not fired on every prompt)."""
    t = (text or "").strip()
    # split condition / action on the first arrow-ish separator
    cond_part, action = "", t
    m = re.split(r"\s*(?:->|=>|→|\bthen\b)\s*", t, maxsplit=1, flags=re.I)
    if len(m) == 2:
        cond_part, action = m[0], m[1]
    # strip leading intent words
    cond_part = re.sub(
        r"^\s*(when|whenever|if|remember to|remind me to)\s+", "", cond_part, flags=re.I
    )
    action = re.sub(
        r"^\s*(remember to|remind me to|then)\s+", "", action, flags=re.I
    ).strip()

    mode = "all" if re.search(r"\band\b", cond_part, re.I) else "any"
    preds: list[dict] = []
    if cond_part.strip():
        for clause in re.split(r"\s+(?:and|or)\s+", cond_part, flags=re.I):
            p = _clause_to_pred(clause)
            if not p:
                continue
            extra = p.pop("_extra", [])
            preds.append(p)
            for kw in extra:
                preds.append({"type": "keyword", "value": kw})
    if not preds:
        preds = [{"type": "always"}]
        mode = "any"
    return {"mode": mode, "preds": preds}, (action or t)


# ---------------------------------------------------------------------------
# Context build + predicate evaluation
# ---------------------------------------------------------------------------
def git_branch(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd or "."), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _recent_files(transcript_path: str, limit: int = 40) -> list[str]:
    """Best-effort: file_paths from recent Edit/Write tool_use blocks in the transcript."""
    out: list[str] = []
    try:
        p = Path(transcript_path)
        if not transcript_path or not p.exists():
            return out
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
        for ln in lines:
            ln = ln.strip()
            if not ln or '"tool_use"' not in ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            msg = ev.get("message") or {}
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for b in content:
                if (
                    isinstance(b, dict)
                    and b.get("type") == "tool_use"
                    and b.get("name") in ("Edit", "Write", "MultiEdit")
                ):
                    fp = (b.get("input") or {}).get("file_path")
                    if fp:
                        out.append(_norm(fp))
    except Exception:
        return out
    return out[-limit:]


def build_ctx(payload: dict) -> dict:
    cwd = str((payload or {}).get("cwd") or os.getcwd())
    prompt = str((payload or {}).get("prompt") or "")
    branch = git_branch(cwd)
    recent = _recent_files(str((payload or {}).get("transcript_path") or ""))
    haystack = " ".join([_norm(cwd), branch.lower(), prompt.lower(), " ".join(recent)])
    return {
        "cwd": cwd,
        "branch": branch,
        "prompt": prompt,
        "recent_files": recent,
        "haystack": haystack,
        "source": str((payload or {}).get("source") or ""),
    }


def _glob_or_sub(value: str, target: str) -> bool:
    """fnmatch when the pattern has glob magic, else a plain substring test."""
    v = _norm(value)
    t = _norm(target)
    if not v:
        return False
    if any(ch in v for ch in "*?["):
        return fnmatch.fnmatch(t, v)
    return v in t


def eval_pred(pred: dict, ctx: dict) -> bool:
    try:
        typ = pred.get("type")
        val = pred.get("value", "")
        if typ == "always":
            return True
        if typ == "cwd_glob":
            return _glob_or_sub(val, ctx.get("cwd", ""))
        if typ == "branch_glob":
            br = ctx.get("branch") or ""
            return bool(br) and fnmatch.fnmatch(br.lower(), _norm(val))
        if typ == "branch_regex":
            br = ctx.get("branch") or ""
            return bool(br) and re.search(val, br, re.I) is not None
        if typ == "file_exists":
            fp = Path(val)
            if not fp.is_absolute():
                fp = Path(ctx.get("cwd") or ".") / val
            return fp.exists()
        if typ == "prompt_regex":
            pr = ctx.get("prompt") or ""
            return bool(pr) and re.search(val, pr, re.I) is not None
        if typ == "keyword":
            return _norm(val) in ctx.get("haystack", "")
    except Exception:
        return False
    return False


def is_contextual(condition: dict) -> bool:
    """True if the condition has any predicate other than bare `always`."""
    for p in (condition or {}).get("preds", []):
        if p.get("type") != "always":
            return True
    return False


def matched_pred_summary(condition: dict, ctx: dict) -> str:
    """A short human note of WHICH predicate matched (for the surfaced reminder)."""
    for p in (condition or {}).get("preds", []):
        if p.get("type") == "always":
            continue
        if eval_pred(p, ctx):
            t = p.get("type")
            v = p.get("value", "")
            if t == "cwd_glob":
                return f"cwd ~ {v}"
            if t in ("branch_glob", "branch_regex"):
                return f"branch ~ {v}"
            if t == "file_exists":
                return f"file exists: {v}"
            if t == "prompt_regex":
                return f"prompt ~ /{v}/"
            if t == "keyword":
                return f"mentions '{v}'"
    return "matches"


def eval_condition(condition: dict, ctx: dict) -> bool:
    preds = (condition or {}).get("preds") or []
    if not preds:
        return False
    mode = (condition or {}).get("mode", "any")
    results = [eval_pred(p, ctx) for p in preds]
    return all(results) if mode == "all" else any(results)


# ---------------------------------------------------------------------------
# Ledger-derived open loops (distinct from sessionstart-replay — see resurface.py)
# ---------------------------------------------------------------------------
def ledger_open_loops(cwd: str) -> list[str]:
    """Unresolved threads from the event ledger: open failures + a standing goal.

    Returns short strings (already de-duplicated against the trigger store's job —
    this is purely the ledger's view of 'started but not closed')."""
    out: list[str] = []
    try:
        if LEDGER_DIR not in sys.path:
            sys.path.insert(0, LEDGER_DIR)
        import ledger  # noqa: PLC0415

        st = ledger.state(cwd) or {}
        of = st.get("open_failures") or []
        if of:
            sample = "; ".join(
                str(f.get("text", ""))[:50] for f in of[-2:] if f.get("text")
            )
            out.append(
                f"{len(of)} unresolved failure(s) still open — close (milestone "
                f"--supersedes) or cheaply re-test, don't silently re-walk: {sample}"
            )
        goal = st.get("goal")
        if goal:
            out.append(f"standing goal not yet marked complete: {str(goal)[:90]}")
    except Exception:
        return out
    return out
