"""Fixture-only publisher identity, update authorisation, and key-recovery drill.

Synthetic Ed25519 keys are minted in memory for this drill. Secrets never leave
the process: they are not written to disk, not serialised into probe JSON, and
are not production credentials. Real-world rotation remains an owner action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ACTION_ACCEPT = "ACCEPTED"
ACTION_REFUSE = "REFUSED"
ALGO = "ed25519"


class FixtureError(ValueError):
    """Authorisation or verification failed closed."""


@dataclass
class SyntheticKey:
    key_id: str
    public_hex: str
    _secret: Ed25519PrivateKey = field(repr=False, compare=False)

    def public_record(self) -> dict[str, str]:
        return {"key_id": self.key_id, "public_hex": self.public_hex, "algorithm": ALGO}


def mint_synthetic_key(key_id: str) -> SyntheticKey:
    """Fixture-only keygen. Never called from production marketplace code."""
    secret = Ed25519PrivateKey.generate()
    public_hex = secret.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return SyntheticKey(key_id=key_id, public_hex=public_hex, _secret=secret)


def canonical_bytes(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass
class KeyRecord:
    key_id: str
    public_hex: str
    valid_from: str
    valid_until: str
    revoked_at: str | None = None

    def as_public(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "public_hex": self.public_hex,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "revoked_at": self.revoked_at,
        }


@dataclass
class Publisher:
    publisher_id: str
    display_name: str
    keys: dict[str, KeyRecord] = field(default_factory=dict)

    def as_public(self) -> dict[str, Any]:
        return {
            "publisher_id": self.publisher_id,
            "display_name": self.display_name,
            "keys": [k.as_public() for k in self.keys.values()],
        }


@dataclass
class Artifact:
    package: str
    version: str
    owner_id: str
    signed_as: str
    key_id: str
    signed_at: str
    payload_sha256: str
    signature_hex: str
    algorithm: str = ALGO

    def body(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "version": self.version,
            "owner_id": self.owner_id,
            "signed_as": self.signed_as,
            "key_id": self.key_id,
            "signed_at": self.signed_at,
            "payload_sha256": self.payload_sha256,
            "algorithm": self.algorithm,
        }

    def as_public(self) -> dict[str, Any]:
        out = self.body()
        out["signature_hex"] = self.signature_hex
        return out


@dataclass
class Decision:
    action: str
    reason: str

    @property
    def accepted(self) -> bool:
        return self.action == ACTION_ACCEPT


def sign_artifact(
    *,
    key: SyntheticKey,
    package: str,
    version: str,
    owner_id: str,
    signed_as: str,
    signed_at: str,
    payload: bytes,
) -> Artifact:
    art = Artifact(
        package=package,
        version=version,
        owner_id=owner_id,
        signed_as=signed_as,
        key_id=key.key_id,
        signed_at=signed_at,
        payload_sha256=payload_digest(payload),
        signature_hex="",
    )
    art.signature_hex = key._secret.sign(canonical_bytes(art.body())).hex()
    return art


def verify_artifact_signature(artifact: Artifact, public_hex: str) -> None:
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
    try:
        pub.verify(bytes.fromhex(artifact.signature_hex), canonical_bytes(artifact.body()))
    except (InvalidSignature, ValueError) as exc:
        raise FixtureError("signature mismatch") from exc


class FixtureRegistry:
    """In-memory fixture registry with an update-authorisation check.

    A package's owner is the publisher who first created it. Updates must be
    authenticated as that owner. Identity B cannot update identity A's package.
    """

    def __init__(self, *, enforce_owner: bool = True) -> None:
        self.enforce_owner = enforce_owner
        self.publishers: dict[str, Publisher] = {}
        self.packages: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []

    def register_publisher(
        self,
        publisher_id: str,
        display_name: str,
        key: SyntheticKey,
        valid_from: str,
        valid_until: str,
    ) -> Publisher:
        rec = KeyRecord(
            key_id=key.key_id,
            public_hex=key.public_hex,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        pub = Publisher(publisher_id=publisher_id, display_name=display_name, keys={rec.key_id: rec})
        self.publishers[publisher_id] = pub
        return pub

    def attach_key(
        self, publisher_id: str, key: SyntheticKey, valid_from: str, valid_until: str
    ) -> KeyRecord:
        pub = self.publishers[publisher_id]
        rec = KeyRecord(
            key_id=key.key_id,
            public_hex=key.public_hex,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        pub.keys[rec.key_id] = rec
        return rec

    def _authorise_update(self, package: str, authenticated_as: str) -> Decision:
        existing = self.packages.get(package)
        if existing is None:
            return Decision(ACTION_ACCEPT, "new package; authenticated publisher becomes owner")
        owner = existing["owner_id"]
        if not self.enforce_owner:
            return Decision(ACTION_ACCEPT, "naive registry skipped owner check")
        if authenticated_as != owner:
            return Decision(
                ACTION_REFUSE,
                f"update of {package} owned by {owner} refused for authenticated {authenticated_as}",
            )
        return Decision(ACTION_ACCEPT, "authenticated publisher is the package owner")

    def publish(
        self,
        *,
        authenticated_as: str,
        key: SyntheticKey,
        package: str,
        version: str,
        payload: bytes,
        signed_at: str,
    ) -> tuple[Decision, Artifact | None]:
        pub = self.publishers.get(authenticated_as)
        if pub is None:
            return Decision(ACTION_REFUSE, f"unknown publisher {authenticated_as}"), None
        rec = pub.keys.get(key.key_id)
        if rec is None or rec.public_hex != key.public_hex:
            return Decision(ACTION_REFUSE, "signing key is not bound to authenticated identity"), None
        if rec.revoked_at is not None and signed_at > rec.revoked_at:
            return Decision(
                ACTION_REFUSE,
                f"signing key {key.key_id} revoked at {rec.revoked_at}",
            ), None
        owner_id = self.packages[package]["owner_id"] if package in self.packages else authenticated_as
        auth = self._authorise_update(package, authenticated_as)
        if not auth.accepted:
            self.events.append(
                {
                    "kind": "publish-refused",
                    "package": package,
                    "version": version,
                    "authenticated_as": authenticated_as,
                    "reason": auth.reason,
                }
            )
            return auth, None
        artifact = sign_artifact(
            key=key,
            package=package,
            version=version,
            owner_id=owner_id,
            signed_as=authenticated_as,
            signed_at=signed_at,
            payload=payload,
        )
        versions = self.packages.setdefault(
            package, {"owner_id": owner_id, "versions": {}}
        )["versions"]
        versions[version] = {"artifact": artifact.as_public(), "payload_sha256": artifact.payload_sha256}
        self.events.append(
            {
                "kind": "publish-accepted",
                "package": package,
                "version": version,
                "authenticated_as": authenticated_as,
                "owner_id": owner_id,
                "key_id": key.key_id,
            }
        )
        return Decision(ACTION_ACCEPT, auth.reason), artifact

    def documented_recovery_procedure(
        self,
        *,
        publisher_id: str,
        compromised_key_id: str,
        replacement: SyntheticKey,
        revoked_at: str,
        replacement_valid_until: str,
    ) -> list[dict[str, Any]]:
        """Execute the documented fixture recovery. Does not mint keys.

        Steps:
          1. Stamp revoked_at on the compromised key (revocation point).
          2. Attach an already-minted fixture replacement public key.
          3. Record the identity document so consumers can refresh.
        Real production credentials are not read, rotated, or revoked.
        """
        steps: list[dict[str, Any]] = []
        pub = self.publishers[publisher_id]
        compromised = pub.keys.get(compromised_key_id)
        if compromised is None:
            raise FixtureError(f"unknown key {compromised_key_id}")
        compromised.revoked_at = revoked_at
        steps.append(
            {
                "step": 1,
                "action": "stamp-revocation-point",
                "key_id": compromised_key_id,
                "revoked_at": revoked_at,
            }
        )
        self.attach_key(
            publisher_id,
            replacement,
            valid_from=revoked_at,
            valid_until=replacement_valid_until,
        )
        steps.append(
            {
                "step": 2,
                "action": "attach-replacement-public-key",
                "replacement_key_id": replacement.key_id,
                "replacement_public_hex": replacement.public_hex,
            }
        )
        steps.append(
            {
                "step": 3,
                "action": "publish-updated-identity-document",
                "publisher": pub.as_public(),
            }
        )
        self.events.append(
            {
                "kind": "recovery",
                "publisher_id": publisher_id,
                "compromised_key_id": compromised_key_id,
                "replacement_key_id": replacement.key_id,
                "revoked_at": revoked_at,
            }
        )
        return steps


class Consumer:
    """Consumer-side acceptance. Honours revocation points on already-trusted keys."""

    def __init__(self, *, honor_revocation_point: bool = True) -> None:
        self.honor_revocation_point = honor_revocation_point
        self.trusted: dict[str, Publisher] = {}

    def trust_from_registry(self, registry: FixtureRegistry, publisher_id: str) -> None:
        src = registry.publishers[publisher_id]
        clone_keys = {
            kid: KeyRecord(
                key_id=rec.key_id,
                public_hex=rec.public_hex,
                valid_from=rec.valid_from,
                valid_until=rec.valid_until,
                revoked_at=rec.revoked_at,
            )
            for kid, rec in src.keys.items()
        }
        self.trusted[publisher_id] = Publisher(
            publisher_id=src.publisher_id,
            display_name=src.display_name,
            keys=clone_keys,
        )

    def refresh_identity(self, registry: FixtureRegistry, publisher_id: str) -> None:
        self.trust_from_registry(registry, publisher_id)

    def accept(self, artifact: Artifact) -> Decision:
        pub = self.trusted.get(artifact.owner_id) or self.trusted.get(artifact.signed_as)
        if pub is None:
            return Decision(ACTION_REFUSE, "publisher is not in the consumer trust store")
        rec = pub.keys.get(artifact.key_id)
        if rec is None:
            return Decision(ACTION_REFUSE, f"unknown key {artifact.key_id}")
        if artifact.signed_at < rec.valid_from or artifact.signed_at > rec.valid_until:
            return Decision(ACTION_REFUSE, "signature outside key validity window")
        if (
            self.honor_revocation_point
            and rec.revoked_at is not None
            and artifact.signed_at > rec.revoked_at
        ):
            return Decision(
                ACTION_REFUSE,
                f"artifact signed at {artifact.signed_at} after revocation point {rec.revoked_at}",
            )
        try:
            verify_artifact_signature(artifact, rec.public_hex)
        except FixtureError as exc:
            return Decision(ACTION_REFUSE, str(exc))
        return Decision(ACTION_ACCEPT, "signature valid under trusted key and revocation policy")


def production_publisher_surface(repo: Path) -> dict[str, Any]:
    """Census of the production marketplace tree. Does not implement IMP-0075."""
    rels = [
        "tools/marketplace/publisher_identity.py",
        "tools/marketplace/schema/publisher.schema.json",
        "tools/marketplace/tests/test_publisher_identity.py",
        "tools/marketplace/update_authorization.py",
        "tools/marketplace/publish.py",
    ]
    present = {rel: (repo / rel).is_file() for rel in rels}
    return {
        "files": present,
        "any_present": any(present.values()),
        "note": (
            "IMP-0075 publisher-identity consumption and the production publish "
            "path are absent on this worktree. ADV-0063 exercises a fixture registry."
        ),
    }
