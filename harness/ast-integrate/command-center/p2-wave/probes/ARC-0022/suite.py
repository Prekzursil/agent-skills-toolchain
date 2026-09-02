"""Executable ARC-0022 tests: named matrix plus guard-removal mutations."""
from __future__ import annotations

from marketplace import (
    ALL_GUARDS,
    DEFINED,
    EVENTS,
    STATES,
    World,
    all_pairs,
    defined_pairs,
    disposition,
    fixture_packages,
    fresh_world,
    seed_corrupt_cache,
    seed_ghost_cache,
    seed_stale_cache,
    sha256_bytes,
)

PROBE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0022/{script}"
)


def _fail(why: str, world: World) -> dict:
    return {
        "pass": False,
        "why": why,
        "state": world.state,
        "error": world.last_error,
        "trace": list(world.trace),
        "lockfile": dict(world.lockfile),
        "installed": {k: {kk: vv for kk, vv in v.items() if kk != "bytes"} for k, v in world.installed.items()},
    }


def _ok(world: World, **extra) -> dict:
    rec = {
        "pass": True,
        "why": None,
        "state": world.state,
        "error": world.last_error,
        "trace": list(world.trace),
        "lockfile": dict(world.lockfile),
        "installed": {k: {kk: vv for kk, vv in v.items() if kk != "bytes"} for k, v in world.installed.items()},
    }
    rec.update(extra)
    return rec


