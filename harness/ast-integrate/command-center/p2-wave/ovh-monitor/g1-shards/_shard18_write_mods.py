#!/usr/bin/env python3
"""Write real production modules required by shard-18 G-1 probes."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def put(rel: str, body: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print("W", rel, path.stat().st_size)


SIGNATURE = r'''"""Detached ed25519 package-digest signatures. Strict canonical wire."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

VALID = "VALID"
INVALID = "INVALID"
UNSIGNED = "UNSIGNED"
ALG = "ed25519"


@dataclass(frozen=True)
class VerifyResult:
    status: str
    reason: str = ""
    reason_code: str = ""
    key_id: str | None = None


def package_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode_record(record: Mapping[str, Any]) -> bytes:
    obj = {
        "algorithm": str(record["algorithm"]),
        "digest": str(record["digest"]),
        "key_id": str(record["key_id"]),
        "signature": str(record["signature"]),
    }
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")


def sign_record(priv: Ed25519PrivateKey, *, digest: str, key_id: str) -> dict[str, str]:
    sig = priv.sign(digest.encode("ascii"))
    return {
        "algorithm": ALG,
        "digest": digest,
        "key_id": key_id,
        "signature": sig.hex(),
    }


def _result(status: str, *, reason: str = "", reason_code: str = "", key_id: str | None = None) -> VerifyResult:
    return VerifyResult(status=status, reason=reason, reason_code=reason_code, key_id=key_id)


def verify_signature(digest: str, record: Mapping[str, Any] | None, store: Mapping[str, str]) -> VerifyResult:
    if record is None:
        return _result(UNSIGNED, reason="unsigned package", reason_code="unsigned")
    alg = str(record.get("algorithm") or "")
    if alg != ALG:
        return _result(INVALID, reason=f"unsupported algorithm {alg}", reason_code="unsupported-algorithm")
    rec_digest = str(record.get("digest") or "")
    if rec_digest != digest:
        return _result(INVALID, reason="digest mismatch", reason_code="digest-mismatch")
    key_id = str(record.get("key_id") or "")
    if key_id not in store:
        return _result(INVALID, reason="unknown key id", reason_code="unknown-key-id")
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(str(store[key_id])))
        pub.verify(bytes.fromhex(str(record.get("signature") or "")), digest.encode("ascii"))
    except Exception:
        return _result(INVALID, reason="signature mismatch", reason_code="signature-mismatch", key_id=key_id)
    return _result(VALID, reason="ok", reason_code="ok", key_id=key_id)


def _duplicate_keys(raw: bytes) -> bool:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return False
    decoder = json.JSONDecoder()

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate")
        return dict(pairs)

    try:
        decoder.decode(text, object_pairs_hook=hook)  # type: ignore[call-arg]
    except TypeError:
        try:
            json.loads(text, object_pairs_hook=hook)
        except ValueError:
            return True
        return False
    except ValueError:
        return True
    return False


def verify_wire(wire: bytes, digest: str, store: Mapping[str, str]) -> VerifyResult:
    if b"\\u" in wire:
        return _result(INVALID, reason="non-canonical unicode escape", reason_code="non-canonical")
    try:
        text = wire.decode("ascii")
    except UnicodeDecodeError:
        return _result(INVALID, reason="malformed encoding", reason_code="malformed")

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate")
        return dict(pairs)

    try:
        obj = json.loads(text, object_pairs_hook=hook)
    except ValueError:
        return _result(INVALID, reason="duplicate keys or malformed", reason_code="malformed")
    except json.JSONDecodeError:
        return _result(INVALID, reason="malformed json", reason_code="malformed")
    if not isinstance(obj, dict):
        return _result(INVALID, reason="not object", reason_code="malformed")
    try:
        canon = encode_record(obj)
    except Exception:
        return _result(INVALID, reason="missing fields", reason_code="malformed")
    if canon != wire:
        return _result(INVALID, reason="non-canonical encoding", reason_code="non-canonical")
    return verify_signature(digest, obj, store)
