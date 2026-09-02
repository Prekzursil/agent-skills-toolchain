#!/usr/bin/env python3
"""First-command-after-install for an isolated capability profile.

Cold path: walk the install prefix (via tools.plugin.census), hash every
capability body, and write a capability-index cache.

Warm path: load that cache and do not rebuild.

A nested (quadratic) builder exists only as a detector control so the
scaling probe can prove it would reject an unbounded index rebuild.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.plugin.census import plugin_root, tree_files  # noqa: E402

Builder = Literal["linear", "quadratic"]

SKILL_NAME = "SKILL.md"
CACHE_REL = Path(".ast") / "capability-index.json"
MANIFEST_NAME = "manifest.json"
HASH_ROUNDS = 48
BODY_BYTES = 12288
BASE_N = 20


def seed_install(profile: Path, n: int, *, body_bytes: int = BODY_BYTES) -> list[str]:
    """Write n unique installed capabilities under profile/prefix/plugins."""
    prefix = profile / "prefix"
    names: list[str] = []
    for i in range(n):
        name = f"cap-{i:04d}"
        root = plugin_root(prefix, name)
        root.mkdir(parents=True, exist_ok=True)
        (root / "plugin.json").write_text(
            json.dumps({"name": name, "version": "1.0.0", "id": name}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (root / "health.json").write_text(
            json.dumps({"version": "1.0.0", "ok": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        header = f"# {name}\ninstalled-capability body\n".encode("utf-8")
        pad = (name.encode("utf-8") * (body_bytes // max(len(name), 1) + 3))[
            : max(0, body_bytes - len(header))
        ]
        (root / SKILL_NAME).write_bytes(header + pad)
        names.append(name)
    (profile / MANIFEST_NAME).write_text(
        json.dumps({"packages": names, "n": n}, indent=2) + "\n",
        encoding="utf-8",
    )
    return names


def installed_names(profile: Path) -> list[str]:
    doc = json.loads((profile / MANIFEST_NAME).read_text(encoding="utf-8"))
    return [str(x) for x in doc["packages"]]


def cache_path(profile: Path) -> Path:
    return profile / CACHE_REL


def _hash_body(data: bytes, rounds: int = HASH_ROUNDS) -> str:
    h = hashlib.sha256()
    for _ in range(max(1, rounds)):
        h.update(data)
    return h.hexdigest()


def load_install_blobs(profile: Path) -> tuple[list[str], list[bytes], list[dict[str, str]]]:
    """Census each installed package and read its SKILL body (cold I/O)."""
    prefix = profile / "prefix"
    names = installed_names(profile)
    blobs: list[bytes] = []
    censuses: list[dict[str, str]] = []
    for name in names:
        root = plugin_root(prefix, name)
        files = tree_files(root)
        if SKILL_NAME not in files:
            raise FileNotFoundError(f"{name} missing {SKILL_NAME}")
        blobs.append((root / SKILL_NAME).read_bytes())
        censuses.append(files)
    return names, blobs, censuses


def build_index_linear(profile: Path) -> dict[str, Any]:
    names, blobs, censuses = load_install_blobs(profile)
    caps = []
    for name, body, files in zip(names, blobs, censuses):
        caps.append(
            {
                "id": name,
                "sha256": _hash_body(body),
                "bytes": len(body),
                "file_count": len(files),
                "census_sha256": hashlib.sha256(
                    json.dumps(files, sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "builder": "linear",
        "count": len(caps),
        "capabilities": caps,
    }


def build_index_quadratic(profile: Path) -> dict[str, Any]:
    """O(n^2): re-census every other package for each capability. Detector only."""
    names = installed_names(profile)
    prefix = profile / "prefix"
    caps = []
    for i, name in enumerate(names):
        acc = hashlib.sha256()
        file_count = 0
        self_bytes = 0
        for other in names:
            root = plugin_root(prefix, other)
            files = tree_files(root)
            body = (root / SKILL_NAME).read_bytes()
            acc.update(body)
            acc.update(str(i).encode("ascii"))
            for digest in files.values():
                acc.update(digest.encode("ascii"))
            if other == name:
                file_count = len(files)
                self_bytes = len(body)
        caps.append(
            {
                "id": name,
                "sha256": acc.hexdigest(),
                "bytes": self_bytes,
                "file_count": file_count,
            }
        )
    return {
        "builder": "quadratic",
        "count": len(caps),
        "capabilities": caps,
    }


def write_cache(profile: Path, index: dict[str, Any]) -> Path:
    path = cache_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_cache(profile: Path) -> dict[str, Any] | None:
    path = cache_path(profile)
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "count" not in doc:
        return None
    return doc


def drop_cache(profile: Path) -> None:
    path = cache_path(profile)
    if path.is_file():
        path.unlink()


def first_command(
    profile: Path,
    *,
    force_cold: bool = False,
    builder: Builder = "linear",
) -> dict[str, Any]:
    """Run the first command against an installed profile.

    Returns mode ('cold' | 'warm'), capability count, and the index used.
    """
    if force_cold:
        drop_cache(profile)
    cached = None if force_cold else read_cache(profile)
    if cached is not None and cached.get("builder") == builder:
        return {
            "ok": True,
            "mode": "warm",
            "count": int(cached["count"]),
            "builder": builder,
            "cache": str(cache_path(profile)),
            "index": cached,
        }
    if builder == "quadratic":
        index = build_index_quadratic(profile)
    else:
        index = build_index_linear(profile)
    write_cache(profile, index)
    return {
        "ok": True,
        "mode": "cold",
        "count": int(index["count"]),
        "builder": builder,
        "cache": str(cache_path(profile)),
        "index": index,
    }


def main() -> int:
    import argparse
    import tempfile

    p = argparse.ArgumentParser(description="TST-0239 first-command harness")
    p.add_argument("--n", type=int, default=BASE_N)
    p.add_argument("--cold", action="store_true")
    p.add_argument("--builder", choices=("linear", "quadratic"), default="linear")
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="tst0239-") as tmp:
        profile = Path(tmp)
        seed_install(profile, args.n)
        result = first_command(
            profile, force_cold=args.cold, builder=args.builder
        )
        print(json.dumps({k: result[k] for k in ("ok", "mode", "count", "builder")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Aliases consumed by scenario.py
BASE_N = BASE_N
BODY_BYTES = BODY_BYTES
seed_install = seed_install
