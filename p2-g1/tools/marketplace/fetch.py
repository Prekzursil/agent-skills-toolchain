"""Marketplace fetch helpers."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


class FetchError(Exception):
    """Blob fetch failed (absent path, I/O, or HTTP)."""


def fetch(url: str, dest: str | Path | None = None, timeout: float = 20, **kwargs: Any) -> bytes:
    try:
        with urlopen(url, timeout=timeout) as resp:  # noqa: S310
            data = resp.read()
    except (URLError, OSError, ValueError) as exc:
        raise FetchError(str(exc)) from exc
    if dest is not None:
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def get(url: str, **kwargs: Any) -> bytes:
    return fetch(url, **kwargs)


def fetch_to_cache(src: str | Path, cache_dir: str | Path) -> Path:
    """Copy a local blob into cache_dir and return the cached path.

    Does not fetch from the network. A missing source raises FetchError so
    installers can fail closed instead of falling back to an unpinned blob.
    """
    source = Path(src)
    dest_dir = Path(cache_dir)
    if not source.is_file():
        raise FetchError(f"absent source blob: {source}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    try:
        shutil.copy2(source, dest)
    except OSError as exc:
        raise FetchError(str(exc)) from exc
    return dest
