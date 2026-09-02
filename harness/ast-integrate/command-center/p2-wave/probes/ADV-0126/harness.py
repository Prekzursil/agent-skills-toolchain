"""Bounded resource-exhaustion fixtures for ADV-0126.

HARD BOUND: disk-full runs only on a 1 MiB tmpfs. Commit pressure is a child
with RLIMIT_AS. Quota is a loopback HTTP fixture. A scenario that would
consume the host disk or host commit charge is aborted, not a finding.

This worktree is missing work_claim.py, cache_ownership.py, and
http_storm_scheduler.py. Those paths are recorded absent. Live write paths
that do exist are the ones exercised. No production rebuild.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import event_log as elog  # noqa: E402
import http_storm_scheduler as storm  # noqa: E402
import retry_engine as retry  # noqa: E402
import status_ledger as sl  # noqa: E402
import work_claim as claim  # noqa: E402
from tools.bench.baseline_store import BaselineStore  # noqa: E402
from tools.marketplace.ledger import (  # noqa: E402
    add_owned_file,
    empty_ledger,
    save_ledger,
)
from tools.marketplace.revocation_list.degrade import DegradeSink  # noqa: E402
from tools.marketplace.revocation_list.revocation import (  # noqa: E402
    FetchError,
    HttpTransport,
)
from tools.plugin.strict_json import emit_strict  # noqa: E402

UNIT = "ADV-0126"
TMPFS_SIZE = "1M"
TMPFS_BYTES = 1024 * 1024
COMMIT_AS_BYTES = 48 * 1024 * 1024
WRITE_ALARM_S = 8
HOST_MEM_FLOOR_KB = 256 * 1024
SEED_DOC = {
    "unit": UNIT,
    "kind": "preexisting-artifact",
    "payload": "seed-" + ("A" * 180),
}
PRESENT_MODULES = {
    rel: (REPO / rel).is_file()
    for rel in (
        "tools/command-center/work_claim.py",
        "tools/command-center/http_storm_scheduler.py",
        "tools/plugin/cache_ownership.py",
    )
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def mem_available_kb() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    return 0


def host_guard() -> dict[str, Any]:
    avail = mem_available_kb()
    du = shutil.disk_usage("/")
    ok = avail >= HOST_MEM_FLOOR_KB and du.free >= 64 * 1024 * 1024
    return {
        "mem_available_kb": avail,
        "root_free_bytes": int(du.free),
        "ok": ok,
        "reason": None if ok else "host-headroom-too-low-abort-not-a-finding",
    }


def _is_tmpfs(path: Path) -> bool:
    try:
        raw = Path("/proc/mounts").read_text(encoding="utf-8")
    except OSError:
        return False
    target = str(path.resolve())
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == target and parts[2] == "tmpfs":
            return True
    return False


class TinyTmpfs:
    """1 MiB dedicated tmpfs. Never fill the host root filesystem."""

    def __init__(self) -> None:
        self.mnt: Path | None = None
        self.mounted = False

    def __enter__(self) -> Path:
        guard = host_guard()
        if not guard["ok"]:
            raise RuntimeError(f"host guard: {guard}")
        self.mnt = Path(tempfile.mkdtemp(prefix="adv0126-vol-"))
        subprocess.check_call(
            [
                "mount",
                "-t",
                "tmpfs",
                "-o",
                f"size={TMPFS_SIZE},nr_inodes=256,mode=0755",
                "tmpfs",
                str(self.mnt),
            ]
        )
        self.mounted = True
        if not _is_tmpfs(self.mnt):
            raise RuntimeError("mounted path is not tmpfs; refusing to fill host disk")
        st = os.statvfs(self.mnt)
        cap = st.f_blocks * st.f_frsize
        if cap > 2 * TMPFS_BYTES:
            raise RuntimeError(f"tmpfs larger than bound: {cap}")
        return self.mnt

    def __exit__(self, *_exc: object) -> None:
        if self.mounted and self.mnt is not None:
            subprocess.run(
                ["umount", "-l", str(self.mnt)],
                check=False,
                capture_output=True,
            )
            self.mounted = False
        if self.mnt is not None:
            shutil.rmtree(self.mnt, ignore_errors=True)


class AlarmTimeout(Exception):
    pass


def _alarm_handler(_signum: int, _frame: object) -> None:
    raise AlarmTimeout("write-watchdog")


def with_alarm(seconds: int, fn: Callable[[], Any]) -> tuple[Any, str | None]:
    old = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(seconds)
    try:
        return fn(), None
    except AlarmTimeout as exc:
        return None, f"HANG:{exc}"
    except Exception as exc:  # noqa: BLE001 — record loud failure
        return None, f"{type(exc).__name__}:{getattr(exc, 'errno', '')}:{exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def fill_tmpfs(mnt: Path, leave_bytes: int = 600) -> dict[str, Any]:
    filler = mnt / ".filler"
    wrote = 0
    err: dict[str, Any] | None = None
    with filler.open("wb") as fh:
        while True:
            st = os.statvfs(mnt)
            free = st.f_bavail * st.f_frsize
            if free <= leave_bytes:
                break
            chunk = min(65536, max(free - leave_bytes, 1))
            try:
                fh.write(b"\x5a" * chunk)
                fh.flush()
                wrote += chunk
            except OSError as exc:
                err = {"errno": exc.errno, "msg": str(exc)}
                break
    st = os.statvfs(mnt)
    cap = st.f_blocks * st.f_frsize
    return {
        "filler_bytes": wrote,
        "free_after": st.f_bavail * st.f_frsize,
        "fill_errno": None if err is None else err["errno"],
        "volume_bytes": cap,
        "fstype_tmpfs": _is_tmpfs(mnt),
        "bounded": cap <= 2 * TMPFS_BYTES,
    }


def snapshot_files(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        exists = path.is_file()
        data = path.read_bytes() if exists else b""
        parseable = False
        if exists and data:
            try:
                json.loads(data.decode("utf-8"))
                parseable = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                parseable = False
        out[name] = {
            "path": str(path),
            "exists": exists,
            "bytes": len(data),
            "sha256": sha256_bytes(data) if exists else "",
            "parseable_json": parseable,
            "empty": exists and len(data) == 0,
        }
    return out


def integrity_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    preserved = True
    truncated = False
    for name, pre in before.items():
        post = after.get(name) or {}
        intact = (
            bool(pre.get("exists"))
            and bool(post.get("exists"))
            and pre.get("sha256") == post.get("sha256")
        )
        lost_parse = bool(pre.get("parseable_json")) and not bool(
            post.get("parseable_json")
        )
        emptied = bool(pre.get("bytes", 0) > 0) and bool(post.get("empty"))
        shrunk = int(post.get("bytes") or 0) < int(pre.get("bytes") or 0)
        if not intact:
            preserved = False
        if lost_parse or emptied or shrunk:
            truncated = True
        rows.append(
            {
                "name": name,
                "intact": intact,
                "lost_parseable_json": lost_parse,
                "emptied": emptied,
                "bytes_before": pre.get("bytes"),
                "bytes_after": post.get("bytes"),
                "sha_before": pre.get("sha256"),
                "sha_after": post.get("sha256"),
            }
        )
    return {
        "preserved_all": preserved,
        "any_truncated_or_unparseable": truncated,
        "files": rows,
    }


def _safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:300]


def _attempt(label: str, fn: Callable[[], Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    result, err = with_alarm(WRITE_ALARM_S, fn)
    dt = int((time.monotonic() - t0) * 1000)
    hung = bool(err and err.startswith("HANG:"))
    enospc = bool(err and ":28:" in err)
    loud = err is not None and not hung
    return {
        "label": label,
        "elapsed_ms": dt,
        "error": err,
        "hung": hung,
        "enospc": enospc,
        "loud_failure": loud,
        "succeeded": err is None,
        "result": None if err else _safe(result),
    }


def seed_program_roots(mnt: Path) -> dict[str, Path]:
    seed_json = mnt / "preexisting.json"
    seed_json.write_text(json.dumps(SEED_DOC, sort_keys=True) + "\n", encoding="utf-8")
    sibling = mnt / "sibling-ledger.json"
    sibling.write_text(
        json.dumps({"ledger": True, "entries": [1, 2, 3]}) + "\n", encoding="utf-8"
    )

    cc = mnt / "cc"
    (cc / "events").mkdir(parents=True)
    (cc / "receipts").mkdir(parents=True)
    events = cc / "events" / "EVENTS.jsonl"
    elog.append_record(events, {"unit": UNIT, "kind": "seed", "n": 1})
    sl.write_status(cc)

    claims = mnt / "claims"
    claim.prepare(claims)
    first = claim.dispatch(claims, "ADV0126-SEED", "sess-seed", {"k": "v"})
    if first.get("status") != claim.EXECUTED:
        raise RuntimeError(f"seed dispatch failed: {first}")

    plugin = mnt / "plugin-root"
    plugin.mkdir()
    plugin_json = plugin / "plugin.json"
    plugin_json.write_text(
        emit_strict({"name": UNIT, "kind": "plugin-manifest", "ok": True}) + "\n",
        encoding="utf-8",
    )

    mkt = mnt / "marketplace-ledger.json"
    ledger = empty_ledger()
    add_owned_file(
        ledger,
        package_id="seed",
        live_path="a.py",
        source_path="src/a.py",
        content_sha256="abc",
    )
    save_ledger(mkt, ledger)

    bench = mnt / "bench-store"
    store = BaselineStore(bench)
    store.write("case-seed", b'{"baseline":true}')

    degrade_path = mnt / "degrade.json"
    DegradeSink(degrade_path).warn_stale("seed-ok")

    return {
        "preexisting_json": seed_json,
        "sibling_ledger": sibling,
        "status_md": sl.status_path(cc),
        "events_jsonl": events,
        "seed_receipt": claim.receipt_path(claims, "ADV0126-SEED"),
        "plugin_json": plugin_json,
        "marketplace_ledger": mkt,
        "bench_pointers": store.pointers_path,
        "degrade_sink": degrade_path,
    }


def stress_writes(mnt: Path, paths: dict[str, Path]) -> list[dict[str, Any]]:
    cc = mnt / "cc"
    attempts: list[dict[str, Any]] = []

    def rewrite_preexisting() -> None:
        paths["preexisting_json"].write_text(
            json.dumps({"unit": UNIT, "kind": "rewrite", "payload": "B" * 8000}) + "\n",
            encoding="utf-8",
        )

    def rewrite_plugin() -> None:
        paths["plugin_json"].write_text(
            emit_strict(
                {"name": UNIT, "kind": "plugin-manifest", "payload": "C" * 4000}
            )
            + "\n",
            encoding="utf-8",
        )

    def rewrite_ledger() -> None:
        ledger = empty_ledger()
        add_owned_file(
            ledger,
            package_id="seed",
            live_path="a.py",
            source_path="src/a.py",
            content_sha256="abc",
        )
        add_owned_file(
            ledger,
            package_id="big",
            live_path="b.py",
            source_path="src/b.py",
            content_sha256="x" * 4000,
        )
        save_ledger(paths["marketplace_ledger"], ledger)

    attempts.append(_attempt("inplace-preexisting-json", rewrite_preexisting))
    attempts.append(_attempt("status_ledger.write_status", lambda: sl.write_status(cc)))
    attempts.append(_attempt("plugin.strict_json.emit", rewrite_plugin))
    attempts.append(_attempt("marketplace.save_ledger", rewrite_ledger))
    attempts.append(
        _attempt(
            "work_claim.dispatch-new-id",
            lambda: claim.dispatch(mnt / "claims", "ADV0126-NEW", "sess-new", {"n": 1}),
        )
    )
    attempts.append(
        _attempt(
            "event_log.append_record",
            lambda: elog.append_record(
                paths["events_jsonl"],
                {"unit": UNIT, "kind": "after-full", "payload": "D" * 4000},
            ),
        )
    )
    attempts.append(
        _attempt(
            "baseline_store.write-large",
            lambda: BaselineStore(mnt / "bench-store").write("case-big", b"C" * 8000),
        )
    )
    attempts.append(
        _attempt(
            "degrade_sink.warn_stale",
            lambda: DegradeSink(paths["degrade_sink"]).warn_stale("after-full"),
        )
    )
    attempts.append(
        _attempt(
            "new-sibling-file",
            lambda: (mnt / "new-after-full.json").write_text(
                '{"n":1}\n', encoding="utf-8"
            ),
        )
    )
    return attempts


def run_disk_full_battery() -> dict[str, Any]:
    guard0 = host_guard()
    if not guard0["ok"]:
        return {"aborted": True, "hung": False, "host_guard": guard0, "fill": {}}
    with TinyTmpfs() as mnt:
        paths = seed_program_roots(mnt)
        before = snapshot_files(paths)
        fill = fill_tmpfs(mnt, leave_bytes=400)
        if not fill["bounded"] or not fill["fstype_tmpfs"]:
            raise RuntimeError(f"volume escaped bound: {fill}")
        attempts = stress_writes(mnt, paths)
        after = snapshot_files(paths)
        delta = integrity_delta(before, after)
        hung = any(a["hung"] for a in attempts)
        loud = any(a["loud_failure"] or a["enospc"] for a in attempts)
        return {
            "scenario": "disk-full-1MiB-tmpfs",
            "aborted": False,
            "host_guard_before": guard0,
            "host_guard_after": host_guard(),
            "fill": fill,
            "attempts": attempts,
            "before": before,
            "after": after,
            "integrity": delta,
            "hung": hung,
            "any_loud_enospc": loud,
            "fail_loudly": (not hung) and loud,
            "preserved_preexisting": bool(delta["preserved_all"]),
            "sibling_ledger_intact": after["sibling_ledger"].get("sha256")
            == before["sibling_ledger"]["sha256"],
            "events_jsonl_intact": after["events_jsonl"].get("sha256")
            == before["events_jsonl"]["sha256"],
            "seed_receipt_intact": after["seed_receipt"].get("sha256")
            == before["seed_receipt"]["sha256"],
            "preexisting_still_parseable": after["preexisting_json"]["parseable_json"],
            "present_modules": dict(PRESENT_MODULES),
        }


def run_unconstrained_control() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="adv0126-free-"))
    try:
        paths = seed_program_roots(root)
        before = snapshot_files(paths)
        attempts = stress_writes(root, paths)
        after = snapshot_files(paths)
        ok = all(a["succeeded"] for a in attempts) and (
            after["sibling_ledger"]["sha256"] == before["sibling_ledger"]["sha256"]
        )
        return {
            "scenario": "unconstrained-volume-control",
            "ok": ok,
            "attempts": [
                {
                    "label": a["label"],
                    "succeeded": a["succeeded"],
                    "error": a["error"],
                }
                for a in attempts
            ],
            "sibling_intact": after["sibling_ledger"]["sha256"]
            == before["sibling_ledger"]["sha256"],
            "events_jsonl_intact": after["events_jsonl"]["sha256"]
            == before["events_jsonl"]["sha256"],
            "seed_receipt_intact": after["seed_receipt"]["sha256"]
            == before["seed_receipt"]["sha256"],
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _QuotaHandler(BaseHTTPRequestHandler):
    body = b'{"error":"quota_exceeded","code":"QUOTA"}'
    status = 403

    def log_message(self, _fmt: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(int(self.status))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def do_POST(self) -> None:  # noqa: N802
        self.do_GET()


class _OkHandler(_QuotaHandler):
    body = b'{"ok":true}'
    status = 200


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[str, ThreadingHTTPServer]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host, port = httpd.server_address[:2]
    return f"http://{host}:{port}/quota", httpd


def run_quota_fixture() -> dict[str, Any]:
    url, httpd = _serve(_QuotaHandler)
    t0 = time.monotonic()
    fetch_err = None
    body = b""
    transport_ok = False
    raw_ok = False
    status = 0
    try:
        try:
            HttpTransport(url, timeout=2.0).fetch_bytes()
            transport_ok = True
        except FetchError as exc:
            fetch_err = str(exc)
        try:
            urllib.request.urlopen(url, timeout=2.0).read()
            raw_ok = True
            status = 200
        except urllib.error.HTTPError as exc:
            raw_ok = False
            status = int(exc.code)
            body = exc.read()
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raw_ok = False
            fetch_err = f"{fetch_err}; {exc}"
    finally:
        httpd.shutdown()
        httpd.server_close()
    elapsed = int((time.monotonic() - t0) * 1000)

    policy = retry.parse_retry_policy(
        "NO automatic retry: this unit is a destructive, state-changing or "
        "owner-gated drill. On failure STOP"
    )
    decision = retry.decide(
        [retry.TypedFailure(failure_class="blocked", fingerprint="quota-exhausted")],
        policy,
    )
    grind = retry.observe_attempts(
        "blocked",
        policy,
        distinct_fingerprints=False,
        fingerprint="quota-exhausted",
    )
    quota_policy = storm.classify(403)
    ok_policy = storm.classify(200)

    url_ok, httpd_ok = _serve(_OkHandler)
    try:
        healthy = HttpTransport(url_ok, timeout=2.0).fetch_bytes()
        healthy_ok = healthy == b'{"ok":true}'
    except FetchError as exc:
        healthy_ok = False
        fetch_err = f"{fetch_err}; healthy:{exc}"
    finally:
        httpd_ok.shutdown()
        httpd_ok.server_close()

    loud = (not transport_ok) and fetch_err is not None and elapsed < 5000
    no_retry = decision.action == "STOP" and grind.observed_attempt_count == 1
    quota_not_ok = (not transport_ok) and status == 403
    return {
        "scenario": "quota-exhausted-loopback-fixture",
        "http_status": status,
        "transport_ok": transport_ok,
        "raw_ok": raw_ok,
        "fetch_error": fetch_err,
        "body_head": body[:80].decode("utf-8", "replace"),
        "elapsed_ms": elapsed,
        "loud_failure": loud,
        "hung": elapsed >= 5000,
        "retry_decision": decision.as_dict(),
        "retry_observed_attempts": grind.observed_attempt_count,
        "no_automatic_retry": no_retry,
        "classify_403": quota_policy.as_dict(),
        "classify_200": ok_policy.as_dict(),
        "quota_not_classified_ok": quota_policy.classification != storm.CLASS_OK,
        "healthy_control_ok": healthy_ok,
        "http_storm_scheduler_present": PRESENT_MODULES[
            "tools/command-center/http_storm_scheduler.py"
        ],
        "pass": loud
        and no_retry
        and healthy_ok
        and (quota_policy.classification != storm.CLASS_OK)
        and quota_not_ok,
    }


def _commit_child() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (COMMIT_AS_BYTES, COMMIT_AS_BYTES))
    chunks: list[bytearray] = []
    try:
        while True:
            chunks.append(bytearray(1024 * 1024))
        print(json.dumps({"unexpected_success": True, "n": len(chunks)}))
    except MemoryError:
        print(json.dumps({"loud": True, "exc": "MemoryError", "n": len(chunks)}))
    except OSError as exc:
        print(
            json.dumps(
                {
                    "loud": True,
                    "exc": type(exc).__name__,
                    "errno": exc.errno,
                    "n": len(chunks),
                }
            )
        )


def run_commit_pressure() -> dict[str, Any]:
    guard0 = host_guard()
    if not guard0["ok"]:
        return {"pass": False, "aborted": True, "host_guard": guard0}
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(HERE / "harness.py"), "--commit-child"],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=8,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    guard1 = host_guard()
    payload: dict[str, Any] = {}
    try:
        if proc.stdout.strip():
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        payload = {"parse_error": proc.stdout[-500:]}
    host_untouched = guard1["mem_available_kb"] + 2_000_000 >= guard0["mem_available_kb"]
    loud = bool(payload.get("loud")) or proc.returncode != 0
    hung = elapsed >= 7000
    return {
        "scenario": "commit-pressure-rlimit-as-child",
        "rlimit_as_bytes": COMMIT_AS_BYTES,
        "elapsed_ms": elapsed,
        "child_returncode": proc.returncode,
        "payload": payload,
        "stderr_tail": (proc.stderr or "")[-400:],
        "loud_failure": loud,
        "hung": hung,
        "host_guard_before": guard0,
        "host_guard_after": guard1,
        "host_commit_untouched": host_untouched,
        "bounded": True,
        "pass": loud and (not hung) and host_untouched,
    }


def plant_and_detect_truncation() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="adv0126-nc-"))
    try:
        good = root / "good.json"
        bad = root / "truncated.json"
        good.write_text(json.dumps({"ok": True, "n": 1}) + "\n", encoding="utf-8")
        bad.write_text('{"ok": true, "payload": "AAAA', encoding="utf-8")
        snap = snapshot_files({"good": good, "bad": bad})
        fired = (
            snap["bad"]["parseable_json"] is False
            and snap["good"]["parseable_json"] is True
        )
        silent_good = snap["good"]["parseable_json"] is True
        return {
            "id": "NC-TRUNCATED-JSON-AUDITOR",
            "fired_on_bad_state": fired,
            "silent_on_good_state": silent_good,
            "good": snap["good"],
            "bad": snap["bad"],
            "pass": fired and silent_good,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def audit_disk_full_postcondition() -> dict[str, Any]:
    """Probe-2 mechanism: re-seed, exhaust, then only audit bytes/JSON validity."""
    with TinyTmpfs() as mnt:
        paths = seed_program_roots(mnt)
        expected = snapshot_files(paths)
        fill_tmpfs(mnt, leave_bytes=400)
        stress_writes(mnt, paths)
        observed = snapshot_files(paths)
        delta = integrity_delta(expected, observed)
        still_present = {name: observed[name]["exists"] for name in expected}
        return {
            "scenario": "postcondition-audit",
            "expected_sha": {k: v["sha256"] for k, v in expected.items()},
            "observed": observed,
            "integrity": delta,
            "all_paths_still_present": all(still_present.values()),
            "present": still_present,
        }


def run_probe1() -> dict[str, Any]:
    disk = run_disk_full_battery()
    control = run_unconstrained_control()
    quota = run_quota_fixture()
    commit = run_commit_pressure()
    nc = plant_and_detect_truncation()
    protocol_ok = (
        not disk.get("aborted")
        and not disk.get("hung")
        and control.get("ok") is True
        and quota.get("pass") is True
        and commit.get("pass") is True
        and nc.get("pass") is True
        and disk.get("fill", {}).get("bounded") is True
        and disk.get("host_guard_after", {}).get("ok") is True
    )
    return {
        "probe": "probe1-exhaustion-scenarios",
        "unit_id": UNIT,
        "pass": protocol_ok,
        "disk_full": disk,
        "unconstrained_control": control,
        "quota": quota,
        "commit": commit,
        "negative_control": nc,
        "present_modules": dict(PRESENT_MODULES),
    }


def run_probe2() -> dict[str, Any]:
    audit = audit_disk_full_postcondition()
    nc = plant_and_detect_truncation()
    control = run_unconstrained_control()
    protocol_ok = (
        nc.get("pass") is True
        and control.get("ok") is True
        and audit.get("all_paths_still_present") is True
        and isinstance(audit.get("integrity"), dict)
    )
    return {
        "probe": "probe2-postcondition-audit",
        "unit_id": UNIT,
        "pass": protocol_ok,
        "audit": audit,
        "negative_control": nc,
        "unconstrained_control": control,
        "computed_not_asserted": True,
        "present_modules": dict(PRESENT_MODULES),
    }


if __name__ == "__main__":
    if "--commit-child" in sys.argv:
        _commit_child()
        raise SystemExit(0)
    raise SystemExit(
        "use probe1_exhaustion_scenarios.py / probe2_postcondition_audit.py"
    )
