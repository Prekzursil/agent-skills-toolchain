"""Deterministic install/snapshot trees for CNF-0046.

V1 is the rollback source. V2 is the installed (current) tree. The client
holds the loaded module and the active hook — analogues of a running Windows
client's open handles — and leaves the log unlocked so a skip-on-error
rollback can produce a mixed-version tree.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

FILES: dict[str, tuple[bytes, bytes]] = {
    "plugin.py": (
        b"CNF-0046-V1 plugin body\n",
        b"CNF-0046-V2 plugin body\n",
    ),
    "hooks/hook.py": (
        b"CNF-0046-V1 hook body\n",
        b"CNF-0046-V2 hook body\n",
    ),
    "logs/active.log": (
        b"CNF-0046-V1 log body\n",
        b"CNF-0046-V2 log body\n",
    ),
}
LOCKED_RELS = ("plugin.py", "hooks/hook.py")
UNLOCKED_REL = "logs/active.log"


def lf_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def known_hashes() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {"v1": {}, "v2": {}}
    for rel, (v1, v2) in FILES.items():
        out["v1"][rel] = lf_sha(v1)
        out["v2"][rel] = lf_sha(v2)
    return out


def write_tree(root: Path, version: str) -> None:
    idx = 0 if version == "v1" else 1
    for rel, pair in FILES.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(pair[idx])


def build_prefix(root: Path) -> dict[str, Path]:
    snapshot = root / "snapshot"
    prefix = root / "prefix"
    write_tree(snapshot, "v1")
    write_tree(prefix, "v2")
    return {"snapshot": snapshot, "prefix": prefix}
