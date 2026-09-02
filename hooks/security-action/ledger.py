#!/usr/bin/env python3
r"""security-action/ledger.py — append-only JSONL audit of matched tool calls.

Harness-safety evidence rail, in the same family as the event-ledger keystone
(agent-self/config/hooks/event-ledger): a durable, append-only record of the
tool invocations a scope hook evaluated — timestamp, tool name, REDACTED
arguments, the allow/block decision, and the reason. Where the event-ledger
records *what happened this turn* for post-compaction replay, this records
*what was reached for* so a scoped run has an after-the-fact audit trail.

Design
------
- One JSON object per line (JSONL); append-only — lines are only ever added,
  never mutated or removed.
- Every write is an ATOMIC REPLACE: read current file, add the new line, write a
  temp file in the same dir, fsync, then os.replace() over the target. A partial
  write can therefore never be observed, and a reader always sees a whole file.
- Concurrency-safe: a cross-platform mkdir-based advisory lock serializes the
  read-modify-replace so parallel writers cannot lose each other's lines. If the
  lock cannot be taken within the timeout, the writer falls back to a single
  O_APPEND line write (still atomic for one short line) rather than dropping the
  record — the ledger must never break a session.
- Secret-shaped values are REDACTED before anything is written (key-name and
  value-pattern based), so the audit trail cannot itself become a secret sink.

Storage: <ROOT>/<project-slug>/actions.jsonl
  ROOT = SECURITY_ACTION_ROOT env, else ~/.claude/security-action
Pure stdlib. Every public function is fail-soft; append_record never raises.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

ROOT = Path(
    os.environ.get(
        "SECURITY_ACTION_ROOT", str(Path.home() / ".claude" / "security-action")
    )
)

# How long a writer waits to acquire the advisory lock before falling back.
_LOCK_TIMEOUT_SEC = float(os.environ.get("SECURITY_ACTION_LOCK_TIMEOUT", "10"))
_LOCK_POLL_SEC = 0.005

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"

# Substrings that mark a key whose VALUE is masked wholesale, regardless of
# shape. Matched against the key name normalized to lowercase alnum (so
# "api_key", "apiKey" and "API-KEY" all collapse to "apikey"). Redaction errs
# toward masking: a rare false positive in an audit log is safer than leaking a
# credential. Bare "auth" is deliberately excluded (it would swallow "author");
# real auth headers are caught by "authorization" / "bearer" / "token".
_SECRET_KEY_HINTS = (
    "password",
    "passwd",
    "passphrase",
    "pwd",
    "secret",
    "token",
    "apikey",
    "accesskey",
    "secretkey",
    "privatekey",
    "clientsecret",
    "authorization",
    "bearer",
    "credential",
    "sessiontoken",
    "sessionid",
    "cookie",
    "otp",
    "passcode",
)


def _is_secret_key(k: str) -> bool:
    try:
        norm = re.sub(r"[^a-z0-9]", "", str(k).lower())
        return any(h in norm for h in _SECRET_KEY_HINTS)
    except Exception:
        return False

# Value-shape rules: secret-looking substrings inside ANY string are masked even
# when the key name is innocent (e.g. a URL query string carrying ?token=...).
_VALUE_RULES: list[tuple[re.Pattern[str], object]] = [
    # PEM private key blocks.
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        _REDACTED,
    ),
    # AWS access key id.
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), _REDACTED),
    # Common provider token prefixes (OpenAI sk-/rk-, GitHub gh?_, Slack xox?-).
    (re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_\-]{16,}\b"), _REDACTED),
    (re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"), _REDACTED),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), _REDACTED),
    # JWTs (header.payload.signature).
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\b"),
        _REDACTED,
    ),
    # key=value / key: value pairs where the key names a secret — mask the value
    # only, keep the key so the record still shows a secret was present.
    (
        re.compile(
            r"(?i)\b(pass(?:word|wd|phrase)?|pwd|secret|token|api[_-]?key|"
            r"access[_-]?key|secret[_-]?key|client[_-]?secret|bearer|credential)\b"
            r"(\s*[:=]\s*)"
            r"(\"?)([^\s\"'&]+)",
        ),
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{_REDACTED}",
    ),
]


def _redact_string(s: str) -> str:
    out = s
    for pat, repl in _VALUE_RULES:
        try:
            out = pat.sub(repl, out)  # type: ignore[arg-type]
        except Exception:
            continue
    return out


def redact(value, _key: str = "", _depth: int = 0):
    """Return a deep-copied, secret-redacted version of *value*.

    - A dict value whose KEY name looks secret is masked wholesale.
    - Every string is additionally scrubbed for secret-shaped substrings.
    - Non-secret content is preserved so the audit trail stays useful.
    Never raises — on any error the input is coerced to a redacted string.
    """
    try:
        if _depth > 12:
            return _REDACTED
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if isinstance(k, str) and _is_secret_key(k):
                    out[k] = _REDACTED
                else:
                    out[k] = redact(v, str(k), _depth + 1)
            return out
        if isinstance(value, (list, tuple)):
            return [redact(v, _key, _depth + 1) for v in value]
        if isinstance(value, str):
            return _redact_string(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return _redact_string(str(value))
    except Exception:
        return _REDACTED


# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------


def _slug(project_path: str) -> str:
    """Stable, readable, collision-resistant per-project directory name."""
    p = str(project_path or os.getcwd())
    base = Path(p).name or "root"
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic per-project slug for a state dir, not a security control
    h = hashlib.sha1(
        p.replace("\\", "/").lower().rstrip("/").encode("utf-8", "replace"),
        usedforsecurity=False,
    ).hexdigest()[:8]
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)[:40]
    return f"{safe}-{h}"


def _dir(project_path: str) -> Path:
    d = ROOT / _slug(project_path)
    d.mkdir(parents=True, exist_ok=True)
    return d


def actions_file(project_path: str | None = None) -> Path:
    return _dir(str(project_path or os.getcwd())) / "actions.jsonl"


# ---------------------------------------------------------------------------
# Advisory lock (cross-platform: mkdir is atomic on POSIX and Windows)
# ---------------------------------------------------------------------------


class _Lock:
    def __init__(self, target: Path):
        self.lock_dir = target.with_suffix(target.suffix + ".lock")
        self.held = False

    def __enter__(self) -> "_Lock":
        deadline = time.monotonic() + _LOCK_TIMEOUT_SEC
        while True:
            try:
                self.lock_dir.mkdir()
                self.held = True
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    return self  # give up — caller falls back to O_APPEND
                time.sleep(_LOCK_POLL_SEC)
            except Exception:
                return self  # any other error → no lock, caller falls back

    def __exit__(self, *exc) -> None:
        if self.held:
            try:
                self.lock_dir.rmdir()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Append (atomic replace under the lock; O_APPEND fallback)
# ---------------------------------------------------------------------------


def _atomic_replace_append(path: Path, line: str) -> bool:
    """Read current file, add *line*, write a temp copy, os.replace over target."""
    try:
        existing = b""
        if path.exists():
            existing = path.read_bytes()
        payload = existing + line.encode("utf-8")
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".jsonl.tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True
    except Exception:
        return False


def _plain_append(path: Path, line: str) -> bool:
    """Fallback: single O_APPEND line write (atomic for one short line)."""
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return True
    except Exception:
        return False


def append_record(record: dict, project_path: str | None = None) -> dict:
    """Redact *record*, then append it as one JSONL line. Never raises.

    The ``args`` field (if present) is redacted deeply; a few well-known top-level
    fields (tool/decision/reason/enforced/targets/unmatched) are passed through
    after string-scrubbing. A ``ts`` ISO timestamp is added when absent. Returns
    the redacted record that was written (with a ``_written`` bool).
    """
    try:
        safe: dict = {}
        safe["ts"] = str(record.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S"))
        for k, v in record.items():
            if k == "ts":
                continue
            safe[k] = redact(v, k)
        line = json.dumps(safe, ensure_ascii=False) + "\n"

        path = actions_file(project_path)
        with _Lock(path) as lock:
            ok = _atomic_replace_append(path, line)
            if not ok or not lock.held:
                # If we never held the lock, a concurrent writer may be mid
                # replace; prefer the atomic path but guarantee the line lands.
                if not ok:
                    ok = _plain_append(path, line)
        safe["_written"] = bool(ok)
        return safe
    except Exception:
        # Absolute last resort: never propagate an error to a hook.
        return {"_written": False, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}


def read_records(project_path: str | None = None) -> list[dict]:
    """Return all audit records (oldest→newest). Bad lines are skipped."""
    path = actions_file(project_path)
    if not path.exists():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out