'''

VERIFY = r'''"""Install-time signature gate. Fail-closed."""
from __future__ import annotations

from typing import Any, Mapping

from marketplace.signature import VALID, verify_signature

GATE_SIGNATURE = "GATE_SIGNATURE"
GATE_COMPATIBILITY = "GATE_COMPATIBILITY"
GATE_LOCKFILE_DIGEST = "GATE_LOCKFILE_DIGEST"
GATE_REVOCATION = "GATE_REVOCATION"
VERIFY_ORDER = ("signature", "revocation", "compatibility", "lockfile")


class GateFailure(Exception):
    def __init__(self, message: str, gate: str = GATE_SIGNATURE) -> None:
        super().__init__(message)
        self.gate = gate


def check_signature(digest: str, record: Mapping[str, Any] | None, store: Mapping[str, str]) -> str:
    result = verify_signature(digest, record, store)
    if result.status != VALID:
        raise GateFailure(result.reason or result.status, gate=GATE_SIGNATURE)
    if not result.key_id:
        raise GateFailure("valid without key id", gate=GATE_SIGNATURE)
    return result.key_id
'''

PACKAGE_CACHE = r'''"""Content-addressed package cache used by ADV-0024 marketplace-publish."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ContentAddressedPackageCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)

    def _registry_path(self) -> Path:
        return self.root / "registry.json"

    def _load(self) -> dict[str, Any]:
        path = self._registry_path()
        if not path.is_file():
            return {"packages": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, doc: dict[str, Any]) -> None:
        self._registry_path().write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def blob_path(self, digest: str) -> Path:
        return self.root / "blobs" / str(digest)

    def publish(self, name: str, payload: bytes, version: str) -> dict[str, Any]:
        digest = _digest(payload)
        dest = self.blob_path(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        src = self.root / "source" / name / digest
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(payload)
        entry = {
            "name": name,
            "version": version,
            "digest": digest,
            "bytes": len(payload),
        }
        doc = self._load()
        packages = doc.setdefault("packages", {})
        packages[f"{name}@{version}"] = entry
        self._save(doc)
        return entry
'''

DISCLOSURE = r'''"""Coordinated-disclosure state machine with owner-gated public disclose."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class State(Enum):
    REPORTED = "reported"
    TRIAGED = "triaged"
    EMBARGOED = "embargoed"
    FIX_AVAILABLE = "fix_available"
    DISCLOSED = "disclosed"
    WITHDRAWN = "withdrawn"


STATES: tuple[State, ...] = (
    State.REPORTED,
    State.TRIAGED,
    State.EMBARGOED,
    State.FIX_AVAILABLE,
    State.DISCLOSED,
    State.WITHDRAWN,
)

LEGAL_TRANSITIONS: frozenset[tuple[State, State]] = frozenset(
    {
        (State.REPORTED, State.TRIAGED),
        (State.REPORTED, State.WITHDRAWN),
        (State.TRIAGED, State.EMBARGOED),
        (State.TRIAGED, State.FIX_AVAILABLE),
        (State.TRIAGED, State.DISCLOSED),
        (State.TRIAGED, State.WITHDRAWN),
        (State.EMBARGOED, State.FIX_AVAILABLE),
        (State.EMBARGOED, State.DISCLOSED),
        (State.EMBARGOED, State.WITHDRAWN),
        (State.FIX_AVAILABLE, State.DISCLOSED),
        (State.FIX_AVAILABLE, State.WITHDRAWN),
        (State.FIX_AVAILABLE, State.EMBARGOED),
    }
)


class IllegalTransition(Exception):
    def __init__(self, message: str, code: str = "illegal-transition") -> None:
        super().__init__(message)
        self.code = code


class OwnerGated(Exception):
    def __init__(self, message: str, code: str = "owner-gated") -> None:
        super().__init__(message)
        self.code = code


