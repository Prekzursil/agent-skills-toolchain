#!/usr/bin/env python3
"""ADV-0127 clock-class census and controlled-clock behavioral harness.

Probe 1 classifies production timestamp writes/comparisons/TTL as monotonic,
UTC-aware, or naive-local (file:line). Probe 2 runs live close.py / vuln_ingestion
paths under DST, timezone change, and a backward wall-clock step.

Production platform/plugin/cache.py and platform/coordination/leases.py are
absent on this worktree; those targets are NOT-CHECKED rather than invented.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0127"
OUT_REL = "command-center/adversarial/ADV-0127-clock-skew-timezone-dst-effects.json"
SCHEMA_REL = "command-center/p2-wave/probes/ADV-0127/fault-injection-run.schema.json"
CATALOG_SCHEMA_REL = "command-center/schema/fault-injection-run.schema.json"
CC = REPO / "tools" / "command-center"
MKT = REPO / "tools" / "marketplace"
NAIVE_ISO = "2026-03-08T01:30:00"
AWARE_ISO = "2026-03-08T01:30:00+00:00"
DST_BEFORE = "2026-03-08T06:59:00+00:00"
DST_AFTER = "2026-03-08T07:00:00+00:00"
BACK_A = "2026-08-24T12:00:00+00:00"
BACK_B = "2026-08-24T10:00:00+00:00"
STABLE_UTC = "2026-08-09T12:00:00+00:00"


def catalog_sentinel() -> str:
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return str(unit.get("completion_sentinel") or "")
    raise RuntimeError("ADV-0127 missing from WORK-UNIT-CATALOG.json")


def _ensure_imports() -> tuple[Any, Any]:
    if str(CC) not in sys.path:
        sys.path.insert(0, str(CC))
    if str(MKT) not in sys.path:
        sys.path.insert(0, str(MKT))
    import close  # noqa: E402
    import vuln_ingestion as vi  # noqa: E402

    return close, vi


def _qual(node: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _src(src: str, node: ast.AST) -> str:
    try:
        text = ast.get_source_segment(src, node) or ""
    except (TypeError, ValueError):
        text = ""
    return " ".join(text.split())[:160]


def _looks_utc(arg: ast.AST) -> bool:
    q = _qual(arg) or ""
    return q.endswith("timezone.utc") or q.endswith("UTC") or q.endswith("datetime.UTC")


def classify_call(qual: str, node: ast.Call) -> tuple[str, str] | None:
    name = qual.split(".")[-1]
    if name == "now" and "datetime" in qual:
        utc = any(_looks_utc(a) for a in node.args)
        utc = utc or any(
            (kw.arg in {"tz", "tzinfo"} and kw.value is not None and _looks_utc(kw.value))
            for kw in node.keywords
        )
        return ("utc-aware", "datetime.now(UTC)") if utc else ("naive-local", "datetime.now() without tz")
    if name == "utcnow":
        return "naive-local", "datetime.utcnow (naive)"
    if name == "fromisoformat":
        return "naive-local", "datetime.fromisoformat (tz optional)"
    if name == "monotonic" or name == "monotonic_ns" or name == "perf_counter":
        return "monotonic", qual
    if name == "time" and qual.endswith("time.time"):
        return "naive-local", "time.time (non-monotonic wall epoch)"
    if name == "getmtime":
        return "naive-local", "os.path.getmtime"
    if name == "sleep":
        return "monotonic", "time.sleep delay (not a wall-clock compare)"
    return None


def census_file(path: Path, rel: str) -> list[dict[str, Any]]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [
            {
                "path": rel,
                "line": 1,
                "clock_class": "naive-local",
                "detail": "unparseable",
                "snippet": "",
            }
        ]
    rows: list[dict[str, Any]] = []

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            qual = _qual(node.func)
            if qual:
                hit = classify_call(qual, node)
                if hit:
                    clock_class, detail = hit
                    rows.append(
                        {
                            "path": rel,
                            "line": int(node.lineno),
                            "clock_class": clock_class,
                            "detail": detail,
                            "snippet": _src(src, node),
                        }
                    )
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr == "st_mtime":
                rows.append(
                    {
                        "path": rel,
                        "line": int(node.lineno),
                        "clock_class": "naive-local",
                        "detail": "stat.st_mtime",
                        "snippet": _src(src, node),
                    }
                )
            if node.attr == "astimezone":
                rows.append(
                    {
                        "path": rel,
                        "line": int(node.lineno),
                        "clock_class": "naive-local",
                        "detail": "datetime.astimezone (naive uses local TZ)",
                        "snippet": _src(src, node),
                    }
                )
            self.generic_visit(node)

    V().visit(tree)
    return rows


def production_census() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    root = REPO / "tools"
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if "/tests/" in f"/{rel}/" or path.name.startswith("test_"):
            continue
        if "__pycache__" in path.parts:
            continue
        rows.extend(census_file(path, rel))
    rows.sort(key=lambda r: (r["path"], r["line"], r["clock_class"], r["detail"], r["snippet"]))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["clock_class"]] = counts.get(row["clock_class"], 0) + 1
    absent = {
        "platform/plugin/cache.py": (REPO / "platform/plugin/cache.py").is_file(),
        "platform/coordination/leases.py": (REPO / "platform/coordination/leases.py").is_file(),
        "ci/harness/ledger.py": (REPO / "ci/harness/ledger.py").is_file(),
        "ci/harness/prebuild_recall/prebuild_recall.py": (
            REPO / "ci/harness/prebuild_recall/prebuild_recall.py"
        ).is_file(),
    }
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "probe": "probe1-static-clock-class-census",
        "unit_id": UNIT,
        "root": "tools/",
        "n_rows": len(rows),
        "counts": counts,
        "rows": rows,
        "fingerprint_sha256": hashlib.sha256(raw).hexdigest(),
        "naive_local_present": any(r["clock_class"] == "naive-local" for r in rows),
        "utc_aware_present": any(r["clock_class"] == "utc-aware" for r in rows),
        "monotonic_present": any(r["clock_class"] == "monotonic" for r in rows),
        "close_fromisoformat": any(
            r["path"] == "tools/command-center/close.py" and "fromisoformat" in r["detail"]
            for r in rows
        ),
        "production_modules_present": absent,
        "anchors": [
            r
            for r in rows
            if r["path"]
            in {
                "tools/command-center/close.py",
                "tools/marketplace/vuln_ingestion.py",
            }
        ],
    }


class _TzGuard:
    def __init__(self) -> None:
        self._orig = os.environ.get("TZ")

    def set(self, tz: str) -> None:
        os.environ["TZ"] = tz
        time.tzset()

    def restore(self) -> None:
        if self._orig is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._orig
        time.tzset()


def _stamp_under_tz(close: Any, iso: str, tz: str, guard: _TzGuard) -> str:
    guard.set(tz)
    return close._stamp(close._now(iso))


def tz_shift_detector(close: Any, iso: str) -> dict[str, Any]:
    """Both-states detector: naive ISO stamps move when TZ changes; aware ISO does not."""
    guard = _TzGuard()
    try:
        utc = _stamp_under_tz(close, iso, "UTC", guard)
        ny = _stamp_under_tz(close, iso, "America/New_York", guard)
    finally:
        guard.restore()
    fired = utc != ny
    return {
        "iso": iso,
        "stamp_utc_tz": utc,
        "stamp_ny_tz": ny,
        "fired": fired,
        "hours_delta": None
        if not fired
        else (
            datetime.fromisoformat(ny) - datetime.fromisoformat(utc)
        ).total_seconds()
        / 3600.0,
    }


def behavioral() -> dict[str, Any]:
    close, vi = _ensure_imports()
    guard = _TzGuard()
    tmp: Path | None = None
    try:
        naive_bad = tz_shift_detector(close, NAIVE_ISO)
        aware_good = tz_shift_detector(close, AWARE_ISO)
        guard.set("UTC")
        dst_a = close._stamp(close._now(DST_BEFORE))
        dst_b = close._stamp(close._now(DST_AFTER))
        dst_order_ok = dst_a < dst_b
        back_a = close._stamp(close._now(BACK_A))
        back_b = close._stamp(close._now(BACK_B))
        tmp = Path(tempfile.mkdtemp(prefix="adv0127-events-"))
        events_path = tmp / "EVENTS.jsonl"
        close.append_event(
            {"seq": 1, "ts": close._stamp(close._now(BACK_A)), "kind": "first"},
            events_path,
        )
        close.append_event(
            {"seq": 2, "ts": close._stamp(close._now(BACK_B)), "kind": "second"},
            events_path,
        )
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        append_seq = [e["seq"] for e in events]
        sorted_seq = [e["seq"] for e in sorted(events, key=lambda item: str(item.get("ts") or ""))]
        backward_reorders = append_seq != sorted_seq
        stable_now = close._now(STABLE_UTC)
        defer_until = close._stamp(stable_now + timedelta(days=14))
        stable_ok = (
            stable_now.tzinfo is not None
            and close._stamp(stable_now) == "2026-08-09T12:00:00+00:00"
            and defer_until.startswith("2026-08-23T12:00:00")
        )
        default_utc = close._now().tzinfo is not None
        parse_naive = vi.parse_iso_z("2026-03-08T01:30:00")
        parse_z = vi.parse_iso_z("2026-03-08T01:30:00Z")
        guard.set("America/New_York")
        iso_z_naive_ny = vi.iso_z(datetime(2026, 3, 8, 1, 30, 0))
        guard.set("UTC")
        iso_z_naive_utc = vi.iso_z(datetime(2026, 3, 8, 1, 30, 0))
        delays: list[float] = []

        def boom() -> None:
            raise OSError("adv0127-retry")

        try:
            vi.with_retry(boom, max_attempts=3, rng=random.Random(0), sleep=delays.append)
            retry_exhausted = False
        except vi.SourceUnreachable:
            retry_exhausted = True
        sys.path.insert(0, str(CC))
        import catalog as cat  # noqa: E402

        deferred = {
            "disposition": None,
            "defer": {"until": defer_until, "reason": "adv0127"},
        }
        lease_never_expires = cat.is_open(deferred) is True
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        mtime_demo = _mtime_ttl_fixture()
    finally:
        guard.restore()
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    distinction = {
        "utc_storage_preserves_dst_order": dst_order_ok,
        "utc_storage_preserves_backward_step_order": not backward_reorders,
        "only_one_handled_by_utc_storage_alone": bool(dst_order_ok and backward_reorders),
        "handled_by_utc_alone": "dst-transition" if dst_order_ok else None,
        "not_handled_by_utc_alone": "backward-clock-step" if backward_reorders else None,
    }
    detector_ok = bool(naive_bad["fired"] and not aware_good["fired"])
    return {
        "probe": "probe2-behavioral-clock-scenarios",
        "unit_id": UNIT,
        "stable_utc_control": {
            "ok": bool(stable_ok and default_utc),
            "default_now_tzinfo_present": default_utc,
            "defer_until": defer_until,
            "stable_stamp": close._stamp(stable_now),
        },
        "timezone_change": {
            "naive": naive_bad,
            "aware": aware_good,
            "defect": bool(naive_bad["fired"]),
        },
        "dst_transition": {
            "before": dst_a,
            "after": dst_b,
            "utc_order_preserved": dst_order_ok,
            "naive_gap_stamp_ny": None,
        },
        "backward_clock_step": {
            "append_seq": append_seq,
            "sort_by_ts_seq": sorted_seq,
            "reorders": backward_reorders,
            "stamps": [back_a, back_b],
        },
        "dst_vs_backward_distinction": distinction,
        "freshness": {
            "parse_iso_z_naive_tzinfo": None if parse_naive.tzinfo is None else str(parse_naive.tzinfo),
            "parse_iso_z_zulu_aware": parse_z.tzinfo is not None,
            "iso_z_naive_ny": iso_z_naive_ny,
            "iso_z_naive_utc": iso_z_naive_utc,
            "iso_z_naive_shifts_with_tz": iso_z_naive_ny != iso_z_naive_utc,
        },
        "lease_defer": {
            "is_open_ignores_until": lease_never_expires,
            "until": defer_until,
        },
        "retry_backoff": {
            "clock_independent": True,
            "exhausted": retry_exhausted,
            "recorded_delays": delays,
            "uses_sleep_not_wall_compare": True,
        },
        "powershell": {
            "present": bool(pwsh),
            "binary": pwsh,
        },
        "mtime_ttl_fixture_not_production": mtime_demo,
        "negative_control": {
            "id": "NC-CLOCK-SCENARIO-DETECTOR-BOTH-STATES",
            "fired_on_bad_state": bool(naive_bad["fired"]),
            "silent_on_good_state": not bool(aware_good["fired"]),
            "ok": detector_ok,
        },
    }


def _mtime_ttl_fixture() -> dict[str, Any]:
    """Class demo only: mtime TTL expires early on forward jump and never on backward jump."""
    tmp = Path(tempfile.mkdtemp(prefix="adv0127-mtime-"))
    try:
        entry = tmp / "entry"
        entry.write_text("x", encoding="utf-8")
        now = 1_700_000_000.0
        os.utime(entry, (now, now))
        mtime = entry.stat().st_mtime
        ttl = 60.0
        expired_stable = (now - mtime) > ttl
        expired_forward = ((now + 120.0) - mtime) > ttl
        expired_backward = ((now - 120.0) - mtime) > ttl
        return {
            "production_cache_module": False,
            "premature_on_forward_jump": expired_forward and not expired_stable,
            "never_expires_on_backward_step": (not expired_backward) and not expired_stable,
            "stable_not_expired": not expired_stable,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fingerprint(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_artifact() -> tuple[str, dict[str, Any]]:
    path = REPO / OUT_REL
    text = path.read_text(encoding="utf-8")
    return text, json.loads(text)


def schema_errors(doc: dict[str, Any]) -> list[str]:
    import jsonschema

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errs]


def garbage_rejected() -> list[int]:
    import jsonschema

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    counts = []
    for garbage in (
        {},
        {"state": "SUCCESS", "passing_tests": 999},
        {"blob": "x" * 400, "state": "BLOCKED"},
    ):
        counts.append(sum(1 for _ in validator.iter_errors(garbage)))
    return counts
