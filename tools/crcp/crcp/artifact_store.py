"""Content-addressed artifact storage for CRCP payloads."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from pathlib import Path


_PREFIX = "sha256:"
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
DEFAULT_ROOT = Path(
    os.environ.get("CRCP_ARTIFACT_STORE", str(Path.home() / ".crcp" / "artifacts"))
)


def _parse_ref(ref: str) -> str:
    if not isinstance(ref, str) or not ref.startswith(_PREFIX):
        raise ValueError("artifact reference must have the form sha256:<64 hex characters>")
    digest = ref[len(_PREFIX) :]
    if len(digest) != 64 or any(character not in _HEX_DIGITS for character in digest):
        raise ValueError("artifact reference must have the form sha256:<64 hex characters>")
    return digest.lower()


class ArtifactStore:
    """Filesystem store whose keys are SHA-256 content addresses."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, digest: str) -> Path:
        return self.root / "sha256" / digest[:2] / digest[2:]

    def put_bytes(self, data: bytes) -> str:
        """Persist bytes atomically and return their ``sha256:`` reference."""
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        digest = hashlib.sha256(data).hexdigest()
        destination = self._path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.is_file():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise OSError(f"artifact collision or corruption at {destination}")
            return f"{_PREFIX}{digest}"

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".artifact-", dir=destination.parent, delete=False
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, destination)
            temporary_name = None
        finally:
            if temporary_name is not None:
                try:
                    Path(temporary_name).unlink()
                except FileNotFoundError:
                    pass
        return f"{_PREFIX}{digest}"

    def get(self, ref: str) -> bytes:
        """Read and verify an artifact, raising on a bad ref, absence, or corruption."""
        digest = _parse_ref(ref)
        data = self._path(digest).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise OSError(f"artifact failed integrity check: {_PREFIX}{digest}")
        return data


_default_lock = threading.Lock()
_default_store: ArtifactStore | None = None


def _get_default_store() -> ArtifactStore:
    global _default_store
    with _default_lock:
        if _default_store is None:
            _default_store = ArtifactStore(DEFAULT_ROOT)
        return _default_store


def put_bytes(data: bytes) -> str:
    """Store bytes in the default artifact store and return their reference."""
    return _get_default_store().put_bytes(data)


def get(ref: str) -> bytes:
    """Read and verify bytes from the default artifact store."""
    return _get_default_store().get(ref)