def test_install(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    pin = w.lockfile.get("pkg.core")
    inst = w.installed.get("pkg.core")
    if w.state != "active" or inst is None or inst["version"] != "1.0.0":
        return _fail("clean-install-not-active", w)
    if pin is None or pin.get("sha256") != inst["sha256"]:
        return _fail("lockfile-pin-missing", w)
    return _ok(w)


def test_upgrade(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    w.upgrade("pkg.core", "1.1.0")
    inst = w.installed.get("pkg.core")
    pin = w.lockfile.get("pkg.core")
    honest = fixture_packages()[("pkg.core", "1.1.0")]
    if w.state != "active" or inst is None or inst["version"] != "1.1.0":
        return _fail("upgrade-not-active", w)
    if inst["sha256"] != honest.sha256:
        return _fail("upgrade-hash-drift", w)
    if not pin or not pin.get("previous") or pin["previous"]["version"] != "1.0.0":
        return _fail("upgrade-previous-pin-missing", w)

    w2 = fresh_world(guards=guards)
    w2.install("pkg.core", "1.0.0")
    rotten_body = b"rotten-upgrade-bytes-not-matching-index-digest"
    honest_pkg = w2.index[("pkg.core", "1.1.0")]
    w2.index[("pkg.core", "1.1.0")] = type(honest_pkg)(
        package_id=honest_pkg.package_id,
        version=honest_pkg.version,
        channel=honest_pkg.channel,
        payload=rotten_body,
        sha256=honest_pkg.sha256,
        signature=honest_pkg.signature,
        malicious=False,
    )
    w2.upgrade("pkg.core", "1.1.0")
    got = w2.installed.get("pkg.core")
    if got and sha256_bytes(got["bytes"]) != honest.sha256 and got["version"] == "1.1.0":
        return _fail("corrupt-upgrade-became-active", w2)
    if "G_VERIFY" in guards and w2.state not in {"quarantined", "failed"}:
        return _fail("corrupt-upgrade-not-refused", w2)
    w.trace.extend(w2.trace)
    return _ok(w, fault_state=w2.state)


def test_downgrade(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    w.upgrade("pkg.core", "1.1.0")
    w.downgrade("pkg.core", "0.9.0")
    inst = w.installed.get("pkg.core")
    want = fixture_packages()[("pkg.core", "0.9.0")]
    if w.state != "active" or inst is None or inst["version"] != "0.9.0":
        return _fail("downgrade-not-0.9.0", w)
    if inst["sha256"] != want.sha256:
        return _fail("downgrade-hash-drift", w)

    w2 = fresh_world(guards=guards)
    w2.install("pkg.core", "1.0.0")
    w2.upgrade("pkg.core", "1.1.0")
    seed_ghost_cache(w2)
    w2.downgrade("pkg.core", "0.8.0")
    ghost = w2.installed.get("pkg.core")
    if ghost and ghost.get("version") == "0.8.0":
        return _fail("ghost-downgrade-installed", w2)
    w.trace.extend(w2.trace)
    return _ok(w, ghost_state=w2.state)


def test_rollback(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    w.upgrade("pkg.core", "1.1.0")
    w.rollback("pkg.core")
    inst = w.installed.get("pkg.core")
    want = fixture_packages()[("pkg.core", "1.0.0")]
    if w.state != "active" or inst is None or inst["version"] != "1.0.0":
        return _fail("rollback-not-previous-1.0.0", w)
    if inst["sha256"] != want.sha256:
        return _fail("rollback-hash-drift", w)
    if inst["version"] == "1.2.0":
        return _fail("rollback-jumped-to-latest", w)
    return _ok(w)


def test_uninstall(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    w.uninstall("pkg.core")
    if w.state != "absent":
        return _fail("uninstall-not-absent", w)
    if "pkg.core" in w.installed or "pkg.core" in w.lockfile:
        return _fail("uninstall-left-files-or-pin", w)
    return _ok(w)


def test_offline(guards: frozenset[str]) -> dict:
    export = fixture_packages()[("pkg.core", "1.0.0")]
    w = fresh_world(guards=guards, network=False)
    stale = fixture_packages()[("pkg.core", "1.1.0-stale")]
    w.cache[w.cache_key("pkg.core", "1.0.0")] = {
        "sha256": stale.sha256,
        "bytes": stale.payload,
        "corrupt": False,
    }
    w.install("pkg.core", "1.0.0", offline=True)
    inst = w.installed.get("pkg.core")
    if w.state != "active" or inst is None:
        return _fail("offline-install-not-active", w)
    if inst["sha256"] != export.sha256:
        return _fail("offline-used-stale-cache-not-export", w)

    w2 = fresh_world(guards=guards, network=False)
    w2.exports.clear()
    w2.cache[w2.cache_key("pkg.core", "1.0.0")] = {
        "sha256": stale.sha256,
        "bytes": stale.payload,
        "corrupt": False,
    }
    w2.install("pkg.core", "1.0.0", offline=True)
    if w2.state == "active":
        return _fail("offline-without-export-became-active", w2)
    w.trace.extend(w2.trace)
    return _ok(w, missing_export_state=w2.state)


def test_cache(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    stale = seed_stale_cache(w)
    honest = w.index[("pkg.core", "1.1.0")]
    w.install("pkg.core", "1.1.0")
    inst = w.installed.get("pkg.core")
    if w.state != "active" or inst is None:
        return _fail("cache-path-not-active", w)
    if inst["sha256"] == stale.sha256:
        return _fail("stale-cache-masked-fixed-package", w)
    if inst["sha256"] != honest.sha256:
        return _fail("cache-revalidate-wrong-hash", w)

    w2 = fresh_world(guards=guards)
    seed_corrupt_cache(w2)
    w2.install("pkg.core", "1.1.0")
    if w2.state != "cache_corrupt":
        return _fail("corrupt-cache-not-detected", w2)
    w2.recover("pkg.core", "1.1.0")
    inst2 = w2.installed.get("pkg.core")
    if w2.state != "active" or inst2 is None or inst2["sha256"] != honest.sha256:
        return _fail("corrupt-cache-recover-failed", w2)
    w.trace.extend(w2.trace)
    return _ok(w, recovered=True)


def test_malicious(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.evil", "1.0.0")
    inst = w.installed.get("pkg.evil")
    if w.state == "active" or (inst and inst.get("version") == "1.0.0" and w.state == "active"):
        return _fail("malicious-package-became-active", w)
    if w.state != "quarantined":
        return _fail("malicious-not-quarantined", w)
    if "pkg.evil" in w.lockfile:
        return _fail("malicious-was-pinned", w)
    return _ok(w)


def test_quarantine_uninstall(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    w.install("pkg.evil", "1.0.0")
    if w.state != "quarantined":
        return _fail("setup-not-quarantined", w)
    w.uninstall("pkg.evil")
    if w.state != "absent":
        return _fail("quarantine-uninstall-not-absent", w)
    return _ok(w)


def test_failed_retry(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards, network=False)
    w.exports.clear()
    w.install("pkg.core", "1.0.0", offline=True)
    if w.state != "failed":
        return _fail("setup-not-failed", w)
    w.network = True
    w.install("pkg.core", "1.0.0")
    if w.state != "active":
        return _fail("failed-retry-install-not-active", w)
    return _ok(w)


def test_failed_offline(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards, network=False)
    w.exports.clear()
    w.install("pkg.core", "1.0.0", offline=True)
    if w.state != "failed":
        return _fail("setup-not-failed", w)
    w.exports[("pkg.core", "1.0.0")] = fixture_packages()[("pkg.core", "1.0.0")].payload
    w.install("pkg.core", "1.0.0", offline=True)
    if w.state != "active":
        return _fail("failed-offline-retry-not-active", w)
    return _ok(w)


def test_failed_recover(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards, network=False)
    w.exports.clear()
    w.install("pkg.core", "1.0.0", offline=True)
    if w.state != "failed":
        return _fail("setup-not-failed", w)
    w.network = True
    w.recover("pkg.core", "1.0.0")
    if w.state != "active":
        return _fail("failed-recover-not-active", w)
    return _ok(w)


def test_failed_uninstall(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards, network=False)
    w.exports.clear()
    w.install("pkg.core", "1.0.0", offline=True)
    if w.state != "failed":
        return _fail("setup-not-failed", w)
    w.uninstall("pkg.core")
    if w.state != "absent":
        return _fail("failed-uninstall-not-absent", w)
    return _ok(w)


def test_cache_uninstall(guards: frozenset[str]) -> dict:
    w = fresh_world(guards=guards)
    seed_corrupt_cache(w)
    w.install("pkg.core", "1.1.0")
    if w.state != "cache_corrupt":
        return _fail("setup-not-cache-corrupt", w)
    w.uninstall("pkg.core")
    if w.state != "absent":
        return _fail("cache-corrupt-uninstall-not-absent", w)
    return _ok(w)


def test_abort_paths(guards: frozenset[str]) -> dict:
    traces: list[tuple[str, str, str]] = []
    for stop in ("resolving", "fetching", "verifying", "staging"):
        w = fresh_world(guards=guards)
        w.install("pkg.core", "1.0.0", abort_at=stop)
        traces.extend(w.trace)
        if w.state == "active":
            return _fail(f"abort-at-{stop}-still-active", w)
        if stop == "resolving" and w.state != "failed":
            return _fail(f"abort-at-resolving-state={w.state}", w)

    w = fresh_world(guards=guards)
    w.abort_now()
    traces.extend(w.trace)
    if w.state != "absent":
        return _fail("absent-abort-moved", w)

    w = fresh_world(guards=guards)
    w.install("pkg.core", "1.0.0")
    w.abort_now()
    traces.extend(w.trace)
    if w.state != "active":
        return _fail("active-abort-left-active", w)
    w.cache[w.cache_key("pkg.core", "1.0.0")] = {
        "sha256": "00",
        "bytes": b"x",
        "corrupt": True,
    }
    w.fire("cache_corrupt")
    traces.extend(w.trace[-1:])
    if w.state != "cache_corrupt":
        return _fail("active-cache-corrupt-missed", w)
    w.abort_now()
    traces.extend(w.trace[-1:])
    if w.state != "failed":
        return _fail("cache-corrupt-abort-not-failed", w)
    w.abort_now()
    traces.extend(w.trace[-1:])
    if w.state != "absent":
        return _fail("failed-abort-not-absent", w)

    w = fresh_world(guards=guards)
    w.install("pkg.evil", "1.0.0")
    if w.state != "quarantined":
        return _fail("abort-setup-not-quarantined", w)
    w.abort_now()
    traces.extend(w.trace[-1:])
    if w.state != "quarantined":
        return _fail("quarantined-abort-moved", w)

    w_all = fresh_world(guards=guards)
    w_all.trace = traces
    return _ok(w_all)


NAMED = [
    {
        "id": "T-INSTALL",
        "title": "clean install",
        "guard": "G_PIN",
        "fn": test_install,
        "operations": ["install"],
    },
    {
        "id": "T-UPGRADE",
        "title": "upgrade",
        "guard": "G_VERIFY",
        "fn": test_upgrade,
        "operations": ["upgrade"],
    },
    {
        "id": "T-DOWNGRADE",
        "title": "downgrade",
        "guard": "G_DOWNGRADE_WINDOW",
        "fn": test_downgrade,
        "operations": ["downgrade"],
    },
    {
        "id": "T-ROLLBACK",
        "title": "rollback",
        "guard": "G_ROLLBACK_PREV",
        "fn": test_rollback,
        "operations": ["rollback"],
    },
    {
        "id": "T-UNINSTALL",
        "title": "uninstall",
        "guard": "G_UNINSTALL_CLEAN",
        "fn": test_uninstall,
        "operations": ["uninstall"],
    },
    {
        "id": "T-OFFLINE",
        "title": "offline install from export",
        "guard": "G_OFFLINE_EXPORT",
        "fn": test_offline,
        "operations": ["offline_install"],
    },
    {
        "id": "T-CACHE",
        "title": "corrupted-cache recovery / stale-cache must not mask a fix",
        "guard": "G_CACHE_REVALIDATE",
        "fn": test_cache,
        "operations": ["cache_corrupt", "recover"],
    },
    {
        "id": "T-MALICIOUS",
        "title": "malicious-package rejection",
        "guard": "G_MALICE",
        "fn": test_malicious,
        "operations": ["malicious"],
    },
]

EXTRA = [
    {
        "id": "T-QUARANTINE-UNINSTALL",
        "title": "uninstall from quarantined",
        "guard": "G_MALICE",
        "fn": test_quarantine_uninstall,
        "operations": ["uninstall"],
    },
    {
        "id": "T-FAILED-RETRY",
        "title": "retry install from failed",
        "guard": "G_PIN",
        "fn": test_failed_retry,
        "operations": ["install"],
    },
    {
        "id": "T-FAILED-OFFLINE",
        "title": "retry offline install from failed",
        "guard": "G_OFFLINE_EXPORT",
        "fn": test_failed_offline,
        "operations": ["offline_install"],
    },
    {
        "id": "T-FAILED-RECOVER",
        "title": "recover from failed",
        "guard": "G_CACHE_REVALIDATE",
        "fn": test_failed_recover,
        "operations": ["recover"],
    },
    {
        "id": "T-FAILED-UNINSTALL",
        "title": "uninstall from failed",
        "guard": "G_UNINSTALL_CLEAN",
        "fn": test_failed_uninstall,
        "operations": ["uninstall"],
    },
    {
        "id": "T-CACHE-UNINSTALL",
        "title": "uninstall from cache_corrupt",
        "guard": "G_UNINSTALL_CLEAN",
        "fn": test_cache_uninstall,
        "operations": ["uninstall"],
    },
    {
        "id": "T-ABORT-PATHS",
        "title": "abort from every state that defines it",
        "guard": "G_PIN",
        "fn": test_abort_paths,
        "operations": ["abort", "cache_corrupt"],
    },
]


def run_one(spec: dict, guards: frozenset[str] | None = None) -> dict:
    g = ALL_GUARDS if guards is None else frozenset(guards)
    rec = spec["fn"](g)
    rec["id"] = spec["id"]
    rec["guard"] = spec["guard"]
    rec["title"] = spec["title"]
    return rec


def run_suite(guards: frozenset[str] | None = None, *, extras: bool = True) -> list[dict]:
    specs = list(NAMED) + (list(EXTRA) if extras else [])
    return [run_one(s, guards) for s in specs]


def mutation_for(spec: dict) -> dict:
    removed = spec["guard"]
    mutant = ALL_GUARDS - {removed}
    green = run_one(spec, ALL_GUARDS)
    red = run_one(spec, mutant)
    return {
        "id": f"MUT-{spec['id']}",
        "test_id": spec["id"],
        "guard_removed": removed,
        "green_with_guard": bool(green.get("pass")),
        "red_without_guard": not bool(red.get("pass")),
        "turns_red": bool(green.get("pass")) and not bool(red.get("pass")),
        "green_why": green.get("why"),
        "red_why": red.get("why"),
        "green_trace": green.get("trace") or [],
        "red_trace": red.get("trace") or [],
    }


def guard_mutations(min_count: int = 3) -> list[dict]:
    rows = [mutation_for(s) for s in NAMED]
    return rows


def covered_defined(results: list[dict]) -> set[tuple[str, str]]:
    hit: set[tuple[str, str]] = set()
    for rec in results:
        for src, ev, dst in rec.get("trace") or []:
            if dst != "REJECTED" and (src, ev) in DEFINED:
                hit.add((src, ev))
    return hit


def coverage_report(results: list[dict]) -> dict:
    defined = defined_pairs()
    hit = covered_defined(results)
    uncovered = [{"state": s, "event": e} for s, e in defined if (s, e) not in hit]
    n_def = len(defined)
    n_hit = n_def - len(uncovered)
    ratio = (n_hit / n_def) if n_def else 0.0
    cells = []
    empty = []
    for state, event in all_pairs():
        disp = disposition(state, event)
        owners = sorted(
            rec["id"]
            for rec in results
            if any(src == state and ev == event for src, ev, _dst in rec.get("trace") or [])
        )
        cell = {
            "state": state,
            "event": event,
            "kind": disp["kind"],
            "next": disp["next"],
            "reason": disp["reason"],
            "covered_by": owners,
        }
        if disp["kind"] == "defined" and not owners:
            empty.append({"state": state, "event": event})
        cells.append(cell)
    return {
        "ratio": ratio,
        "defined_count": n_def,
        "covered_count": n_hit,
        "uncovered": uncovered,
        "matrix_empty_defined_cells": empty,
        "matrix_cell_count": len(cells),
        "rejected_count": sum(1 for c in cells if c["kind"] == "rejected"),
        "states": list(STATES),
        "events": list(EVENTS),
        "cells": cells,
        "method": "named+extra scenario traces / defined transitions (computed, not asserted)",
    }


def matrix_is_total() -> tuple[bool, list[str]]:
    missing = []
    for state, event in all_pairs():
        if (state, event) not in DEFINED:
            continue
    classified = {(s, e) for s, e in all_pairs()}
    if len(classified) != len(STATES) * len(EVENTS):
        missing.append("pair-set-size")
    for state, event in all_pairs():
        d = disposition(state, event)
        if d["kind"] not in {"defined", "rejected"}:
            missing.append(f"{state}+{event}")
        if d["kind"] == "defined" and (state, event) not in DEFINED:
            missing.append(f"defined-not-in-table:{state}+{event}")
    return (not missing, missing)
