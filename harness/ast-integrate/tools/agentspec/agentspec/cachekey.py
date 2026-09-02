"""Deterministic, clock-free artifact cache key (IMP-0141)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from agentspec.canonical import dumpb, dumps, loads

KEY_FIELDS: tuple[str, ...] = (
    "workflow_id",
    "spec_version",
    "unit_id",
    "resolved_prompt",
    "param_values",
    "tool_policy",
    "input_artifact_hashes",
)
SCHEMA = "ast-integrate/artifact-cache/v1"


def _canon_policy(policy: Any) -> list[str]:
    if policy is None:
        return []
    if isinstance(policy, str):
        return [policy]
    return sorted(str(x) for x in policy)


def _canon_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): value[k] for k in sorted(value, key=str)}


@dataclass(frozen=True)
class CacheInputs:
    workflow_id: str
    spec_version: str
    unit_id: str
    resolved_prompt: str
    param_values: Mapping[str, Any] = field(default_factory=dict)
    tool_policy: tuple[str, ...] | list[str] = field(default_factory=tuple)
    input_artifact_hashes: Mapping[str, str] = field(default_factory=dict)

    def evolve(self, **kwargs: Any) -> "CacheInputs":
        return replace(self, **kwargs)

    def as_canonical_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "spec_version": self.spec_version,
            "unit_id": self.unit_id,
            "resolved_prompt": self.resolved_prompt,
            "param_values": _canon_mapping(self.param_values),
            "tool_policy": _canon_policy(self.tool_policy),
            "input_artifact_hashes": _canon_mapping(self.input_artifact_hashes),
        }


def derive_cache_key(inputs: CacheInputs | Mapping[str, Any]) -> str:
    if isinstance(inputs, CacheInputs):
        payload = inputs.as_canonical_dict()
    else:
        payload = {
            "workflow_id": str(inputs.get("workflow_id") or ""),
            "spec_version": str(inputs.get("spec_version") or ""),
            "unit_id": str(inputs.get("unit_id") or ""),
            "resolved_prompt": str(inputs.get("resolved_prompt") or ""),
            "param_values": _canon_mapping(inputs.get("param_values")),
            "tool_policy": _canon_policy(inputs.get("tool_policy")),
            "input_artifact_hashes": _canon_mapping(inputs.get("input_artifact_hashes")),
        }
    return hashlib.sha256(dumpb(payload)).hexdigest()


def mutant_key_omit_artifact_hashes(inputs: CacheInputs) -> str:
    stripped = inputs.evolve(input_artifact_hashes={})
    return derive_cache_key(stripped)


@dataclass
class Diagnose:
    ok: bool
    reason: str
    payload: bytes | None = None
    action: str = "diagnose"
    fetch_invoked: bool = False
    served_corrupt: bool = False

    def __repr__(self) -> str:
        return f"Diagnose(ok={self.ok}, reason={self.reason!r}, action={self.action!r})"


def diagnose_bytes(raw: bytes, expected_key: str) -> Diagnose:
    if not raw:
        return Diagnose(ok=False, reason="zero-byte")
    try:
        doc = loads(raw.decode("utf-8")) if isinstance(raw, (bytes, bytearray)) else loads(raw)
    except Exception:
        return Diagnose(ok=False, reason="unparseable")
    if not isinstance(doc, dict):
        return Diagnose(ok=False, reason="unparseable")
    if str(doc.get("schema") or "") != SCHEMA:
        return Diagnose(ok=False, reason="wrong-schema")
    if str(doc.get("key") or "") != expected_key:
        return Diagnose(ok=False, reason="key-mismatch")
    hex_payload = str(doc.get("payload_hex") or "")
    try:
        payload = bytes.fromhex(hex_payload)
    except ValueError:
        return Diagnose(ok=False, reason="unparseable")
    digest = str(doc.get("payload_digest") or "")
    live = hashlib.sha256(payload).hexdigest()
    if digest != live:
        return Diagnose(ok=False, reason="payload-digest-mismatch")
    return Diagnose(ok=True, reason="ok", payload=payload)


def mutate_payload_hex_in_place(path: Path) -> None:
    raw = Path(path).read_bytes()
    if not raw:
        Path(path).write_bytes(b"00")
        return
    buf = bytearray(raw)
    buf[0] ^= 0xFF
    Path(path).write_bytes(bytes(buf))


def mutant_serve_without_digest_check(path: Path) -> bytes | None:
    raw = Path(path).read_bytes()
    try:
        doc = loads(raw.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    try:
        return bytes.fromhex(str(doc.get("payload_hex") or ""))
    except ValueError:
        return None


class ArtifactCache:
    def __init__(self, root: Path, fetch: Callable[[CacheInputs], bytes] | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.fetch = fetch

    def path_for(self, inputs: CacheInputs) -> Path:
        key = derive_cache_key(inputs)
        return self.root / f"{key}.json"

    def put(self, inputs: CacheInputs, payload: bytes) -> str:
        key = derive_cache_key(inputs)
        doc = {
            "schema": SCHEMA,
            "key": key,
            "payload_digest": hashlib.sha256(payload).hexdigest(),
            "payload_hex": payload.hex(),
        }
        path = self.path_for(inputs)
        path.write_bytes(dumpb(doc))
        return key

    def get(self, inputs: CacheInputs) -> Diagnose:
        key = derive_cache_key(inputs)
        path = self.path_for(inputs)
        raw = path.read_bytes() if path.is_file() else b""
        diagnosed = diagnose_bytes(raw, key)
        if diagnosed.ok:
            diagnosed.action = "cache-hit"
            return diagnosed
        if self.fetch is None:
            diagnosed.action = "miss"
            return diagnosed
        payload = self.fetch(inputs)
        self.put(inputs, payload)
        return Diagnose(
            ok=True,
            reason=diagnosed.reason,
            payload=payload,
            action="refetch",
            fetch_invoked=True,
            served_corrupt=False,
        )