def legal_transition_edges() -> list[dict[str, str]]:
    return [{"from": a.value, "to": b.value} for a, b in sorted(LEGAL_TRANSITIONS, key=lambda x: (x[0].value, x[1].value))]


@dataclass
class Advisory:
    id: str
    package_id: str
    detail: str
    state: State = State.REPORTED
    actor: str = "reporter"


@dataclass
class EventLog:
    events: list[dict[str, str]] = field(default_factory=list)

    def add(self, *, advisory_id: str, frm: str, to: str, actor: str) -> None:
        self.events.append(
            {
                "advisory_id": advisory_id,
                "from": frm,
                "to": to,
                "actor": actor,
            }
        )

    def dump_text(self) -> str:
        # Lifecycle names only — never advisory detail.
        lines = [f"{e['advisory_id']} {e['from']}->{e['to']} actor={e['actor']}" for e in self.events]
        return "\n".join(lines)


class DisclosureRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Advisory] = {}
        self.log = EventLog()

    def create(self, package_id: str, detail: str, actor: str = "reporter") -> Advisory:
        rec = Advisory(id=str(uuid.uuid4()), package_id=package_id, detail=detail, actor=actor)
        self._items[rec.id] = rec
        self.log.add(advisory_id=rec.id, frm="none", to=rec.state.value, actor=actor)
        return rec

    def get(self, aid: str) -> Advisory:
        return self._items[aid]

    def transition(
        self,
        aid: str,
        target: State,
        actor: str = "triager",
        owner_approved: bool = False,
    ) -> Advisory:
        rec = self._items[aid]
        if rec.state is target:
            if (rec.state, target) not in LEGAL_TRANSITIONS:
                raise IllegalTransition(f"{rec.state.value}->{target.value}", code="illegal-transition")
            return rec
        if (rec.state, target) not in LEGAL_TRANSITIONS:
            raise IllegalTransition(f"{rec.state.value}->{target.value}", code="illegal-transition")
        if target is State.DISCLOSED and not owner_approved:
            raise OwnerGated("disclose requires owner approval", code="owner-gated")
        frm = rec.state
        rec.state = target
        self.log.add(advisory_id=rec.id, frm=frm.value, to=target.value, actor=actor)
        return rec
'''

PUBLIC_API = r'''"""Public read API that withholds embargoed detail."""
from __future__ import annotations

import json

from marketplace.disclosure import DisclosureRegistry, State


def get_json(reg: DisclosureRegistry, aid: str) -> str:
    rec = reg.get(aid)
    if rec.state is State.DISCLOSED:
        body = {
            "id": rec.id,
            "package_id": rec.package_id,
            "disclosed": True,
            "detail": rec.detail,
            "state": rec.state.value,
        }
    else:
        body = {"id": rec.id, "package_id": rec.package_id, "disclosed": False}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def list_json(reg: DisclosureRegistry) -> str:
    rows = []
    for rec in reg._items.values():
        if rec.state is State.DISCLOSED:
            rows.append(
                {
                    "id": rec.id,
                    "package_id": rec.package_id,
                    "disclosed": True,
                    "detail": rec.detail,
                    "state": rec.state.value,
                }
            )
    return json.dumps({"advisories": rows}, sort_keys=True, separators=(",", ":"))
'''


def main() -> None:
    put("tools/marketplace/signature.py", SIGNATURE)
    put("marketplace/signature.py", SIGNATURE.replace("from marketplace.signature", "from tools.marketplace.signature") if False else SIGNATURE)
    put("tools/marketplace/verify.py", VERIFY)
    put("marketplace/verify.py", VERIFY)
    put("tools/marketplace/package_cache.py", PACKAGE_CACHE)
    put("marketplace/package_cache.py", PACKAGE_CACHE)
    put("tools/marketplace/disclosure.py", DISCLOSURE)
    put("marketplace/disclosure.py", DISCLOSURE)
    put("tools/marketplace/public_api.py", PUBLIC_API)
    put("marketplace/public_api.py", PUBLIC_API)


if __name__ == "__main__":
    main()
