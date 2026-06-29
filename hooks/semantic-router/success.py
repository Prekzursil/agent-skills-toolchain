"""Success-alignment store (shared by route.py and observe.py).

Memento-Skills idea: a suggestion that the agent actually ACTS ON is worth more than
one it ignores. route.py records each suggestion it surfaces (suggested++); observe.py
(PostToolUse) records when a suggested skill/MCP is actually invoked (used++). route.py
then gives a small ranking nudge to historically-acted-on units. Durable JSON, atomic
writes, fully fail-open — this is a soft signal, never load-bearing for correctness.

Two files:
  success.json                 {"kind:name": {"suggested": N, "used": M}}  (global, durable)
  <tmp>/semantic-router/<sid>.json   per-session {"pending":[...], "credited":[...]}
Per-session state prevents double-counting (one suggested++ per name per session; one
used++ per name per session) and lets observe.py credit a use only to something that was
actually suggested THIS session.
"""
import json
import os
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
SUCCESS_JSON = THIS / "success.json"


def _session_dir():
    d = Path(tempfile.gettempdir()) / "semantic-router"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write(path, obj):
    try:
        tmp = str(path) + f".tmp{os.getpid()}"
        Path(tmp).write_text(json.dumps(obj), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def load_success():
    """Return {"kind:name": {"suggested": int, "used": int}}; {} on any error."""
    d = _load(SUCCESS_JSON, {})
    return d if isinstance(d, dict) else {}


def _sess_path(sid):
    sid = str(sid or "default").replace("/", "_").replace("\\", "_")[:80]
    return _session_dir() / f"{sid}.json"


def record_suggested(keys, sid):
    """Mark these 'kind:name' keys as suggested this session (suggested++ once per session).
    Returns the per-session pending set (for the caller's reference). Fail-open."""
    try:
        sp = _sess_path(sid)
        sess = _load(sp, {})
        pending = set(sess.get("pending", []))
        new = [k for k in keys if k not in pending]
        if new:
            succ = load_success()
            for k in new:
                row = succ.get(k) or {"suggested": 0, "used": 0}
                row["suggested"] = int(row.get("suggested", 0)) + 1
                succ[k] = row
            _atomic_write(SUCCESS_JSON, succ)
            pending.update(new)
            sess["pending"] = sorted(pending)
            sess["ts"] = time.time()
            _atomic_write(sp, sess)
        return pending
    except Exception:
        return set()


def record_used(key, sid):
    """If `key` was suggested this session and not yet credited, used++ (once). Fail-open.
    Returns True if a credit was recorded."""
    try:
        sp = _sess_path(sid)
        sess = _load(sp, {})
        pending = set(sess.get("pending", []))
        credited = set(sess.get("credited", []))
        if key not in pending or key in credited:
            return False
        succ = load_success()
        row = succ.get(key) or {"suggested": 0, "used": 0}
        row["used"] = int(row.get("used", 0)) + 1
        succ[key] = row
        _atomic_write(SUCCESS_JSON, succ)
        credited.add(key)
        sess["credited"] = sorted(credited)
        _atomic_write(sp, sess)
        return True
    except Exception:
        return False


def boost(key, succ, alpha):
    """Additive ranking nudge in z-units: alpha * used/(suggested+2). 0 if never used. Bounded by alpha."""
    try:
        row = succ.get(key)
        if not row:
            return 0.0
        s, u = int(row.get("suggested", 0)), int(row.get("used", 0))
        if u <= 0:
            return 0.0
        return alpha * (u / (s + 2.0))
    except Exception:
        return 0.0
