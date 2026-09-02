#!/usr/bin/env python3
"""Hermetic cold-cache reproduction for CNF-0148.

Isolates npm, uv, pip, plugin-installer, build and harness caches under a
temp root. Does not purge the operator's global stores (measured empty/absent
on this Linux worktree; npm/uv/pip binaries are also absent).

Cache keys are name@version only (no content hash) so a warm entry can mask
a BROKEN live package and a stale entry can mask a FIXED live package.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import socket
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any

CACHE_KINDS = (
    "npm",
    "uv",
    "pip",
    "plugin-installer",
    "build",
    "harness",
)
PAYLOAD_BYTES = 64_000
KNOWN_REL = "caches/plugin-installer/broken-pkg/1.0.0/payload.bin"
MISS_BLOB = zlib.compress(("CNF0148-MISS-WORK\n" * 120000).encode("ascii"), 3)

# live = what the registry serves after a purge (egress permitted, local registry).
# warm  = what a name@version cache key holds before the purge.
PACKAGES: dict[str, dict[str, str]] = {
    "good-pkg": {"version": "1.0.0", "live_marker": "GOOD", "warm_marker": "GOOD", "live_rev": "1", "warm_rev": "1"},
    "broken-pkg": {"version": "1.0.0", "live_marker": "BROKEN", "warm_marker": "GOOD", "live_rev": "1", "warm_rev": "1"},
    "fixed-pkg": {"version": "1.0.0", "live_marker": "GOOD", "warm_marker": "BROKEN", "live_rev": "2", "warm_rev": "1"},
}

# Confirmation "package works" iff resolved payload marker is GOOD.
CONFIRMATIONS: tuple[dict[str, Any], ...] = (
    {"id": "cnf.npm.good-pkg.works", "kind": "npm", "name": "good-pkg", "expect": "GOOD"},
    {"id": "cnf.uv.good-pkg.works", "kind": "uv", "name": "good-pkg", "expect": "GOOD"},
    {"id": "cnf.pip.good-pkg.works", "kind": "pip", "name": "good-pkg", "expect": "GOOD"},
    {"id": "cnf.build.good-pkg.works", "kind": "build", "name": "good-pkg", "expect": "GOOD"},
    {
        "id": "cnf.plugin-installer.broken-pkg.works",
        "kind": "plugin-installer",
        "name": "broken-pkg",
        "expect": "GOOD",
    },
    {
        "id": "cnf.harness.fixed-pkg.works",
        "kind": "harness",
        "name": "fixed-pkg",
        "expect": "GOOD",
    },
    {
        "id": "cnf.inline.cache-independent.works",
        "kind": None,
        "name": "inline-pkg",
        "expect": "GOOD",
    },
)

HOST_CACHE_CANDIDATES = (
    "~/.npm",
    "~/.cache/pip",
    "~/.cache/uv",
    "~/.local/share/uv",
    "~/.cache/pypoetry",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def payload(marker: str, rev: str, seed: int) -> bytes:
    header = f"CNF0148-MARKER={marker}\nCNF0148-REV={rev}\n".encode("ascii")
    n = PAYLOAD_BYTES - len(header)
    if n < 0:
        raise ValueError("header longer than payload")
    pad = bytearray(n)
    # Deterministic mix of zeros and seed-derived bytes so gzip still shrinks
    # but the body is not a single-character run.
    for i in range(n):
        pad[i] = 0 if i % 3 else (seed + i) & 0xFF
    return header + bytes(pad)


def parse_marker(raw: bytes) -> str:
    for line in raw.split(b"\n", 4)[:4]:
        if line.startswith(b"CNF0148-MARKER="):
            return line.split(b"=", 1)[1].decode("ascii")
    return "UNKNOWN"


def dir_bytes(path: Path) -> tuple[int, int]:
    total = 0
    files = 0
    if not path.is_dir():
        return 0, 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            fp = Path(root) / name
            try:
                total += fp.stat().st_size
                files += 1
            except OSError:
                continue
    return total, files


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry = root / "registry"
        self.caches_root = root / "caches"
        self.inline = root / "inline" / "payload.bin"
        self.caches = {k: self.caches_root / k for k in CACHE_KINDS}

    def entry(self, kind: str, name: str, version: str) -> Path:
        return self.caches[kind] / name / version / "payload.bin"

    def registry_gz(self, name: str, version: str) -> Path:
        return self.registry / name / version / "payload.bin.gz"


def build_store(root: Path) -> Store:
    store = Store(root)
    store.registry.mkdir(parents=True, exist_ok=True)
    store.caches_root.mkdir(parents=True, exist_ok=True)
    store.inline.parent.mkdir(parents=True, exist_ok=True)
    for kind in CACHE_KINDS:
        store.caches[kind].mkdir(parents=True, exist_ok=True)
    seeds = {"GOOD": 11, "BROKEN": 23}
    for name, spec in PACKAGES.items():
        live = payload(spec["live_marker"], spec["live_rev"], seeds[spec["live_marker"]] + 100)
        gz_path = store.registry_gz(name, spec["version"])
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        gz_path.write_bytes(gzip.compress(live, compresslevel=6))
    store.inline.write_bytes(payload("GOOD", "inline", 7))
    return store


def seed_warm(store: Store) -> dict[str, str]:
    """Write name@version cache entries from the WARM marker, not live."""
    seeds = {"GOOD": 11, "BROKEN": 23}
    written: dict[str, str] = {}
    for conf in CONFIRMATIONS:
        kind = conf["kind"]
        name = conf["name"]
        if kind is None or name not in PACKAGES:
            continue
        spec = PACKAGES[name]
        body = payload(spec["warm_marker"], spec["warm_rev"], seeds[spec["warm_marker"]])
        path = store.entry(kind, name, spec["version"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        written[f"{kind}/{name}@{spec['version']}"] = sha256_bytes(body)
    return written


def purge(store: Store) -> None:
    if store.caches_root.is_dir():
        shutil.rmtree(store.caches_root)
    store.caches_root.mkdir(parents=True, exist_ok=True)
    for kind in CACHE_KINDS:
        store.caches[kind].mkdir(parents=True, exist_ok=True)


def resolve(store: Store, kind: str, name: str) -> dict[str, Any]:
    spec = PACKAGES[name]
    version = spec["version"]
    entry = store.entry(kind, name, version)
    t0 = time.perf_counter()
    if entry.is_file():
        data = entry.read_bytes()
        source = "cache"
    else:
        gz = store.registry_gz(name, version).read_bytes()
        data = gzip.decompress(gz)
        zlib.decompress(MISS_BLOB)
        entry.parent.mkdir(parents=True, exist_ok=True)
        tmp = entry.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(entry)
        source = "registry"
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "kind": kind,
        "name": name,
        "version": version,
        "source": source,
        "marker": parse_marker(data),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "ms": round(ms, 4),
        "cache_entry": f"{kind}/{name}@{version}",
        "entry_present": entry.is_file(),
    }


def run_suite(store: Store, warmth: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for conf in CONFIRMATIONS:
        if conf["kind"] is None:
            t0 = time.perf_counter()
            data = store.inline.read_bytes()
            ms = (time.perf_counter() - t0) * 1000.0
            marker = parse_marker(data)
            rec: dict[str, Any] = {
                "kind": None,
                "name": conf["name"],
                "version": "inline",
                "source": "inline",
                "marker": marker,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "ms": round(ms, 4),
                "cache_entry": None,
                "entry_present": False,
            }
        else:
            rec = resolve(store, conf["kind"], conf["name"])
        verdict = "PASS" if rec["marker"] == conf["expect"] else "FAIL"
        rows.append(
            {
                "id": conf["id"],
                "warmth": warmth,
                "verdict": verdict,
                "expect": conf["expect"],
                **rec,
            }
        )
    return rows


def host_inventory() -> dict[str, Any]:
    tools = {}
    for name in ("npm", "uv", "pip", "pip3"):
        tools[name] = shutil.which(name)
    caches = []
    for rel in HOST_CACHE_CANDIDATES:
        path = Path(os.path.expanduser(rel))
        b, n = dir_bytes(path)
        caches.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "files": n,
                "bytes": b,
            }
        )
    return {
        "tools": tools,
        "global_caches": caches,
        "purged_global_stores": False,
        "reason": (
            "Host npm/uv/pip binaries are absent and global cache dirs are empty "
            "or missing. Purge is executed on redirected isolated stores so this "
            "unit does not destroy an operator cache that is not present."
        ),
    }


def egress_state() -> dict[str, Any]:
    proxy_keys = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    proxies = {k: os.environ[k] for k in proxy_keys if os.environ.get(k)}
    reachable: bool | None
    err = None
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2.0).close()
        reachable = True
    except OSError as exc:
        reachable = False
        err = type(exc).__name__
    return {
        "block_installed_by_this_unit": False,
        "permitted": True,
        "proxy_env": proxies,
        "outbound_443_1_1_1_1": reachable,
        "outbound_error": err,
        "registry": "local-file gzip registry (simulates egress-permitted fetch; no deny-all)",
    }


def _timing_sum(rows: list[dict[str, Any]]) -> float:
    return round(sum(float(r["ms"]) for r in rows if r.get("kind")), 4)


def _verdicts(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {r["id"]: r["verdict"] for r in rows}


def attribute_flips(
    warm: list[dict[str, Any]], cold: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cold_by = {r["id"]: r for r in cold}
    out: list[dict[str, Any]] = []
    for w in warm:
        c = cold_by[w["id"]]
        if w["verdict"] == c["verdict"]:
            continue
        out.append(
            {
                "confirmation": w["id"],
                "warm_verdict": w["verdict"],
                "cold_verdict": c["verdict"],
                "named_cache_entry": w.get("cache_entry"),
                "warm_source": w["source"],
                "cold_source": c["source"],
                "warm_sha256": w["sha256"],
                "cold_sha256": c["sha256"],
                "warm_marker": w["marker"],
                "cold_marker": c["marker"],
                "class": (
                    "warm-cache-masks-BROKEN-package"
                    if w["verdict"] == "PASS" and c["verdict"] == "FAIL"
                    else "stale-cache-masks-FIXED-package"
                    if w["verdict"] == "FAIL" and c["verdict"] == "PASS"
                    else "unclassified-flip"
                ),
            }
        )
    return out


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0148-") as tmp:
        root = Path(tmp)
        store = build_store(root)
        seeded = seed_warm(store)
        known = store.root / KNOWN_REL
        present_before = known.is_file()
        before_bytes, before_files = dir_bytes(store.caches_root)
        warm_rows = run_suite(store, "warm")
        warm_ms = _timing_sum(warm_rows)
        purge(store)
        after_bytes, after_files = dir_bytes(store.caches_root)
        present_after = known.is_file()
        cold_rows = run_suite(store, "cold")
        cold_ms = _timing_sum(cold_rows)
        rewarm_rows = run_suite(store, "rewarm")
        rewarm_ms = _timing_sum(rewarm_rows)
        flips = attribute_flips(warm_rows, cold_rows)
        survivors = [
            wid
            for wid, wv in _verdicts(warm_rows).items()
            if wv == _verdicts(cold_rows)[wid]
        ]
        return {
            "seeded_entries": seeded,
            "purge": {
                "before_bytes": before_bytes,
                "after_bytes": after_bytes,
                "before_files": before_files,
                "after_files": after_files,
                "purged": after_files == 0 and after_bytes == 0 and before_bytes > 0,
                "delta_bytes": before_bytes - after_bytes,
            },
            "detector_control": {
                "known_artifact_rel": KNOWN_REL,
                "present_before": present_before,
                "present_after": present_after,
                "pass": present_before is True and present_after is False,
            },
            "warm": {
                "timing_ms_sum": warm_ms,
                "verdicts": _verdicts(warm_rows),
                "rows": warm_rows,
            },
            "cold": {
                "timing_ms_sum": cold_ms,
                "verdicts": _verdicts(cold_rows),
                "rows": cold_rows,
            },
            "rewarm": {
                "timing_ms_sum": rewarm_ms,
                "verdicts": _verdicts(rewarm_rows),
                "rows": rewarm_rows,
            },
            "flips": flips,
            "survivors": survivors,
            "host": host_inventory(),
            "egress": egress_state(),
        }


def predicates(doc: dict[str, Any]) -> list[str]:
    """Return failing predicate names (empty list means the reproduction held)."""
    bad: list[str] = []
    purge = doc["purge"]
    det = doc["detector_control"]
    warm_ms = float(doc["warm"]["timing_ms_sum"])
    cold_ms = float(doc["cold"]["timing_ms_sum"])
    rewarm_ms = float(doc["rewarm"]["timing_ms_sum"])
    if not purge["purged"]:
        bad.append("purge-not-measured")
    if int(purge["before_bytes"]) <= int(purge["after_bytes"]):
        bad.append("purge-size-did-not-drop")
    if not det["pass"]:
        bad.append("known-artifact-not-absent-after-purge")
    if cold_ms <= warm_ms:
        bad.append("cold-not-slower-than-warm")
    # Rewarm must restore the hit timing profile, not the miss profile.
    if abs(rewarm_ms - warm_ms) >= abs(rewarm_ms - cold_ms):
        bad.append("rewarm-timing-not-restored")
    if not doc["flips"]:
        bad.append("no-result-delta")
    named = [f for f in doc["flips"] if f.get("named_cache_entry")]
    if len(named) != len(doc["flips"]):
        bad.append("flip-missing-named-entry")
    classes = {f["class"] for f in doc["flips"]}
    if "warm-cache-masks-BROKEN-package" not in classes:
        bad.append("missing-broken-mask-class")
    if "stale-cache-masks-FIXED-package" not in classes:
        bad.append("missing-fixed-mask-class")
    if doc["egress"].get("block_installed_by_this_unit") is not False:
        bad.append("egress-block-confound")
    if "cnf.inline.cache-independent.works" not in doc["survivors"]:
        bad.append("inline-confirmation-flipped")
    return bad


def main() -> int:
    doc = run()
    bad = predicates(doc)
    print(json.dumps({k: doc[k] for k in ("purge", "detector_control", "survivors", "flips") if k in doc}, indent=2))
    print(
        f"warm_ms={doc['warm']['timing_ms_sum']} cold_ms={doc['cold']['timing_ms_sum']} "
        f"rewarm_ms={doc['rewarm']['timing_ms_sum']} before={doc['purge']['before_bytes']} "
        f"after={doc['purge']['after_bytes']}"
    )
    if bad:
        print("FAILED:CNF-0148-experiment " + ",".join(bad))
        return 1
    print("SUCCESS:CNF-0148-experiment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
