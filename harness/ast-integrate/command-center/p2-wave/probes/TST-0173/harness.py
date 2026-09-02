"""Shared origin, corruption, and SilentCache (known-broken) for TST-0173."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from artifact_cache.store import IntegrityCache, sha256_bytes  # noqa: E402

SEED = 1730173
PAYLOAD_N = 2048
FUZZ_N = 500
KEY = "pkg-fixed-1.0.0"


class Origin:
    """Authoritative bytes plus a fetch counter. Digest is independent of cache."""

    def __init__(self, payload: bytes) -> None:
        self.payload = bytes(payload)
        self.digest = sha256_bytes(self.payload)
        self.fetch_count = 0

    def fetch(self, key: str) -> bytes:
        del key
        self.fetch_count += 1
        return bytes(self.payload)


class SilentCache:
    """Known-broken: serves on-disk bytes with no checksum and no refetch."""

    def __init__(self, inner: IntegrityCache) -> None:
        self.inner = inner

    def payload_path(self, key: str) -> Path:
        return self.inner.payload_path(key)

    def fill(self, key: str) -> None:
        self.inner.get(key)

    def get_silent(self, key: str) -> dict[str, Any]:
        path = self.payload_path(key)
        data = path.read_bytes()
        return {
            "payload": data,
            "digest": sha256_bytes(data),
            "source": "cache-unchecked",
            "mismatch": False,
            "events": [],
        }


def patterned_payload(n: int = PAYLOAD_N, seed: int = SEED) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(n))


def flip_bit(path: Path, offset: int, bit: int) -> dict[str, Any]:
    data = bytearray(path.read_bytes())
    if not data:
        raise ValueError("empty payload")
    offset = offset % len(data)
    bit = bit % 8
    before = bytes(data)
    data[offset] ^= 1 << bit
    after = bytes(data)
    path.write_bytes(after)
    return {
        "kind": "single-bit",
        "offset": offset,
        "bit": bit,
        "before_digest": sha256_bytes(before),
        "after_digest": sha256_bytes(after),
        "changed": before != after,
    }


def multi_byte(path: Path, rng: random.Random) -> dict[str, Any]:
    data = bytearray(path.read_bytes())
    if len(data) < 2:
        raise ValueError("payload too small")
    length = rng.randint(2, min(16, len(data)))
    offset = rng.randrange(0, len(data) - length + 1)
    before = bytes(data)
    patch = bytes(rng.randrange(256) for _ in range(length))
    if patch == before[offset : offset + length]:
        patch = bytes((b ^ 0xFF) for b in patch)
    data[offset : offset + length] = patch
    after = bytes(data)
    path.write_bytes(after)
    return {
        "kind": "multi-byte",
        "offset": offset,
        "length": length,
        "before_digest": sha256_bytes(before),
        "after_digest": sha256_bytes(after),
        "changed": before != after,
    }


def make_cache(root: Path, origin: Origin) -> IntegrityCache:
    return IntegrityCache(root, origin.fetch)


def recovery_ok(
    *,
    origin: Origin,
    result_digest: str,
    result_payload: bytes,
    served_digest_before_recovery: str,
    mismatch_events: list[dict[str, Any]],
    fetches_before: int,
    fetches_after: int,
    crashed: bool,
) -> dict[str, Any]:
    independent = sha256_bytes(origin.payload)
    served_corrupt = result_payload != origin.payload
    ok = (
        not crashed
        and not served_corrupt
        and result_digest == origin.digest == independent
        and served_digest_before_recovery != origin.digest
        and len(mismatch_events) >= 1
        and fetches_after == fetches_before + 1
    )
    return {
        "ok": ok,
        "crashed": crashed,
        "served_corrupt": served_corrupt,
        "result_digest": result_digest,
        "authoritative_digest": origin.digest,
        "independent_origin_digest": independent,
        "corrupt_digest": served_digest_before_recovery,
        "mismatch_events": len(mismatch_events),
        "refetch_observed": fetches_after == fetches_before + 1,
        "fetches_before": fetches_before,
        "fetches_after": fetches_after,
    }
