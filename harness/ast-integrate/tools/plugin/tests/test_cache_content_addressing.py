#!/usr/bin/env python3
"""Content-addressed plugin cache (IMP-0040): a source byte change forces a new key.

Oracles (each returns the measurements it made, and asserts them):
* ``test_source_change_forces_new_key``  -- flip one source byte, serve, compare the
  served bytes with ``produce(new_source)`` (content comparison, never a hit-rate
  counter) and list the on-disk keys before/after.
* ``test_time_based_cache_fails_within_ttl`` -- NEGATIVE CONTROL (both-states): a
  cache keyed by plugin id+version with a TTL serves the STALE artefact inside its
  window and only recovers once the window expires.
* ``test_concurrent_read_write_does_not_corrupt`` -- writers and readers race on
  the same entries; every read is a complete artefact, never a torn one.

Runnable standalone: ``python3 -B test_cache_content_addressing.py
[ContentAddressingTests.<method>]`` and under pytest.
"""
from __future__ import annotations

import ast
import hashlib
import sys
import tempfile
import threading
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
REAPER = PLUGIN.parent / "plugin-cache-reaper"
sys.path.insert(0, str(REAPER))
import reap as R  # noqa: E402

PLUGIN_VERSION = "1.2.3"
SRC_OLD = b"def produce():\n    return b'OLD-PAYLOAD'\n"
SRC_NEW = b"def produce():\n    return b'NEW-PAYLOAD'\n"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def produce(source: bytes) -> bytes:
    """Build step used by every oracle: the bytes literal ``produce()`` returns in ``source``.

    Derived by parsing, not by executing, the source.
    """
    tree = ast.parse(source.decode("utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, bytes)
        ):
            return node.value.value
    raise ValueError("source carries no bytes literal to build")


def test_source_change_forces_new_key() -> dict:
    d_old, d_new = _digest(SRC_OLD), _digest(SRC_NEW)
    key_old = R.content_addressed_key(PLUGIN_VERSION, d_old)
    key_new = R.content_addressed_key(PLUGIN_VERSION, d_new)
    expected_old, expected_new = produce(SRC_OLD), produce(SRC_NEW)
    with tempfile.TemporaryDirectory(prefix="imp0040-cache-") as raw:
        root = Path(raw)
        cache = R.ContentAddressedPluginCache(root, produce)
        served_old = cache.get_or_compute(PLUGIN_VERSION, SRC_OLD)
        again = cache.get_or_compute(PLUGIN_VERSION, SRC_OLD)
        keys_after_old = cache.keys()
        # The flip: one source change between the two calls.
        served_new = cache.get_or_compute(PLUGIN_VERSION, SRC_NEW)
        keys_after_new = cache.keys()
        assert cache.key(PLUGIN_VERSION, SRC_OLD) == key_old
        assert cache.key(PLUGIN_VERSION, SRC_NEW) == key_new
        assert (root / key_old / R.PAYLOAD_NAME).read_bytes() == expected_old
        assert (root / key_new / R.PAYLOAD_NAME).read_bytes() == expected_new
        assert cache.computed == 2 and cache.served_from_disk == 1
    assert served_old == again == expected_old
    assert served_new == expected_new, "served bytes are not produce(new_source)"
    assert served_new != served_old
    assert key_old != key_new
    assert keys_after_old == [key_old]
    assert keys_after_new == sorted([key_old, key_new])
    return {
        "served_new_equals_expected_new": served_new == expected_new,
        "served_new_differs_from_old": served_new != served_old,
        "on_disk_key_changed": keys_after_old != keys_after_new and key_old != key_new,
        "keys_after_old": keys_after_old,
        "keys_after_new": keys_after_new,
        "content_addressed_key_old": key_old,
        "content_addressed_key_new": key_new,
        "src_old_sha256": d_old,
        "src_new_sha256": d_new,
        "served_old": served_old.decode("utf-8", "replace")[:80],
        "served_new": served_new.decode("utf-8", "replace")[:80],
    }


class _Clock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_time_based_cache_fails_within_ttl() -> dict:
    """NEGATIVE CONTROL: the id+version+TTL design serves the stale artefact after a source flip."""
    expected_old, expected_new = produce(SRC_OLD), produce(SRC_NEW)
    clock = _Clock()
    with tempfile.TemporaryDirectory(prefix="imp0040-ttl-") as raw:
        root = Path(raw)
        cache = R.TimeBasedPluginCache(root, ttl_seconds=3600, clock=clock, produce=produce)
        served_old = cache.get_or_compute("demo", PLUGIN_VERSION, SRC_OLD)
        keys_after_old = cache.keys()
        clock.now += 60  # inside the window
        served_new = cache.get_or_compute("demo", PLUGIN_VERSION, SRC_NEW)
        keys_after_new = cache.keys()
        clock.now += 3600  # window expired: only now does the expiry heuristic notice
        served_after_ttl = cache.get_or_compute("demo", PLUGIN_VERSION, SRC_NEW)
    assert served_old == expected_old
    assert served_new == expected_old, "time-based cache unexpectedly saw the source change"
    assert served_new != expected_new
    assert keys_after_old == keys_after_new == [f"demo@{PLUGIN_VERSION}"]
    assert served_after_ttl == expected_new
    return {
        "served_new_equals_expected_old": served_new == expected_old,
        "served_new_equals_expected_new": served_new == expected_new,
        "served_after_ttl_equals_expected_new": served_after_ttl == expected_new,
        "keys_after_old": keys_after_old,
        "keys_after_new": keys_after_new,
        "ttl_seconds": 3600,
    }


def test_concurrent_read_write_does_not_corrupt() -> dict:
    """Writers re-derive two entries while readers hammer them: no torn payload is ever observed."""
    payload_a = (b"A" * 4096 + b"\n") * 64
    payload_b = (b"B" * 4096 + b"\n") * 64
    sources = {b"src-a": payload_a, b"src-b": payload_b}
    expected = set(sources.values())

    def build(source: bytes) -> bytes:
        return sources[source]

    errors: list[str] = []
    reads: list[int] = [0]
    lock = threading.Lock()
    with tempfile.TemporaryDirectory(prefix="imp0040-conc-") as raw:
        root = Path(raw)
        cache = R.ContentAddressedPluginCache(root, build)
        paths = {src: cache.payload_path(cache.key(PLUGIN_VERSION, src)) for src in sources}
        stop = threading.Event()

        def writer(src: bytes) -> None:
            for _ in range(40):
                path = paths[src]
                if path.is_file():
                    path.unlink()  # force a fresh derivation + atomic replace
                served = cache.get_or_compute(PLUGIN_VERSION, src)
                if served != sources[src]:
                    with lock:
                        errors.append(f"writer served wrong bytes for {src!r}")

        def reader() -> None:
            while not stop.is_set():
                for src, path in paths.items():
                    try:
                        data = path.read_bytes()
                    except FileNotFoundError:
                        continue  # between unlink and replace: absent is allowed, torn is not
                    with lock:
                        reads[0] += 1
                    if data not in expected or data != sources[src]:
                        with lock:
                            errors.append(f"torn/mixed read {len(data)} bytes for {src!r}")
                        return

        threads = [threading.Thread(target=writer, args=(s,)) for s in sources]
        readers = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads + readers:
            t.start()
        for t in threads:
            t.join()
        stop.set()
        for t in readers:
            t.join()
        final = {src: cache.get_or_compute(PLUGIN_VERSION, src) for src in sources}
        leftovers = sorted(p.name for p in root.rglob(".*.tmp"))
    assert not errors, errors[:3]
    assert final == sources
    assert reads[0] > 0, "readers never observed a payload"
    assert leftovers == [], leftovers
    return {"reads": reads[0], "errors": errors, "both_keys_intact": final == sources}


class ContentAddressingTests:
    """Method-addressable wrappers so a single oracle can be named on the command line."""

    def test_key_includes_version_and_source_hash(self) -> dict:
        d_old, d_new = _digest(SRC_OLD), _digest(SRC_NEW)
        same = R.content_addressed_key(PLUGIN_VERSION, d_old)
        assert same == R.content_addressed_key(PLUGIN_VERSION, d_old) == R.cache_key(PLUGIN_VERSION, d_old)
        assert same.split("/") == [PLUGIN_VERSION, d_old]
        assert R.content_addressed_key("1.2.4", d_old) != same, "version not part of the key"
        assert R.content_addressed_key(PLUGIN_VERSION, d_new) != same, "source hash not part of the key"
        assert R.source_digest_of(SRC_OLD) == d_old
        assert R.source_digest_of(SRC_OLD.replace(b"\n", b"\r\n")) == d_old, "CRLF twin must share identity"
        for bad in ("", "nothex", d_old[:-1]):
            try:
                R.content_addressed_key(PLUGIN_VERSION, bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted non-sha256 digest {bad!r}")
        return {"key": same, "version_changes_key": True, "source_changes_key": True}

    def test_source_change_forces_new_key(self) -> dict:
        return test_source_change_forces_new_key()

    def test_time_based_cache_fails_within_ttl(self) -> dict:
        return test_time_based_cache_fails_within_ttl()

    def test_concurrent_read_write_does_not_corrupt(self) -> dict:
        return test_concurrent_read_write_does_not_corrupt()


def main(argv: list[str]) -> int:
    suite = ContentAddressingTests()
    names = [
        "test_key_includes_version_and_source_hash",
        "test_source_change_forces_new_key",
        "test_time_based_cache_fails_within_ttl",
        "test_concurrent_read_write_does_not_corrupt",
    ]
    if argv:
        names = [a.split(".")[-1] for a in argv]
    failed = 0
    for name in names:
        try:
            result = getattr(suite, name)()
            print(f"PASS {name} {result if isinstance(result, dict) else ''}"[:400])
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{len(names) - failed}/{len(names)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
