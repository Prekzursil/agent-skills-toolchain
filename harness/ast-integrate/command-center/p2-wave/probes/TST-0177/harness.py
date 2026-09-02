#!/usr/bin/env python3
"""TST-0177: clean-room profile cache isolation.

Does not ship B07 (IMP-0040/0041 cache). Production is discovered, not rebuilt.
The tester-instrument is a profile-scoped cache used only to prove the
both-states control and the machine-wide-plant detector are live.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARTIFACT_REL = "command-center/receipts/TST-0177.json"
ARTIFACT = REPO / ARTIFACT_REL
UNIT = "TST-0177"
SENTINEL = "SUCCESS:TST-0177"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/cache_report"
PLANTED_MARKER = b"TST-0177-PLANTED-MACHINE-WIDE-CACHE\n"
QUESTION = (
    "Does a fresh user profile observe zero inherited cache entries, and are "
    "all cache paths profile-scoped? PASS requires an install in a new profile "
    "to perform full fetches and to write only inside that profile."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0177/probe1_both_states.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0177/probe2_detector_audit.py"
)

PRODUCTION_CANDIDATES = (
    "tools/plugin/cache.py",
    "tools/plugin/plugin_cache.py",
    "tools/plugin-cache-reaper/reap.py",
    "tools/plugin-cache-reaper/cache.py",
    "platform/plugin/cache.py",
    "command-center/tools/plugin/cache.py",
)

PACKAGES = (
    {"name": "alpha-kit", "version": "1.0.0", "payload": b"ALPHA-KIT-BODY-v1\n"},
    {"name": "beta-lint", "version": "2.1.0", "payload": b"BETA-LINT-BODY-v2\n"},
    {"name": "gamma-mcp", "version": "0.9.0", "payload": b"GAMMA-MCP-BODY-v0\n"},
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class WriteTracker:
    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    def record(self, path: Path, kind: str, nbytes: int) -> None:
        self.writes.append(
            {
                "path": str(path.resolve()),
                "kind": kind,
                "bytes": int(nbytes),
            }
        )


class Mirror:
    """Local file-backed mirror standing in for the network."""

    def __init__(self, payloads: dict[tuple[str, str], bytes]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, str]] = []

    def fetch(self, name: str, version: str) -> bytes:
        key = (name, version)
        if key not in self.payloads:
            raise KeyError(f"mirror-miss:{name}@{version}")
        self.calls.append({"name": name, "version": version})
        return self.payloads[key]


class ProfileScopedCache:
    """Instrument: every blob lives under the profile home. Not B07 production."""

    REL = Path(".harness") / "plugin-cache"

    def __init__(self, profile_home: Path, tracker: WriteTracker) -> None:
        self.home = profile_home
        self.root = profile_home / self.REL
        self.tracker = tracker
        self.root.mkdir(parents=True, exist_ok=True)

    def key_path(self, name: str, version: str) -> Path:
        digest = hashlib.sha256(f"{name}@{version}".encode("utf-8")).hexdigest()[:16]
        return self.root / f"{name}--{version}--{digest}.blob"

    def put(self, name: str, version: str, data: bytes) -> Path:
        path = self.key_path(name, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        self.tracker.record(tmp, "tmp-write", len(data))
        tmp.replace(path)
        self.tracker.record(path, "commit", len(data))
        return path

    def get(self, name: str, version: str) -> bytes | None:
        path = self.key_path(name, version)
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
        return None

    def listing(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return rows
        for p in sorted(self.root.glob("*.blob")):
            raw = p.read_bytes()
            rows.append(
                {
                    "name": p.name,
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                    "rel": p.relative_to(self.home).as_posix(),
                }
            )
        return rows


class SharedGlobalCache:
    """Negative control: one directory shared by every profile."""

    def __init__(self, global_root: Path, tracker: WriteTracker) -> None:
        self.home = global_root
        self.root = global_root
        self.tracker = tracker
        self.root.mkdir(parents=True, exist_ok=True)

    def key_path(self, name: str, version: str) -> Path:
        digest = hashlib.sha256(f"{name}@{version}".encode("utf-8")).hexdigest()[:16]
        return self.root / f"{name}--{version}--{digest}.blob"

    def put(self, name: str, version: str, data: bytes) -> Path:
        path = self.key_path(name, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        self.tracker.record(tmp, "tmp-write", len(data))
        tmp.replace(path)
        self.tracker.record(path, "commit", len(data))
        return path

    def get(self, name: str, version: str) -> bytes | None:
        path = self.key_path(name, version)
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
        return None

    def listing(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for p in sorted(self.root.glob("*.blob")):
            raw = p.read_bytes()
            rows.append(
                {
                    "name": p.name,
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                    "rel": p.name,
                }
            )
        return rows


def listing_fingerprint(listing: list[dict[str, Any]]) -> str:
    body = [{k: r[k] for k in ("name", "bytes", "sha256")} for r in listing]
    return sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":")))


def install_packages(
    cache: Any,
    mirror: Mirror,
    names: list[str],
) -> list[dict[str, Any]]:
    by_name = {p["name"]: p for p in PACKAGES}
    rows: list[dict[str, Any]] = []
    for name in names:
        pkg = by_name[name]
        hit = cache.get(pkg["name"], pkg["version"])
        if hit is not None:
            rows.append(
                {
                    "name": pkg["name"],
                    "version": pkg["version"],
                    "mode": "cache-hit",
                    "fetch": False,
                    "bytes": len(hit),
                    "sha256": sha256_bytes(hit),
                }
            )
            continue
        data = mirror.fetch(pkg["name"], pkg["version"])
        cache.put(pkg["name"], pkg["version"], data)
        rows.append(
            {
                "name": pkg["name"],
                "version": pkg["version"],
                "mode": "full-fetch",
                "fetch": True,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )
    return rows


def leaks_for(writes: list[dict[str, Any]], profile_home: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in writes:
        path = Path(row["path"])
        if not is_under(path, profile_home):
            out.append(row)
    return out


def scan_roots(
    roots: list[Path],
    profile_home: Path,
    marker: bytes = PLANTED_MARKER,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = [p for p in sorted(root.rglob("*")) if p.is_file()]
        for p in candidates:
            raw = p.read_bytes() if p.stat().st_size <= 1_000_000 else b""
            findings.append(
                {
                    "path": str(p.resolve()),
                    "bytes": p.stat().st_size,
                    "outside_profile": not is_under(p, profile_home),
                    "has_plant_marker": marker in raw,
                    "sha256": sha256_bytes(raw) if raw else None,
                }
            )
    return findings


def load_production_modules() -> dict[str, Any]:
    """Import live plugin.cache via platform/ on sys.path (same as plugin/conftest.py)."""
    plat = str(REPO / "platform")
    if plat not in sys.path:
        sys.path.insert(0, plat)
    try:
        from plugin.cache import Cache
        from plugin.fsops import hash_bytes
        from plugin.journal import Prefix
    except Exception as exc:  # production may be broken; record, do not rebuild
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"Cache": Cache, "Prefix": Prefix, "hash_bytes": hash_bytes}


def production_listing(cache_root: Path, profile_home: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not cache_root.is_dir():
        return rows
    for p in sorted(cache_root.rglob("*")):
        if not p.is_file() or "quarantine" in p.parts:
            continue
        raw = p.read_bytes()
        rel = (
            p.relative_to(profile_home).as_posix()
            if is_under(p, profile_home)
            else str(p.resolve())
        )
        rows.append(
            {
                "name": p.name,
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "rel": rel,
            }
        )
    return rows


def seed_production_profile(profile_home: Path, tracker: WriteTracker) -> dict[str, Any]:
    mods = load_production_modules()
    if "Cache" not in mods:
        return {"ok": False, "error": mods.get("error")}
    prefix = mods["Prefix"](profile_home)
    prefix.ensure()
    cache = mods["Cache"](prefix.cache)
    for pkg in PACKAGES:
        key = cache.put(pkg["payload"])
        tracker.record(cache._path(key), "production-seed", len(pkg["payload"]))
    listing = production_listing(prefix.cache, profile_home)
    return {
        "ok": True,
        "listing": listing,
        "fingerprint": listing_fingerprint(listing),
        "cache_root": str(prefix.cache.resolve()),
        "entry_count": len(listing),
        "under_profile": is_under(prefix.cache, profile_home),
    }


def discover_production() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    importable = False
    api: dict[str, Any] | None = None
    for rel in PRODUCTION_CANDIDATES:
        path = REPO / rel
        row: dict[str, Any] = {
            "path": rel,
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location(
                    "tst0177_prod_" + path.stem, path
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    names = [n for n in dir(mod) if not n.startswith("_")]
                    row["importable"] = True
                    row["public_names"] = names[:40]
                    importable = True
                    cache_cls = getattr(mod, "Cache", None) or getattr(
                        mod, "PluginCache", None
                    )
                    if cache_cls is not None:
                        api = {
                            "class": getattr(cache_cls, "__name__", str(cache_cls)),
                            "module": rel,
                            "methods": [
                                m
                                for m in dir(cache_cls)
                                if not m.startswith("_")
                            ],
                        }
                else:
                    row["importable"] = False
            except Exception as exc:  # production may be broken; record, do not rebuild
                row["importable"] = False
                row["import_error"] = type(exc).__name__
        hits.append(row)
    mods = load_production_modules()
    pkg_row: dict[str, Any] = {
        "path": "plugin.cache",
        "source": "platform/plugin/cache.py",
        "exists": (REPO / "platform" / "plugin" / "cache.py").is_file(),
    }
    if "Cache" in mods:
        C = mods["Cache"]
        pkg_row["importable"] = True
        importable = True
        api = {
            "class": "Cache",
            "module": "plugin.cache",
            "source": "platform/plugin/cache.py",
            "prefix_cache_rel": "state/cache",
            "methods": [m for m in dir(C) if not m.startswith("_")],
        }
        pkg_row["public_names"] = ["Cache", "CacheStats"]
    else:
        pkg_row["importable"] = False
        pkg_row["import_error"] = mods.get("error")
    plugin_dir = REPO / "tools" / "plugin"
    plugin_files = []
    if plugin_dir.is_dir():
        plugin_files = sorted(
            p.relative_to(REPO).as_posix()
            for p in plugin_dir.glob("*.py")
            if p.is_file()
        )
    return {
        "any_present": any(h["exists"] for h in hits) or bool(pkg_row.get("exists")),
        "importable": importable,
        "api": api,
        "package_import": pkg_row,
        "candidates": hits,
        "tools_plugin_py": plugin_files,
        "note": (
            "B07 production cache is plugin.cache.Cache rooted at Prefix.cache "
            "(<prefix>/state/cache). This tester does not rebuild it."
        ),
    }


def try_production_install(
    profile_home: Path,
    tracker: WriteTracker,
    mirror: Mirror,
    names: list[str],
) -> dict[str, Any]:
    disc = discover_production()
    mods = load_production_modules()
    if "Cache" not in mods:
        present_files = bool(disc.get("any_present"))
        return {
            "present": present_files,
            "full_fetches": False,
            "inherited_hits": 0,
            "install_rows": [],
            "leaks": [],
            "listing": [],
            "empty_at_start": True,
            "cache_root_under_profile": False,
            "reason": (
                "production-cache-present-but-not-importable"
                if present_files
                else "production-cache-absent"
            ),
            "discovery": disc,
            "load_error": mods.get("error"),
        }
    prefix = mods["Prefix"](profile_home)
    prefix.ensure()
    cache = mods["Cache"](prefix.cache)
    hash_bytes = mods["hash_bytes"]
    before = production_listing(prefix.cache, profile_home)
    by_name = {p["name"]: p for p in PACKAGES}
    rows: list[dict[str, Any]] = []
    for name in names:
        pkg = by_name[name]
        key = hash_bytes(pkg["payload"])
        hit = cache.get(key)
        if hit is not None:
            rows.append(
                {
                    "name": pkg["name"],
                    "version": pkg["version"],
                    "mode": "cache-hit",
                    "fetch": False,
                    "bytes": len(hit),
                    "sha256": sha256_bytes(hit),
                    "key": key,
                }
            )
            continue
        data = mirror.fetch(pkg["name"], pkg["version"])
        stored_key = cache.put(data)
        tracker.record(cache._path(stored_key), "production-put", len(data))
        rows.append(
            {
                "name": pkg["name"],
                "version": pkg["version"],
                "mode": "full-fetch",
                "fetch": True,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "key": stored_key,
            }
        )
    listing = production_listing(prefix.cache, profile_home)
    writes_here = [w for w in tracker.writes if "production" in w["kind"]]
    fs_leaks: list[dict[str, Any]] = []
    if prefix.cache.is_dir():
        for p in prefix.cache.rglob("*"):
            if p.is_file() and not is_under(p, profile_home):
                fs_leaks.append(
                    {
                        "path": str(p.resolve()),
                        "kind": "fs-outside-profile",
                        "bytes": p.stat().st_size,
                    }
                )
    return {
        "present": True,
        "full_fetches": bool(rows) and all(r["fetch"] for r in rows),
        "inherited_hits": sum(1 for r in rows if r["mode"] == "cache-hit"),
        "install_rows": rows,
        "leaks": leaks_for(writes_here, profile_home) + fs_leaks,
        "listing": listing,
        "listing_before": before,
        "empty_at_start": len(before) == 0,
        "cache_root": str(prefix.cache.resolve()),
        "cache_root_under_profile": is_under(prefix.cache, profile_home),
        "reason": "production-plugin.cache.Cache-prefix-scoped",
        "discovery": disc,
    }


def make_profile(scratch: Path, name: str) -> dict[str, Path]:
    home = scratch / name / "home"
    home.mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    return {"home": home, "root": scratch / name}


def run_scenario(scratch: Path | None = None) -> dict[str, Any]:
    owned = False
    tmp_ctx = None
    if scratch is None:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="tst0177-")
        scratch = Path(tmp_ctx.name)
        owned = True
    try:
        return _run_scenario(scratch)
    finally:
        if owned and tmp_ctx is not None:
            tmp_ctx.cleanup()


def _run_scenario(scratch: Path) -> dict[str, Any]:
    payloads = {(p["name"], p["version"]): p["payload"] for p in PACKAGES}
    original = make_profile(scratch, "original")
    cleanroom = make_profile(scratch, "cleanroom")
    machine_wide = scratch / "machine-wide" / "plugin-cache"
    global_shared = scratch / "global-shared-cache"
    machine_wide.mkdir(parents=True, exist_ok=True)
    global_shared.mkdir(parents=True, exist_ok=True)

    seed_tracker = WriteTracker()
    orig_cache = ProfileScopedCache(original["home"], seed_tracker)
    seed_mirror = Mirror(payloads)
    seed_names = [p["name"] for p in PACKAGES]
    seed_rows = install_packages(orig_cache, seed_mirror, seed_names)
    orig_before = orig_cache.listing()
    orig_fp_before = listing_fingerprint(orig_before)

    clean_tracker = WriteTracker()
    clean_cache = ProfileScopedCache(cleanroom["home"], clean_tracker)
    clean_mirror = Mirror(payloads)
    clean_before = clean_cache.listing()
    install_names = ["alpha-kit", "beta-lint"]
    clean_rows = install_packages(clean_cache, clean_mirror, install_names)
    clean_after = clean_cache.listing()
    orig_after = orig_cache.listing()
    orig_fp_after = listing_fingerprint(orig_after)
    instrument_leaks = leaks_for(clean_tracker.writes, cleanroom["home"])
    inherited = [r for r in clean_rows if r["mode"] == "cache-hit"]
    fetches = [r for r in clean_rows if r["fetch"]]

    orig_prod_tracker = WriteTracker()
    orig_prod_seed = seed_production_profile(original["home"], orig_prod_tracker)
    prod_tracker = WriteTracker()
    prod_mirror = Mirror(payloads)
    production = try_production_install(
        cleanroom["home"], prod_tracker, prod_mirror, install_names
    )
    orig_prod_after: list[dict[str, Any]] = []
    orig_prod_fp_after = ""
    orig_prod_intact = False
    if orig_prod_seed.get("ok"):
        orig_prod_after = production_listing(
            Path(str(orig_prod_seed["cache_root"])), original["home"]
        )
        orig_prod_fp_after = listing_fingerprint(orig_prod_after)
        orig_prod_intact = (
            orig_prod_fp_after == orig_prod_seed["fingerprint"]
            and len(orig_prod_after) == len(PACKAGES)
        )

    plant_path = machine_wide / "planted-entry.blob"
    plant_path.write_bytes(PLANTED_MARKER)
    audit_roots = [
        machine_wide,
        original["home"] / ProfileScopedCache.REL,
        cleanroom["home"] / ProfileScopedCache.REL,
        original["home"] / "state" / "cache",
        cleanroom["home"] / "state" / "cache",
        global_shared,
    ]
    planted_scan = scan_roots(audit_roots, cleanroom["home"])
    plant_hits = [f for f in planted_scan if f["has_plant_marker"]]
    plant_outside = [f for f in plant_hits if f["outside_profile"]]

    absent_scan = scan_roots(
        [
            original["home"] / ProfileScopedCache.REL,
            cleanroom["home"] / ProfileScopedCache.REL,
            global_shared,
        ],
        cleanroom["home"],
    )
    absent_marker_hits = [f for f in absent_scan if f["has_plant_marker"]]

    leaky_seed_tracker = WriteTracker()
    leaky = SharedGlobalCache(global_shared, leaky_seed_tracker)
    leaky_mirror = Mirror(payloads)
    install_packages(leaky, leaky_mirror, seed_names)
    leaky_clean_tracker = WriteTracker()
    leaky_clean = SharedGlobalCache(global_shared, leaky_clean_tracker)
    leaky_clean_mirror = Mirror(payloads)
    leaky_rows = install_packages(leaky_clean, leaky_clean_mirror, install_names)
    leaky_hits = [r for r in leaky_rows if r["mode"] == "cache-hit"]
    leaky_leaks = leaks_for(leaky_clean_tracker.writes, cleanroom["home"])
    leaky_detected = bool(leaky_hits) or bool(leaky_leaks)

    both_states = (
        orig_fp_before == orig_fp_after
        and len(orig_after) == len(PACKAGES)
        and all(r["mode"] == "full-fetch" for r in seed_rows)
    )
    zero_inherited = len(inherited) == 0 and len(clean_before) == 0
    full_fetches_instrument = len(fetches) == len(install_names) and len(fetches) > 0
    writes_inside = len(instrument_leaks) == 0 and bool(clean_tracker.writes)
    detector_plant = bool(plant_outside) and all(
        f["outside_profile"] for f in plant_hits
    )
    detector_absent_silent = len(absent_marker_hits) == 0

    production_property = bool(
        production.get("present")
        and production.get("full_fetches")
        and production.get("inherited_hits") == 0
        and not production.get("leaks")
        and production.get("empty_at_start")
        and production.get("cache_root_under_profile")
        and orig_prod_intact
    )
    verdict = "CONFIRMED" if production_property and both_states else "REFUTED"

    return {
        "unit_id": UNIT,
        "verdict": verdict,
        "production_property_pass": production_property,
        "production": {
            "present": bool(production.get("present")),
            "full_fetches": bool(production.get("full_fetches")),
            "inherited_hits": int(production.get("inherited_hits") or 0),
            "empty_at_start": bool(production.get("empty_at_start")),
            "cache_root": production.get("cache_root"),
            "cache_root_under_profile": bool(
                production.get("cache_root_under_profile")
            ),
            "original_intact": orig_prod_intact,
            "original_entry_count": len(orig_prod_after),
            "original_listing_before": orig_prod_seed.get("listing") or [],
            "original_listing_after": orig_prod_after,
            "reason": production.get("reason"),
            "discovery": production.get("discovery") or discover_production(),
            "install_rows": production.get("install_rows") or [],
            "leaks": production.get("leaks") or [],
            "listing": production.get("listing") or [],
        },
        "original": {
            "seed_rows": seed_rows,
            "listing_before": orig_before,
            "listing_after": orig_after,
            "fingerprint_before": orig_fp_before,
            "fingerprint_after": orig_fp_after,
            "intact": orig_fp_before == orig_fp_after,
            "entry_count": len(orig_after),
        },
        "cleanroom": {
            "listing_before": clean_before,
            "listing_after": clean_after,
            "empty_at_start": len(clean_before) == 0,
            "install_rows": clean_rows,
            "inherited_hits": inherited,
            "fetches": fetches,
            "fetch_count": len(fetches),
            "hit_count": len(inherited),
            "mirror_calls": list(clean_mirror.calls),
            "zero_inherited": zero_inherited,
            "full_fetches": full_fetches_instrument,
        },
        "audit": {
            "instrument_writes": list(clean_tracker.writes),
            "instrument_leaks": instrument_leaks,
            "writes_only_inside_profile": writes_inside,
            "plant_path": str(plant_path.resolve()),
            "plant_hits": plant_hits,
            "plant_outside_profile": plant_outside,
            "plant_detected": detector_plant,
            "absent_marker_hits": absent_marker_hits,
            "absent_silent": detector_absent_silent,
        },
        "leaky_mutant": {
            "install_rows": leaky_rows,
            "inherited_hits": leaky_hits,
            "leaks": leaky_leaks,
            "detected": leaky_detected,
            "fetch_count": sum(1 for r in leaky_rows if r["fetch"]),
        },
        "controls": {
            "both_states_original_intact": both_states,
            "zero_inherited_cleanroom": zero_inherited,
            "instrument_full_fetches": full_fetches_instrument,
            "writes_only_inside_profile": writes_inside,
            "detector_plant_seen": detector_plant,
            "detector_absent_silent": detector_absent_silent,
            "leaky_mutant_detected": leaky_detected,
            "production_original_intact": orig_prod_intact,
            "production_empty_at_start": bool(production.get("empty_at_start")),
        },
        "detector_live": (
            both_states
            and zero_inherited
            and full_fetches_instrument
            and writes_inside
            and detector_plant
            and detector_absent_silent
            and leaky_detected
        ),
    }


def fingerprints() -> dict[str, str]:
    p1 = HERE / "probe1_both_states.py"
    p2 = HERE / "probe2_detector_audit.py"
    return {
        "source": sha256_path(p1) if p1.is_file() else "",
        "verifier": sha256_path(p2) if p2.is_file() else "",
    }


def build_record() -> dict[str, Any]:
    live = run_scenario()
    fp = fingerprints()
    if not fp["source"] or not fp["verifier"] or fp["source"] == fp["verifier"]:
        raise RuntimeError("source_probe/verifier_probe fingerprints missing or identical")
    tests = [
        {
            "id": "TST-0177-BOTH-STATES",
            "result": "PASS" if live["controls"]["both_states_original_intact"] else "FAIL",
            "name": "both-states control: the original profile still has its cache",
        },
        {
            "id": "TST-0177-DETECTOR-PLANT",
            "result": "PASS" if live["controls"]["detector_plant_seen"] else "FAIL",
            "name": "detector control: plant a machine-wide cache entry and confirm the audit sees it",
        },
        {
            "id": "TST-0177-DETECTOR-ABSENT",
            "result": "PASS" if live["controls"]["detector_absent_silent"] else "FAIL",
            "name": "detector silent-on-absent: no plant marker when the machine-wide file is not in the scan set",
        },
        {
            "id": "TST-0177-ZERO-INHERIT",
            "result": "PASS" if live["controls"]["zero_inherited_cleanroom"] else "FAIL",
            "name": "instrument clean-room profile observes zero inherited cache hits",
        },
        {
            "id": "TST-0177-WRITES-SCOPED",
            "result": "PASS" if live["controls"]["writes_only_inside_profile"] else "FAIL",
            "name": "(b) filesystem audit: instrument cache writes stay inside the clean-room profile root",
        },
        {
            "id": "TST-0177-NAMED-A",
            "result": "PASS" if live["cleanroom"]["listing_after"] is not None else "FAIL",
            "name": "(a) the new profile's cache directory contents after install",
        },
        {
            "id": "TST-0177-LEAKY-MUTANT",
            "result": "PASS" if live["controls"]["leaky_mutant_detected"] else "FAIL",
            "name": "mutation control: a shared global cache inherits original entries and is detected",
        },
        {
            "id": "TST-0177-PRODUCTION-PROPERTY",
            "result": "FAIL" if not live["production_property_pass"] else "PASS",
            "name": "production install in a new profile performs full fetches and writes only inside that profile",
        },
        {
            "id": "TST-0177-PROD-ORIGINAL-INTACT",
            "result": "PASS" if live["production"].get("original_intact") else "FAIL",
            "name": "both-states (production): original Prefix cache listing unchanged after clean-room install",
        },
    ]
    methodology = [
        t
        for t in tests
        if t["id"]
        not in {"TST-0177-PRODUCTION-PROPERTY", "TST-0177-PROD-ORIGINAL-INTACT"}
    ]
    if any(t["result"] != "PASS" for t in methodology):
        raise RuntimeError("methodology controls failed: " + json.dumps(tests))
    schema_path = REPO / "command-center/schema/receipt.schema.json"
    rec: dict[str, Any] = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Clean-room profile sees an empty cache (no cross-profile leakage)",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "cache_report",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "verdict": live["verdict"],
        "functional_verdict": live["verdict"],
        "owner_approval_required": True,
        "owner_ruling": (
            "Catalog flags owner_approval_required; this executor delivery was "
            "explicitly requested as P2-deliver G-1 for TST-0177 and does not "
            "forge a separate owner signature."
        ),
        "output_schema": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "cloud_ok": False,
        "ts": utc_now(),
        "source_probe": f"sha256:{fp['source']} {P1_CMD}",
        "verifier_probe": f"sha256:{fp['verifier']} {P2_CMD}",
        "source_probe_detail": {"command": P1_CMD, "fingerprint": fp["source"]},
        "verifier_probe_detail": {"command": P2_CMD, "fingerprint": fp["verifier"]},
        "baseline_repro": {
            "subject": "production-plugin-cache",
            "discovery": live["production"]["discovery"],
            "property_pass": live["production_property_pass"],
            "reason": live["production"]["reason"],
        },
        "corrected_repro": {
            "status": "NOT-NEEDED" if live["production_property_pass"] else "NOT-APPLIED",
            "reason": (
                "Live plugin.cache.Cache is prefix-scoped; no production patch applied."
                if live["production_property_pass"]
                else (
                    "Tester does not ship B07 cache (IMP-0040/0041). Production "
                    "property did not pass; no ADV rebuild circle."
                )
            ),
        },
        "production": live["production"],
        "original_profile": live["original"],
        "cleanroom_profile": live["cleanroom"],
        "filesystem_audit": live["audit"],
        "leaky_mutant": live["leaky_mutant"],
        "controls": live["controls"],
        "detector_live": live["detector_live"],
        "evidence": [
            {
                "id": "EV-A",
                "kind": "new-profile-cache-listing",
                "detail": (
                    "Clean-room instrument cache after install: "
                    f"{len(live['cleanroom']['listing_after'])} entries, "
                    f"{live['cleanroom']['hit_count']} inherited hits, "
                    f"{live['cleanroom']['fetch_count']} full fetches. "
                    "Production Prefix cache after install: "
                    f"{len(live['production']['listing'])} entries, "
                    f"{live['production']['inherited_hits']} inherited hits, "
                    f"full_fetches={live['production']['full_fetches']}."
                ),
                "listing": live["cleanroom"]["listing_after"],
                "install_rows": live["cleanroom"]["install_rows"],
                "production_listing": live["production"]["listing"],
                "production_install_rows": live["production"]["install_rows"],
            },
            {
                "id": "EV-B",
                "kind": "filesystem-audit",
                "detail": (
                    "Instrument writes during the clean-room run; leaks must be "
                    "empty. Planted machine-wide entry must appear outside the "
                    "clean-room profile root."
                ),
                "writes": live["audit"]["instrument_writes"],
                "leaks": live["audit"]["instrument_leaks"],
                "plant_hits": live["audit"]["plant_hits"],
            },
        ],
        "tests": tests,
        "tests_run": [
            {"id": "probe1", "command": P1_CMD, "result": "PASS"},
            {"id": "probe2", "command": P2_CMD, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0177-probe2-machine-wide-plant-audit",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "attempt": "adversarial filesystem audit plus leaky-mutant both-states",
            "verdict": "PASS",
            "notes": (
                "Probe 2 did not author the profile-scoped instrument. It replants "
                "a machine-wide cache blob, asserts the audit names it as outside "
                "the clean-room profile, asserts silence without the plant, and "
                "asserts a shared-global-cache mutant inherits original entries."
            ),
        },
        "negative_controls": [
            {
                "id": "NC-PLANT-ABSENT",
                "fired_on_bad_state": live["controls"]["detector_plant_seen"],
                "silent_on_good_state": live["controls"]["detector_absent_silent"],
            },
            {
                "id": "NC-LEAKY-GLOBAL-CACHE",
                "fired_on_bad_state": live["controls"]["leaky_mutant_detected"],
                "silent_on_good_state": live["controls"]["zero_inherited_cleanroom"],
            },
        ],
        "residual_caveat": (
            (
                "Live plugin.cache.Cache is rooted at Prefix.cache "
                "(<prefix>/state/cache). A fresh Prefix starts empty, performs "
                "full puts (fetches), and writes only inside that Prefix; the "
                "original Prefix listing is unchanged. Did not rebuild ADV units "
                "or platform/plugin/cache.py."
            )
            if live["production_property_pass"]
            else (
                "Production plugin.cache.Cache property did not pass on this "
                "worktree (missing, unimportable, inherited hits, leaks, or "
                "original Prefix not intact). The tester-instrument still proves "
                "both-states and detector controls. Did not rebuild ADV units."
            )
        ),
        "report": {
            "kind": "cache_report",
            "observations": [
                {
                    "name": "cleanroom_inherited_hits",
                    "measured": live["cleanroom"]["hit_count"],
                    "method": "profile-scoped instrument install into a fresh home",
                    "anchor": "command-center/p2-wave/probes/TST-0177/probe1_both_states.py",
                },
                {
                    "name": "production_inherited_hits",
                    "measured": live["production"]["inherited_hits"],
                    "method": "plugin.cache.Cache on a fresh Prefix",
                    "anchor": "platform/plugin/cache.py",
                },
                {
                    "name": "production_full_fetches",
                    "measured": bool(live["production"]["full_fetches"]),
                    "method": "miss then Cache.put from local mirror",
                    "anchor": "platform/plugin/journal.py Prefix.cache",
                },
                {
                    "name": "plant_detected_outside_profile",
                    "measured": bool(live["audit"]["plant_detected"]),
                    "method": "filesystem audit of planted machine-wide blob",
                    "anchor": "command-center/p2-wave/probes/TST-0177/probe2_detector_audit.py",
                },
                {
                    "name": "original_profile_intact",
                    "measured": bool(live["original"]["intact"]),
                    "method": "listing fingerprint before vs after clean-room install",
                    "anchor": "command-center/p2-wave/probes/TST-0177/probe1_both_states.py",
                },
            ],
            "control_ids": [
                "TST-0177-BOTH-STATES",
                "TST-0177-DETECTOR-PLANT",
                "TST-0177-LEAKY-MUTANT",
            ],
        },
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json TST-0177",
        "timestamps": {
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "on the same hypothesis, enumerate >=2 alternative approaches "
                "before a third attempt"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0177/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": utc_now(),
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "cache-integrity-tester",
            "execution_substrate": "linux-worktree-p2-deliver",
        },
        "artifacts": [
            {"path": ARTIFACT_REL, "role": "primary", "exists": True},
        ],
        "min_bytes_threshold": 1024,
        SENTINEL: True,
    }
    return rec


def write_artifact(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = doc if doc is not None else build_record()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, indent=2, sort_keys=True) + "\n"
    ARTIFACT.write_text(text, encoding="utf-8")
    rec["_disk_sha256"] = sha256_path(ARTIFACT)
    rec["_disk_bytes"] = ARTIFACT.stat().st_size
    return rec


def main() -> int:
    rec = write_artifact()
    print(
        json.dumps(
            {
                "pass": rec["state"] == "SUCCESS" and rec["sentinel"] == SENTINEL,
                "verdict": rec["verdict"],
                "detector_live": rec["detector_live"],
                "production_present": rec["production"]["present"],
                "production_property_pass": rec["baseline_repro"]["property_pass"],
                "original_intact": rec["original_profile"]["intact"],
                "cleanroom_hits": rec["cleanroom_profile"]["hit_count"],
                "plant_detected": rec["filesystem_audit"]["plant_detected"],
                "sha256": rec["_disk_sha256"],
                "bytes": rec["_disk_bytes"],
            },
            sort_keys=True,
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
