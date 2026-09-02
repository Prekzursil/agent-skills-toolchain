"""Content-addressed blob store."""
from __future__ import annotations

import hashlib
from pathlib import Path


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, blob: bytes) -> str:
        digest = hashlib.sha256(blob).hexdigest()
        dest = self.root / digest
        if not dest.is_file():
            dest.write_bytes(blob)
        return digest

    def get(self, digest: str) -> bytes:
        return (self.root / digest).read_bytes()
