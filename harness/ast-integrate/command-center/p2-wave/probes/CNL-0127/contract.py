#!/usr/bin/env python3
"""Executable audit/replay/privacy/persistence contract for council transcripts.

Findings never include secret values — only class, JSON path, byte length, and
sha256 of the matched span. AGENTS.md 9: READ-ONLY diagnosis, no rotation.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Synthetic fixture only. Never a live credential. Never printed by probes.
SYNTHETIC_TOKEN = "sk-CNL0127SYNTHETICPLACEHOLDER000000NOTLIVE"
SYNTHETIC_TOKEN_SHA256 = hashlib.sha256(SYNTHETIC_TOKEN.encode("utf-8")).hexdigest()
REDACTED_PREFIX = "[REDACTED:"

TOKEN_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-style-token", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("pem-private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer-header", re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]{20,}")),
)
ENV_RE = re.compile(
    r"(?i)(?:^|[\s;])([A-Z][A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*)\s*[=:]\s*([^\s'\"\\]+)"
)
JSON_KEY_RE = re.compile(
    r'(?i)"((?:api[_-]?key|access[_-]?token|secret[_-]?key|password|private[_-]?key|credential))"\s*:\s*"([^"]+)"'
)
CAMEL_RE = re.compile(
    r"(?i)\b(apiKey|accessToken|secretKey|privateKey)\s*[:=]\s*['\"]([^'\"]+)['\"]"
)
B64_RE = re.compile(r"\b([A-Za-z0-9+/]{32,}={0,2})\b")
SECRET_FIELD_KEYS = {
    "apikey",
    "api_key",
    "access_token",
    "accesstoken",
    "secret",
    "secret_key",
    "secretkey",
    "password",
    "private_key",
    "privatekey",
    "credential",
    "token",
}

MAY_PERSIST = (
    "round structure and seat_id / role labels",
    "votes, tallies, stopping_rule_id, dissent text after secret-scan",
    "replay seeds (sampling, tool-order) — seeds are not credentials",
    "input hashes, declared retain_until, payload sha256",
    "tombstones after expiry (id + sha256 + deleted_at, no payload)",
)
MUST_REDACT = (
    "credentials, API tokens, private keys, decrypted secrets (spec :11345)",
    "env-style KEY=value assignments whose key names a secret class",
    "JSON and camelCase secret-shaped keys (apiKey, accessToken, secretKey)",
    "base64 envelopes that decode to a token-shaped or PEM payload",
    "vendor auth material used to recruit a seat — never a replay seed",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def _finding(cls: str, path: str, matched: str) -> dict[str, Any]:
    raw = matched.encode("utf-8")
    return {
        "class": cls,
        "path": path,
        "byte_length": len(raw),
        "sha256": sha256_bytes(raw),
        "value_printed": False,
    }


def _merge(findings: list[dict[str, Any]], item: dict[str, Any]) -> None:
    key = (item["class"], item["path"], item["sha256"])
    if any((f["class"], f["path"], f["sha256"]) == key for f in findings):
        return
    findings.append(item)


def _try_b64_utf8(blob: str) -> str | None:
    pad = (-len(blob)) % 4
    try:
        decoded = base64.b64decode(blob + ("=" * pad))
    except (ValueError, binascii.Error):
        return None
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_text(text: str, path: str, findings: list[dict[str, Any]]) -> None:
    for cls, cre in TOKEN_SPECS:
        for m in cre.finditer(text):
            _merge(findings, _finding(cls, path, m.group(0)))
    for m in ENV_RE.finditer(text):
        _merge(findings, _finding("env-assignment", path, m.group(0).strip()))
        _scan_text(m.group(2), path + "/env-value", findings)
    for m in JSON_KEY_RE.finditer(text):
        _merge(findings, _finding("json-embedded-secret-key", path, m.group(0)))
        _scan_text(m.group(2), path + "/json-value", findings)
    for m in CAMEL_RE.finditer(text):
        _merge(findings, _finding("camelCase-secret-key", path, m.group(0)))
        _scan_text(m.group(2), path + "/camel-value", findings)
    for m in B64_RE.finditer(text):
        blob = m.group(1)
        inner = _try_b64_utf8(blob)
        if not inner:
            continue
        nested: list[dict[str, Any]] = []
        _scan_text(inner, path + "/b64-utf8", nested)
        if nested:
            _merge(findings, _finding("base64-envelope", path, blob))
            for n in nested:
                _merge(findings, n)


def _walk(obj: Any, path: str, findings: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}/{k}" if path else str(k)
            key_l = str(k).lower().replace("-", "_")
            if key_l in SECRET_FIELD_KEYS and isinstance(v, str) and v:
                _merge(findings, _finding("secret-shaped-field", child, v))
            _walk(v, child, findings)
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk(v, f"{path}[{i}]", findings)
        return
    if isinstance(obj, str):
        _scan_text(obj, path, findings)


def scan(obj: Any, path: str = "$") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    _walk(obj, path, findings)
    if not isinstance(obj, str):
        _scan_text(canonical(obj), "$canonical", findings)
    return findings


def _redact_span(text: str, cls: str, span: str) -> str:
    placeholder = (
        f"{REDACTED_PREFIX}{cls}:{len(span.encode('utf-8'))}:{sha256_text(span)[:12]}]"
    )
    return text.replace(span, placeholder)


def redact(obj: Any) -> Any:
    blob = json.loads(json.dumps(obj))

    def rec(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: rec(v) for k, v in node.items()}
        if isinstance(node, list):
            return [rec(v) for v in node]
        if isinstance(node, str):
            out = node
            for cls, cre in TOKEN_SPECS:
                for m in list(cre.finditer(out)):
                    out = _redact_span(out, cls, m.group(0))
            for m in list(ENV_RE.finditer(out)):
                out = _redact_span(out, "env-assignment", m.group(0).strip())
            for m in list(JSON_KEY_RE.finditer(out)):
                out = _redact_span(out, "json-embedded-secret-key", m.group(0))
            for m in list(CAMEL_RE.finditer(out)):
                out = _redact_span(out, "camelCase-secret-key", m.group(0))
            for m in list(B64_RE.finditer(out)):
                inner = _try_b64_utf8(m.group(1))
                if inner and scan(inner, path="b64"):
                    out = _redact_span(out, "base64-envelope", m.group(1))
            return out
        return node

    return rec(blob)


def payload_path(store: Path, council_id: str) -> Path:
    return store / f"{council_id}.payload.json"


def meta_path(store: Path, council_id: str) -> Path:
    return store / f"{council_id}.meta.json"


def tombstone_path(store: Path, council_id: str) -> Path:
    return store / f"{council_id}.tombstone.json"


def persist(
    transcript: Any,
    store: Path,
    *,
    council_id: str,
    retain_until: datetime | str | None = None,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
    scan_enabled: bool = True,
    **compat: Any,
) -> dict[str, Any]:
    """Write a transcript only when the scan is clean and retention is declared.

    scan_enabled=False is the negative-control hook. Production callers leave True.
    """
    if "scan_enabled" in compat:
        scan_enabled = bool(compat.pop("scan_enabled"))
    if "scan_enabled" in compat:
        scan_enabled = bool(compat.pop("scan_enabled"))
    if compat:
        raise TypeError(f"unexpected persist kwargs {sorted(compat)}")
    now = now or utcnow()
    store.mkdir(parents=True, exist_ok=True)
    if retain_until is None and ttl_seconds is None:
        return {
            "ok": False,
            "refused": True,
            "reason": "retention-undeclared",
            "path": None,
            "findings": [],
            "retain_until": None,
            "payload_sha256": None,
            "wrote": False,
        }
    if isinstance(retain_until, str):
        until = parse_iso(retain_until)
    elif retain_until is not None:
        until = retain_until
    else:
        until = now + timedelta(seconds=int(ttl_seconds))
    findings = scan(transcript) if scan_enabled else []
    if findings:
        return {
            "ok": False,
            "refused": True,
            "reason": "secret-scan-refused-before-persist",
            "path": None,
            "findings": findings_public(findings),
            "retain_until": iso(until),
            "payload_sha256": None,
            "wrote": False,
            "finding_count": len(findings),
            "finding_classes": sorted({f["class"] for f in findings}),
        }
    body = canonical(transcript)
    raw = (body + "\n").encode("utf-8")
    dest = payload_path(store, council_id)
    dest.write_bytes(raw)
    digest = sha256_bytes(raw)
    meta = {
        "council_id": council_id,
        "created_at": iso(now),
        "retain_until": iso(until),
        "payload_sha256": digest,
        "bytes": len(raw),
        "scan_enabled": scan_enabled,
    }
    meta_path(store, council_id).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    tomb = tombstone_path(store, council_id)
    if tomb.exists():
        tomb.unlink()
    return {
        "ok": True,
        "refused": False,
        "reason": "persisted",
        "path": str(dest),
        "findings": [],
        "retain_until": iso(until),
        "payload_sha256": digest,
        "wrote": True,
        "bytes": len(raw),
    }


def sweep(store: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    deleted: list[str] = []
    kept: list[str] = []
    if not store.is_dir():
        return {"deleted": deleted, "kept": kept, "now": iso(now)}
    for meta_file in sorted(store.glob("*.meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        cid = str(meta.get("council_id") or meta_file.name[: -len(".meta.json")])
        until = parse_iso(str(meta["retain_until"]))
        if until <= now:
            payload = payload_path(store, cid)
            payload_sha = str(meta.get("payload_sha256") or "")
            if payload.is_file():
                payload_sha = sha256_bytes(payload.read_bytes())
                payload.unlink()
            tombstone_path(store, cid).write_text(
                json.dumps(
                    {
                        "council_id": cid,
                        "payload_sha256": payload_sha,
                        "retain_until": meta.get("retain_until"),
                        "deleted_at": iso(now),
                        "reason": "retention-expired",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            meta_file.unlink()
            deleted.append(cid)
        else:
            kept.append(cid)
    return {"deleted": deleted, "kept": kept, "now": iso(now)}


class ReplayUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def replay(store: Path, council_id: str) -> dict[str, Any]:
    payload = payload_path(store, council_id)
    tomb = tombstone_path(store, council_id)
    if tomb.is_file() and not payload.is_file():
        stone = json.loads(tomb.read_text(encoding="utf-8"))
        raise ReplayUnavailable(
            "REPLAY_EXPIRED",
            "replay unavailable: payload deleted at retention expiry "
            f"(council_id={council_id} deleted_at={stone.get('deleted_at')})",
        )
    if not payload.is_file():
        raise ReplayUnavailable(
            "REPLAY_MISSING",
            f"replay unavailable: no payload for council_id={council_id}",
        )
    return json.loads(payload.read_text(encoding="utf-8"))


def disk_contains_synthetic_token(store: Path) -> bool:
    """True when any file under store contains the synthetic fixture bytes."""
    needle = SYNTHETIC_TOKEN.encode("utf-8")
    if not store.is_dir():
        return False
    for path in store.rglob("*"):
        if path.is_file() and needle in path.read_bytes():
            return True
    return False


def findings_public(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "class": f["class"],
            "path": f["path"],
            "byte_length": f["byte_length"],
            "sha256": f["sha256"],
            "value_printed": False,
        }
        for f in findings
    ]


# Import aliases so probes can use either spelling without churn.
disk_contains_synthetic_token = disk_contains_synthetic_token
ReplayUnavailable = ReplayUnavailable
utcnow = utcnow
sweep = sweep  # noqa: F811 — re-export
persist = persist  # noqa: F811
