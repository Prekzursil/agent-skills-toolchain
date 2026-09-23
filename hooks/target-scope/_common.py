#!/usr/bin/env python3
r"""target-scope/_common.py — shared helpers for check.py and set_scope.py.

Pure stdlib. Every public helper is fail-soft (safe default) so callers stay
FAIL-OPEN. Self-contained: no cross-dir imports (mirrors the file-scope
convention so this hook can never be broken by a sibling hook moving/breaking).

This is the argument-scope analogue of hooks/file-scope/_common.py. Where
file-scope matches ONE write target (file_path) against allowed globs, this
module extracts every host / URL / path string that a tool call would *reach*
and checks each against a per-agent allowlist. The glob engine is the same one
file-scope uses (** across path components, * within one), so a single flat
allow-list can express host globs (``*.example.com``), URL globs
(``https://api.example.com/**``) and path globs (``/tmp/**``) side by side.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------


def scopes_dir(hook_dir: Path) -> Path:
    """Return the scopes directory.

    Production:      <HOOK_DIR>/scopes/
    Test-isolation:  TARGET_SCOPE_DIR env overrides base to <TARGET_SCOPE_DIR>/scopes/
    """
    base = os.environ.get("TARGET_SCOPE_DIR", "")
    return Path(base) / "scopes" if base else hook_dir / "scopes"


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def _safe(s: str) -> str:
    """Convert a string to a safe filesystem component (max 80 chars)."""
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(s))[:80]
        or "default"
    )


def _cwd_slug(cwd: str) -> str:
    """12-char sha1 slug of a normalized cwd path (case-folded)."""
    norm = cwd.replace("\\", "/").lower().rstrip("/")
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic cwd-path slug for a state key, not a security control
    return hashlib.sha1(norm.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def sidecar_path(sd: Path, key_type: str, key: str) -> Path:
    """Return the sidecar file path for a given key type + key."""
    if key_type == "session":
        return sd / f"session-{_safe(key)}.json"
    if key_type == "agent":
        return sd / f"agent-{_safe(key)}.json"
    if key_type == "cwd":
        return sd / f"cwd-{_cwd_slug(key)}.json"
    raise ValueError(f"unknown key_type: {key_type!r}")


# ---------------------------------------------------------------------------
# Sidecar I/O
# ---------------------------------------------------------------------------


def try_sidecar(path: Path) -> dict | None:
    """Load and validate a sidecar file.  Returns the dict or None.

    None means "no enforcement" — callers MUST exit 0 (fail-open) on None.
    None is returned for: missing file, bad JSON, wrong shape, expired TTL.
    A sidecar with an empty allow list IS valid — it blocks all targets.
    """
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        allow = obj.get("allow")
        if not isinstance(allow, list):
            return None
        ttl = float(obj.get("ttl_hours") or 0)
        if ttl > 0:
            created = float(obj.get("created_at") or 0)
            if created and (created + ttl * 3600.0) < time.time():
                return None  # expired — treat as absent
        return obj
    except Exception:
        return None  # fail-open on any error


def write_sidecar(
    path: Path, key: str, key_type: str, allow: list[str], ttl_hours: float = 24.0
) -> bool:
    """Atomically write a sidecar. Returns True on success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        obj = {
            "key": key,
            "key_type": key_type,
            "allow": allow,
            "created_at": time.time(),
            "ttl_hours": ttl_hours,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Glob matching — supports ** for zero-or-more path components
# ---------------------------------------------------------------------------


def _norm(p: str) -> str:
    """Normalize path separators to forward slashes."""
    return str(p or "").replace("\\", "/")


def _is_abs_pattern(pat: str) -> bool:
    """True for absolute patterns (Unix /foo or Windows C:/foo)."""
    return pat.startswith("/") or (len(pat) >= 2 and pat[1] == ":")


def _path_tails(norm_path: str) -> list[str]:
    """All suffix components of a normalized path for relative-pattern matching."""
    result: list[str] = []
    if norm_path.startswith("/"):
        result.append(norm_path)
    parts = norm_path.lstrip("/").split("/")
    for i in range(len(parts)):
        tail = "/".join(parts[i:])
        if tail and tail not in result:
            result.append(tail)
    return result


def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern to a regex string.

    Rules:
      **  followed by /  → zero or more path-component+separator groups
      **  at end / alone → anything (including nested paths)
      *                  → any characters within one path component (no /)
      ?                  → any single character (no /)
      Other              → re.escaped literal
    """
    result: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern[i : i + 2] == "**":
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                result.append("(?:[^/]+/)*")
                i += 1  # consume the /
            else:
                result.append(".*")
        elif ch == "*":
            result.append("[^/]*")
            i += 1
        elif ch == "?":
            result.append("[^/]")
            i += 1
        else:
            result.append(re.escape(ch))
            i += 1
    return "".join(result)


def matches_any(value: str, patterns: list[str]) -> bool:
    """Return True if *value* matches any glob pattern in the list.

    Absolute patterns are matched against the full normalized value only.
    Relative patterns are tried against every tail so that ``example.com``
    matches ``https://example.com/x`` via the tail ``example.com/x`` is NOT
    implied — hosts are matched as whole tokens by the caller, which passes the
    bare host as its own candidate.  Case-folding matches file-scope on
    Windows (drive-letter / dir case differences must not cause false blocks).
    """
    norm = _norm(value)
    if os.name == "nt":
        norm = norm.lower()
    tails = _path_tails(norm)

    for pattern in patterns:
        pat = _norm(pattern)
        if os.name == "nt":
            pat = pat.lower()
        if not pat:
            continue
        try:
            rx = re.compile(_glob_to_regex(pat) + r"\Z")
        except re.error:
            continue  # malformed pattern → skip (fail-open)

        if _is_abs_pattern(pat):
            if rx.fullmatch(norm):
                return True
        else:
            for tail in tails:
                if rx.fullmatch(tail):
                    return True

    return False


# ---------------------------------------------------------------------------
# Target extraction — the argument-scope core
# ---------------------------------------------------------------------------

# Keys whose string value names a URL/endpoint the tool will reach.
URL_KEYS = frozenset(
    {"url", "uri", "endpoint", "base_url", "baseurl", "link", "href", "callback"}
)
# Keys whose string value names a host / address the tool will reach.
HOST_KEYS = frozenset(
    {
        "host",
        "hostname",
        "domain",
        "target",
        "targets",
        "address",
        "addr",
        "ip",
        "remote",
        "rhost",
        "rhosts",
        "server",
        "proxy",
    }
)
# Keys whose string value names a filesystem path the tool will touch.
PATH_KEYS = frozenset(
    {
        "file_path",
        "notebook_path",
        "path",
        "cwd",
        "directory",
        "dir",
        "output",
        "outfile",
        "out",
        "filename",
        "file",
        "source",
        "destination",
        "dest",
    }
)

# scheme://rest — stops at whitespace / quote / angle / pipe / backslash.
_URL_RX = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s'\"<>|\\]+")

_MAX_TARGETS = 256  # bound work on pathological inputs
_MAX_DEPTH = 8


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").strip().lower()
    except Exception:
        return ""


def _strip_port(host: str) -> str:
    # IPv6 literals are wrapped in [] — leave those alone.
    if host.startswith("["):
        return host
    if ":" in host:
        head, _, tail = host.rpartition(":")
        if head and tail.isdigit():
            return head
    return host


def _mk_target(kind: str, raw: str, candidates: list[str]) -> dict:
    seen: list[str] = []
    for c in candidates:
        c = (c or "").strip()
        if c and c not in seen:
            seen.append(c)
    return {"kind": kind, "raw": raw, "candidates": seen}


def _targets_from_string(key: str, value: str) -> list[dict]:
    out: list[dict] = []
    v = value.strip()
    if not v:
        return out
    klow = key.lower()

    # 1. Any scheme://... substring anywhere is a URL target (covers command
    #    strings, nested blobs, and url-typed keys alike).
    for m in _URL_RX.finditer(v):
        url = m.group(0).rstrip(".,);]'\"")
        host = _host_of(url)
        cands = [url]
        if host:
            cands.append(host)
            cands.append(_strip_port(host))
        out.append(_mk_target("url", url, cands))

    # 2. Key-directed classification of the whole value (only when it is not
    #    itself a bare URL already captured above).
    is_bare_url = bool(_URL_RX.fullmatch(v))
    if not is_bare_url:
        if klow in URL_KEYS:
            # url-typed but no scheme → treat the value as a host token.
            host = _strip_port(v.lower())
            out.append(_mk_target("host", v, [v, v.lower(), host]))
        elif klow in HOST_KEYS:
            host = v.lower()
            out.append(_mk_target("host", v, [v, host, _strip_port(host)]))
        elif klow in PATH_KEYS:
            out.append(_mk_target("path", v, [v]))
    return out


def extract_targets(tool_input) -> list[dict]:
    """Walk a tool_input structure and return the target objects to check.

    Each target is ``{"kind", "raw", "candidates"}`` and is considered
    in-scope when ANY candidate matches ANY allow glob (so allowing a host
    covers every URL on that host).  Extraction is deliberately conservative:
    URLs are picked up anywhere (unambiguous ``scheme://``), while bare
    hosts/paths are only taken from explicitly named keys — never guessed out
    of free-form command text — so the hook does not manufacture false blocks.
    """
    targets: list[dict] = []

    def _walk(key: str, node, depth: int) -> None:
        if len(targets) >= _MAX_TARGETS or depth > _MAX_DEPTH:
            return
        if isinstance(node, str):
            targets.extend(_targets_from_string(key, node))
        elif isinstance(node, dict):
            for k, v in node.items():
                _walk(str(k), v, depth + 1)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(key, item, depth + 1)

    try:
        _walk("", tool_input, 0)
    except Exception:
        return []  # fail-open: extraction must never raise

    # De-dup by (kind, raw) preserving order.
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for t in targets:
        sig = (t["kind"], t["raw"])
        if sig not in seen:
            seen.add(sig)
            deduped.append(t)
    return deduped[:_MAX_TARGETS]


# ---------------------------------------------------------------------------
# Sidecar lookup (three-tier keying — mirrors file-scope)
# ---------------------------------------------------------------------------


def find_sidecar(payload: dict, sd: Path) -> dict | None:
    """Return the first sidecar found under any supported key, or None.

    Lookup order (first match wins), same as file-scope:
      1. TARGET_SCOPE_AGENT env var → scopes/agent-<name>.json  (isolation-safe)
      2. session_id from payload    → scopes/session-<id>.json
      3. cwd from payload           → scopes/cwd-<sha1>.json
    """
    agent = os.environ.get("TARGET_SCOPE_AGENT", "").strip()
    if agent:
        s = try_sidecar(sidecar_path(sd, "agent", agent))
        if s is not None:
            return s

    session_id = extract_session_id(payload)
    if session_id and session_id != "default":
        s = try_sidecar(sidecar_path(sd, "session", session_id))
        if s is not None:
            return s

    cwd = str((payload or {}).get("cwd") or "")
    if cwd:
        s = try_sidecar(sidecar_path(sd, "cwd", cwd))
        if s is not None:
            return s

    return None


# ---------------------------------------------------------------------------
# The pure decision function (fully unit-testable)
# ---------------------------------------------------------------------------


def evaluate(payload: dict, sd: Path) -> dict:
    """Pure: decide whether a tool call's targets are in declared scope.

    Returns a dict:
      tool      — the tool name
      enforced  — True only when a sidecar applied AND targets were found
      decision  — "allow" | "block"
      reason    — human-readable explanation
      allow     — the allow-list that applied (empty when not enforced)
      targets   — raw target strings seen
      unmatched — raw target strings that matched no allow glob (block cause)

    FAIL-OPEN contract: no sidecar, no targets, or any error → decision
    "allow" with enforced False (callers exit 0).
    """
    result = {
        "tool": str((payload or {}).get("tool_name") or ""),
        "enforced": False,
        "decision": "allow",
        "reason": "no-sidecar",
        "allow": [],
        "targets": [],
        "unmatched": [],
    }
    try:
        ti = (payload or {}).get("tool_input") or {}
        targets = extract_targets(ti)
        result["targets"] = [t["raw"] for t in targets]

        sidecar = find_sidecar(payload or {}, sd)
        if sidecar is None:
            result["reason"] = "no-sidecar"
            return result

        allow = sidecar.get("allow") or []
        result["allow"] = list(allow)

        if not targets:
            result["reason"] = "no-targets"
            return result

        result["enforced"] = True
        unmatched = [
            t
            for t in targets
            if not any(matches_any(c, allow) for c in t["candidates"])
        ]
        if unmatched:
            raws = sorted({t["raw"] for t in unmatched})
            result["decision"] = "block"
            result["unmatched"] = raws
            result["reason"] = "target(s) out of declared scope: " + ", ".join(raws)
        else:
            result["decision"] = "allow"
            result["reason"] = "all targets in declared scope"
        return result
    except Exception:
        # fail-open: any internal error → allow, not enforced.
        result["enforced"] = False
        result["decision"] = "allow"
        result["reason"] = "error-failopen"
        return result


# ---------------------------------------------------------------------------
# Hook payload helpers
# ---------------------------------------------------------------------------


def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def extract_session_id(data: dict) -> str:
    return (
        str((data or {}).get("session_id") or "default")
        .replace("/", "_")
        .replace("\\", "_")
    )
