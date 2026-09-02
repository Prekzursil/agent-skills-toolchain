#!/usr/bin/env python3
"""Plant the BLD-0003 hostile-class fixture (Linux-safe reserved names)."""
from __future__ import annotations

import shutil
from pathlib import Path

from enumerator import GITCRYPT_MAGIC, READ_CAP_BYTES

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE / "fixtures" / "hostile"
CONTROL_REL = "readable.md"


def plant(root: Path | None = None) -> dict[str, str]:
    root = Path(root or FIXTURE_ROOT)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    (root / ".gitignore").write_text("ignored-plain.md\n", encoding="utf-8")
    (root / CONTROL_REL).write_text(
        "# BLD-0003 control\n"
        "This UTF-8 markdown must not appear in any unreadable class.\n",
        encoding="utf-8",
    )
    (root / "ignored-plain.md").write_text(
        "gitignored utf-8 body; structurally unread by git-ls-files pipelines\n",
        encoding="utf-8",
    )
    (root / "nonutf8.bin").write_bytes(b"\xff\xfe\x00\x01\x80\x81\x82 binary")
    (root / "secret.gitcrypt").write_bytes(
        GITCRYPT_MAGIC + b"\x00\x01fake-ciphertext-not-a-key\x00"
    )
    (root / "oversized.bin").write_bytes(b"B" * (READ_CAP_BYTES + 1))
    (root / "NUL").write_text("reserved-device-body\n", encoding="utf-8")

    parts: list[str] = ["long"]
    chunk = "p" * 50
    rel = "long"
    while len(rel) < 220:
        parts.append(chunk)
        rel = "/".join(parts)
    parts.append("leaf.txt")
    long_path = root.joinpath(*parts)
    long_path.parent.mkdir(parents=True, exist_ok=True)
    long_path.write_text("long-path-leaf utf-8\n", encoding="utf-8")
    long_rel = "/".join(parts)
    return {
        "root": str(root),
        "control": CONTROL_REL,
        "reserved": "NUL",
        "long_path": long_rel,
        "binary": "nonutf8.bin",
        "encrypted": "secret.gitcrypt",
        "oversized": "oversized.bin",
        "gitignored": "ignored-plain.md",
    }


if __name__ == "__main__":
    planted = plant()
    for k, v in planted.items():
        print(f"{k}={v}")
