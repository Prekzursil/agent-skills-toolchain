"""Shared IMP-0410 scenarios: expiry, renew-extends, advisory, unleased control."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MANAGER_PY = REPO / "command-center" / "leases" / "manager.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("imp0410_leases_manager", MANAGER_PY)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MANAGER_PY}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["imp0410_leases_manager"] = mod
    spec.loader.exec_module(mod)
    return mod


def _mgr(mod, tmp: Path, clock):
    store = tmp / "lease-store"
    store.mkdir(parents=True, exist_ok=True)
    return mod.FileLeaseManager(store, clock=clock.now), tmp / "workspace"


def run_expiry(tmp: Path) -> dict:
    """After TTL, a non-holder write no longer logs a conflict; before TTL it does."""
    mod = load_manager()
    clock = mod.FakeClock(1000.0)
    mgr, ws = _mgr(mod, tmp / "expiry", clock)
    leased = "src/leased.txt"
    lease = mgr.acquire("sess-A", [leased], ttl_seconds=10.0)
    clock.advance(5.0)
    mid = mgr.note_write(
        "sess-B",
        leased,
        payload=b"intruder-before-expiry",
        dest=ws / leased,
    )
    clock.advance(6.0)
    post = mgr.note_write(
        "sess-C",
        leased,
        payload=b"after-expiry",
        dest=ws / leased,
    )
    mid_ok = (
        mid["ok"]
        and not mid["refused"]
        and mid["conflict"]
        and (ws / leased).read_bytes() == b"after-expiry"
    )
    post_ok = post["ok"] and not post["refused"] and not post["conflict"]
    passed = mid_ok and post_ok and lease["expires_at"] == 1010.0
    return {
        "id": "expiry",
        "pass": passed,
        "result": "PASS" if passed else "FAIL",
        "lease_id": lease["lease_id"],
        "before_expiry_conflict": mid["conflict"],
        "before_expiry_refused": mid["refused"],
        "after_expiry_conflict": post["conflict"],
        "after_expiry_refused": post["refused"],
        "write_succeeded_after_expiry": post["write_succeeded"],
        "on_disk_after": (ws / leased).read_bytes().decode("utf-8"),
    }


def run_renew_extends(tmp: Path) -> dict:
    """Renew moves expiry past the original TTL so a late non-holder still logs."""
    mod = load_manager()
    clock = mod.FakeClock(2000.0)
    mgr, ws = _mgr(mod, tmp / "renew", clock)
    path = "src/renewed.txt"
    lease = mgr.acquire("sess-A", [path], ttl_seconds=10.0)
    clock.advance(8.0)
    renewed = mgr.renew("sess-A", lease["lease_id"])
    clock.advance(5.0)
    late = mgr.note_write(
        "sess-B",
        path,
        payload=b"still-leased",
        dest=ws / path,
    )
    clock2 = mod.FakeClock(2000.0)
    mgr2, ws2 = _mgr(mod, tmp / "renew-control", clock2)
    mgr2.acquire("sess-A", [path], ttl_seconds=10.0)
    clock2.advance(13.0)
    control = mgr2.note_write(
        "sess-B",
        path,
        payload=b"unrenewed-expired",
        dest=ws2 / path,
    )
    passed = (
        bool(renewed.get("ok"))
        and float(renewed["expires_at"]) == 2018.0
        and late["conflict"]
        and not late["refused"]
        and late["write_succeeded"]
        and not control["conflict"]
        and (ws / path).read_bytes() == b"still-leased"
    )
    return {
        "id": "renew_extends",
        "pass": passed,
        "result": "PASS" if passed else "FAIL",
        "original_expires_at": 2010.0,
        "renewed_expires_at": renewed.get("expires_at"),
        "late_write_conflict": late["conflict"],
        "late_write_refused": late["refused"],
        "unrenewed_control_conflict": control["conflict"],
        "on_disk": (ws / path).read_bytes().decode("utf-8"),
    }


def run_advisory(tmp: Path) -> dict:
    """Non-holder writes always land on disk and always log a conflict event."""
    mod = load_manager()
    clock = mod.FakeClock(3000.0)
    mgr, ws = _mgr(mod, tmp / "advisory", clock)
    path = "src/advisory.txt"
    lease = mgr.acquire("sess-A", [path], ttl_seconds=60.0)
    dest = ws / path
    result = mgr.note_write(
        "sess-B",
        path,
        payload=b"non-holder-payload",
        dest=dest,
    )
    excerpt = []
    for ev in result["conflicts"]:
        excerpt.append(
            {
                "event": "lease-conflict",
                "path": ev["path"],
                "writer_session": ev["writer_session"],
                "holder_session": ev["holder_session"],
                "lease_id": ev["lease_id"],
                "write_allowed": True,
                "write_succeeded": True,
                "ts": ev["ts"],
            }
        )
    passed = (
        result["ok"]
        and not result["refused"]
        and result["conflict"]
        and dest.is_file()
        and dest.read_bytes() == b"non-holder-payload"
        and len(excerpt) == 1
        and excerpt[0]["holder_session"] == "sess-A"
        and excerpt[0]["writer_session"] == "sess-B"
    )
    return {
        "id": "advisory",
        "pass": passed,
        "result": "PASS" if passed else "FAIL",
        "lease_id": lease["lease_id"],
        "refused": result["refused"],
        "conflict": result["conflict"],
        "write_succeeded": result["write_succeeded"],
        "on_disk": dest.read_bytes().decode("utf-8") if dest.is_file() else "",
        "event_log_excerpt": excerpt,
    }


def run_unleased_negative(tmp: Path) -> dict:
    """A write to a path nobody leased must produce zero conflict events."""
    mod = load_manager()
    clock = mod.FakeClock(4000.0)
    mgr, ws = _mgr(mod, tmp / "unleased", clock)
    mgr.acquire("sess-A", ["src/other.txt"], ttl_seconds=60.0)
    path = "src/unleased.txt"
    dest = ws / path
    result = mgr.note_write("sess-B", path, payload=b"free-path", dest=dest)
    conflicts = mgr.conflict_events()
    passed = (
        result["ok"]
        and not result["refused"]
        and not result["conflict"]
        and dest.read_bytes() == b"free-path"
        and len(conflicts) == 0
    )
    return {
        "id": "unleased_negative_control",
        "pass": passed,
        "result": "PASS" if passed else "FAIL",
        "conflict": result["conflict"],
        "conflict_event_count": len(conflicts),
        "refused": result["refused"],
        "on_disk": dest.read_bytes().decode("utf-8") if dest.is_file() else "",
    }


def blocking_mutant_refuses(tmp: Path) -> dict:
    """Both-states control: a blocking wrapper refuses the write the real manager allows."""
    mod = load_manager()
    clock = mod.FakeClock(5000.0)
    mgr, ws = _mgr(mod, tmp / "mutant", clock)
    path = "src/mutant.txt"
    mgr.acquire("sess-A", [path], ttl_seconds=60.0)
    dest = ws / path
    live = mgr.note_write("sess-B", path, payload=b"live", dest=dest)

    def blocking_write(session_id: str, p: str, payload: bytes, dest_path: Path) -> dict:
        foreign = [h for h in mgr.active_holders(p) if h.get("session_id") != session_id]
        if foreign:
            return {
                "ok": False,
                "refused": True,
                "conflict": True,
                "write_succeeded": False,
                "bytes_written": 0,
            }
        return mgr.note_write(session_id, p, payload=payload, dest=dest_path)

    mutant = blocking_write("sess-B", path, b"mutant", dest)
    fired = (not live["refused"] and live["ok"]) and mutant["refused"] and not mutant["ok"]
    return {
        "id": "blocking_mutant",
        "pass": fired,
        "result": "PASS" if fired else "FAIL",
        "live_refused": live["refused"],
        "mutant_refused": mutant["refused"],
        "fired_on_bad_state": mutant["refused"],
        "silent_on_good_state": not live["refused"],
    }


def run_all(tmp: Path) -> dict:
    rows = {
        "expiry": run_expiry(tmp),
        "renew_extends": run_renew_extends(tmp),
        "advisory": run_advisory(tmp),
        "unleased_negative_control": run_unleased_negative(tmp),
        "blocking_mutant": blocking_mutant_refuses(tmp),
    }
    return rows
