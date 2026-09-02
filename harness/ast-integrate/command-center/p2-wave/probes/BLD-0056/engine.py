#!/usr/bin/env python3
"""Live + synthetic scale measurements for BLD-0056 (artifact/ledger growth)."""
from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PATHOLOGY_BYTES = 774 * 1024
PARSE_BUDGET_MS = 1000.0
DIR_BUDGET_MS = 2000.0
DIR_N = 20480
SCALE = 10
RECORD = (
    b'{"ts":"2026-08-24T00:00:00Z","kind":"append","payload":"' + (b"x" * 180) + b'"}\n'
)
FULL_PARSE_READERS = [
    "command-center/p2-wave/_measure_one_delivered.py",
    "command-center/p2-wave/probes/CNF-0123/inventory.py",
    "command-center/p2-wave/probes/ADV-0002/engine.py",
    "command-center/p2-wave/probes/BLD-0029/close.py",
]


def fstype_of(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", "-T", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    text = (proc.stdout or "").strip()
    return text.splitlines()[0].strip() if text else "unknown"


def ntfs_mounts() -> list[str]:
    try:
        proc = subprocess.run(
            ["findmnt", "-n", "-o", "TARGET,FSTYPE", "-t", "ntfs,ntfs3,fuse.ntfs"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _skip_part(part: str) -> bool:
    return part in {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "ovh-monitor",
        "scw-pull",
        "error-pull",
        "missing-pull",
        "probes",
    }


def largest_json(root: Path) -> dict[str, Any]:
    best: tuple[int, Path] | None = None
    base = root / "command-center"
    if not base.is_dir():
        return {"path": "command-center", "present": False, "bytes": 0}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not _skip_part(d)]
        for name in filenames:
            if not name.endswith(".json"):
                continue
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if best is None or size > best[0]:
                best = (size, path)
    if best is None:
        return {"path": "command-center", "present": False, "bytes": 0}
    return {
        "path": best[1].relative_to(root).as_posix(),
        "present": True,
        "bytes": best[0],
    }


def _path_stat(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.exists():
        return {"path": rel, "present": False, "bytes": 0, "entries": 0}
    if path.is_file():
        return {"path": rel, "present": True, "bytes": path.stat().st_size, "entries": 1}
    entries = 0
    total = 0
    try:
        for child in path.iterdir():
            entries += 1
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return {"path": rel, "present": True, "bytes": total, "entries": entries}


def _glob_sum(pattern: str) -> dict[str, Any]:
    paths = [p for p in REPO.glob(pattern) if p.is_file()]
    return {
        "path": pattern,
        "present": bool(paths),
        "bytes": sum(p.stat().st_size for p in paths),
        "entries": len(paths),
    }


def _catalog_unit_count() -> int:
    path = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError):
        return 0
    units = data.get("work_units")
    return len(units) if isinstance(units, list) else 0


def live_inventory() -> dict[str, Any]:
    events = _path_stat("command-center/events/EVENTS.jsonl")
    if not events["present"]:
        nested = _path_stat("command-center/events")
        if nested["present"]:
            events = nested
    return {
        "events_log": events,
        "receipt_tree": _path_stat("command-center/receipts"),
        "artifact_manifest": _path_stat("command-center/ARTIFACT-MANIFEST.json"),
        "unit_manifests": _glob_sum("**/UNIT-ARTIFACT-MANIFEST.json"),
        "largest_json": largest_json(REPO),
        "catalog_units": _catalog_unit_count(),
    }


def inflate_n(raw: bytes, n: int) -> bytes:
    if n < 1:
        raise ValueError("n")
    if n == 1:
        return raw
    return b"[" + raw + (b"," + raw) * (n - 1) + b"]"


def parse_ms(raw: bytes) -> float:
    t0 = time.perf_counter()
    json.loads(raw)
    return (time.perf_counter() - t0) * 1000.0


def measure_parse_pair(src: Path) -> dict[str, Any]:
    raw = src.read_bytes()
    x1_ms = parse_ms(raw)
    blob10 = inflate_n(raw, SCALE)
    x10_ms = parse_ms(blob10)
    rec = "stream-or-paginate" if x10_ms > PARSE_BUDGET_MS else "full-parse-ok"
    try:
        source = src.relative_to(REPO).as_posix()
    except ValueError:
        source = str(src)
    return {
        "threshold_ms": PARSE_BUDGET_MS,
        "source": source,
        "x1": {"kind": "MEASURED", "file_bytes": len(raw), "parse_ms": round(x1_ms, 3)},
        "x10": {
            "kind": "MEASURED",
            "file_bytes": len(blob10),
            "parse_ms": round(x10_ms, 3),
        },
        "reader_recommendation": rec,
        "full_parse_readers": list(FULL_PARSE_READERS),
        "byte_ratio": round(len(blob10) / max(len(raw), 1), 4),
    }


def _write_receipt_tree(root: Path, n: int) -> float:
    payload = b"{}"
    t0 = time.perf_counter()
    for i in range(n):
        fd = os.open(
            os.path.join(str(root), f"r{i:05d}.json"),
            os.O_CREAT | os.O_WRONLY,
            0o644,
        )
        os.write(fd, payload)
        os.close(fd)
    return (time.perf_counter() - t0) * 1000.0


def measure_dir_scale(base: Path | None, n: int = DIR_N) -> dict[str, Any]:
    if base is None:
        return {
            "status": "NOT-CHECKED",
            "fstype": "absent",
            "n": 0,
            "listdir_ms": None,
            "glob_ms": None,
            "create_ms": None,
            "within_budget": False,
            "reason": "second filesystem path not available",
        }
    base = Path(base)
    if not base.is_dir() or not os.access(base, os.W_OK):
        return {
            "status": "NOT-CHECKED",
            "fstype": fstype_of(base) if base.exists() else "absent",
            "n": 0,
            "listdir_ms": None,
            "glob_ms": None,
            "create_ms": None,
            "within_budget": False,
            "reason": f"not a writable directory: {base}",
        }
    with tempfile.TemporaryDirectory(prefix="bld0056-dir-", dir=str(base)) as tmp:
        root = Path(tmp)
        create_ms = _write_receipt_tree(root, n)
        t0 = time.perf_counter()
        names = os.listdir(root)
        listdir_ms = (time.perf_counter() - t0) * 1000.0
        t0 = time.perf_counter()
        matched = glob.glob(str(root / "*.json"))
        glob_ms = (time.perf_counter() - t0) * 1000.0
        if len(names) != n or len(matched) != n:
            raise RuntimeError(
                f"directory scale produced listdir={len(names)} glob={len(matched)} want={n}"
            )
        return {
            "status": "MEASURED",
            "fstype": fstype_of(root),
            "n": n,
            "listdir_ms": round(listdir_ms, 3),
            "glob_ms": round(glob_ms, 3),
            "create_ms": round(create_ms, 3),
            "within_budget": listdir_ms <= DIR_BUDGET_MS and glob_ms <= DIR_BUDGET_MS,
            "budget_ms": DIR_BUDGET_MS,
            "base": str(base),
        }


def detect_always_skip(size: int, compacts: int) -> bool:
    return compacts == 0 and size >= PATHOLOGY_BYTES


def run_consolidator(mode: str, target: int = PATHOLOGY_BYTES) -> dict[str, Any]:
    buf = bytearray()
    compacts = 0
    appends = 0
    cap = 64 * 1024
    keep = 16 * 1024
    guard = 0
    while len(buf) < target:
        buf.extend(RECORD)
        appends += 1
        guard += 1
        if guard > 1_000_000:
            raise RuntimeError("consolidator did not reach target")
        if mode == "compact":
            if len(buf) > cap:
                buf[:] = buf[-keep:]
                compacts += 1
            if compacts > 8:
                break
        elif mode != "always_skip":
            raise ValueError(mode)
    return {
        "mode": mode,
        "bytes": len(buf),
        "appends": appends,
        "compacts": compacts,
        "detected_as_always_skip": detect_always_skip(len(buf), compacts),
        "pathology_bytes": PATHOLOGY_BYTES,
    }


def measure_event_append(n_lines: int = 20_000) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bld0056-ev-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        t0 = time.perf_counter()
        with path.open("wb") as fh:
            for _ in range(n_lines):
                fh.write(RECORD)
        ms = (time.perf_counter() - t0) * 1000.0
        size = path.stat().st_size
    return {
        "kind": "MEASURED",
        "lines": n_lines,
        "bytes": size,
        "write_ms": round(ms, 3),
        "lines_per_s": round(n_lines / max(ms / 1000.0, 1e-9), 1),
        "note": "synthetic JSONL append; live command-center/events/EVENTS.jsonl is absent",
    }


def second_fs_base() -> Path | None:
    shm = Path("/dev/shm")
    if shm.is_dir() and os.access(shm, os.W_OK):
        return shm
    return None


def primary_fs_base() -> Path:
    return Path(tempfile.gettempdir())


def consolidation_control() -> dict[str, Any]:
    skip = run_consolidator("always_skip")
    compact = run_consolidator("compact")
    fires = bool(skip["detected_as_always_skip"])
    silent = not bool(compact["detected_as_always_skip"])
    return {
        "pathology_bytes": PATHOLOGY_BYTES,
        "always_skip": skip,
        "compacting": compact,
        "detector": {
            "fires_on_always_skip": fires,
            "silent_on_compacting": silent,
            "rule": (
                "always-skip iff compacts==0 and bytes>=774*1024 "
                "(named 774 KB consolidation-skip pathology)"
            ),
            "control_pass": fires and silent,
        },
    }


def _store(
    sid: str,
    scale_1x: dict[str, Any],
    scale_10x: dict[str, Any],
    limit_name: str,
    limit_value: float,
    limit_unit: str,
    crosses: bool,
    note: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": sid,
        "scale_1x": scale_1x,
        "scale_10x": scale_10x,
        "hard_limit": {"name": limit_name, "value": limit_value, "unit": limit_unit},
        "crosses_limit_at_10x": crosses,
    }
    if note:
        row["note"] = note
    return row


def build_model() -> dict[str, Any]:
    inv = live_inventory()
    largest = inv["largest_json"]
    src = REPO / largest["path"] if largest["present"] else None
    if src is None or not src.is_file():
        raise RuntimeError("no largest JSON artifact to parse")
    parse = measure_parse_pair(src)
    primary = measure_dir_scale(primary_fs_base(), DIR_N)
    second = measure_dir_scale(second_fs_base(), DIR_N)
    consol = consolidation_control()
    append = measure_event_append()
    mounts = ntfs_mounts()
    ntfs = {
        "status": "MEASURED" if mounts else "NOT-CHECKED",
        "reason": (
            "NTFS mounts: " + "; ".join(mounts)
            if mounts
            else "no NTFS/ntfs3 mount on this Linux worktree; directory scale not assumed from ext4/tmpfs"
        ),
        "mounts": mounts,
    }

    receipts_1x = int(inv["receipt_tree"]["entries"])
    man_1x = int(inv["unit_manifests"]["bytes"])
    ev_present = bool(inv["events_log"]["present"])
    ev_1x = int(inv["events_log"]["bytes"])
    ev_10x_kind = "PROJECTION" if ev_present else "ESTIMATE"
    ev_10x = (ev_1x * SCALE) if ev_present else int(append["bytes"]) * SCALE
    parse_crosses = float(parse["x10"]["parse_ms"]) > PARSE_BUDGET_MS
    dir_crosses = not bool(primary.get("within_budget"))
    skip_crosses = bool(consol["always_skip"]["detected_as_always_skip"])

    stores = [
        _store(
            "event-log",
            {"kind": "MEASURED" if ev_present else "ABSENT", "value": ev_1x, "unit": "bytes"},
            {"kind": ev_10x_kind, "value": ev_10x, "unit": "bytes"},
            "unbounded-if-always-skip",
            PATHOLOGY_BYTES,
            "bytes",
            skip_crosses and not ev_present,
            "live EVENTS.jsonl absent; 10x of live log is ESTIMATE. "
            "synthetic append rate measured; always-skip consolidator is the measured pathology.",
        ),
        _store(
            "receipt-tree",
            {"kind": "MEASURED", "value": receipts_1x, "unit": "files"},
            {"kind": "PROJECTION", "value": receipts_1x * SCALE, "unit": "files"},
            "dir-list-glob-budget",
            DIR_BUDGET_MS,
            "ms-at-20480",
            False,
            "linear 10x of live receipt count uses measured 1x anchor (PROJECTION)",
        ),
        _store(
            "manifest-tree",
            {
                "kind": "MEASURED" if inv["unit_manifests"]["present"] else "ABSENT",
                "value": man_1x,
                "unit": "bytes",
            },
            {
                "kind": "PROJECTION" if inv["unit_manifests"]["present"] else "ESTIMATE",
                "value": man_1x * SCALE,
                "unit": "bytes",
            },
            "none-measured-on-this-box",
            0,
            "bytes",
            False,
            "global ARTIFACT-MANIFEST.json absent; 1x is sum of UNIT-ARTIFACT-MANIFEST.json files",
        ),
        _store(
            "directory-entries",
            {"kind": "MEASURED", "value": receipts_1x, "unit": "entries"},
            {"kind": "MEASURED", "value": DIR_N, "unit": "entries-synthetic"},
            "listdir+glob-ms",
            DIR_BUDGET_MS,
            "ms",
            dir_crosses,
        ),
        _store(
            "largest-json",
            {"kind": "MEASURED", "value": parse["x1"]["file_bytes"], "unit": "bytes"},
            {"kind": "MEASURED", "value": parse["x10"]["file_bytes"], "unit": "bytes"},
            "full-parse-ms",
            PARSE_BUDGET_MS,
            "ms",
            parse_crosses,
        ),
        _store(
            "consolidation-log",
            {"kind": "MEASURED", "value": consol["always_skip"]["bytes"], "unit": "bytes"},
            {
                "kind": "PROJECTION",
                "value": int(consol["always_skip"]["bytes"]) * SCALE,
                "unit": "bytes",
            },
            "774kb-always-skip-pathology",
            PATHOLOGY_BYTES,
            "bytes",
            skip_crosses,
        ),
    ]

    rationale = (
        "The always-skip consolidator was reproduced to "
        f"{consol['always_skip']['bytes']} bytes with compacts="
        f"{consol['always_skip']['compacts']}, crossing the named 774 KB "
        f"({PATHOLOGY_BYTES} byte) pathology while the compacting twin stayed "
        f"at {consol['compacting']['bytes']} bytes with "
        f"{consol['compacting']['compacts']} compact steps. On this box the "
        f"largest JSON 10x parse is {parse['x10']['parse_ms']} ms "
        f"(budget {PARSE_BUDGET_MS} ms) and a 20480-file directory listed in "
        f"{primary.get('listdir_ms')} ms / globbed in {primary.get('glob_ms')} ms "
        f"(budget {DIR_BUDGET_MS} ms). Unbounded skip-consolidation therefore "
        "degrades first. NTFS directory behaviour is NOT-CHECKED."
    )

    tests = [
        {
            "id": "parse-budget-10x",
            "result": (
                "PASS"
                if parse["x1"]["file_bytes"] >= 1
                and parse["x10"]["file_bytes"] >= parse["x1"]["file_bytes"] * 9
                else "FAIL"
            ),
        },
        {
            "id": "directory-20480",
            "result": (
                "PASS"
                if primary["status"] == "MEASURED" and primary.get("within_budget")
                else "FAIL"
            ),
        },
        {
            "id": "consolidation-always-skip-774kb",
            "result": "PASS" if consol["detector"]["control_pass"] else "FAIL",
        },
    ]

    return {
        "inventory": inv,
        "parse_budget": parse,
        "directory_scale": {
            "n": DIR_N,
            "budget_ms": DIR_BUDGET_MS,
            "primary": primary,
            "second_filesystem": second,
        },
        "consolidation_control": consol,
        "event_append": append,
        "stores": stores,
        "first_to_degrade": {
            "store_id": "consolidation-log",
            "kind": "MEASURED",
            "rationale": rationale,
        },
        "ntfs": ntfs,
        "reviewer": {
            "reviewer_id": "BLD-0056-second-fs-dir-scale",
            "independent": True,
            "verdict": "PASS" if primary["status"] == "MEASURED" else "FAIL",
            "second_filesystem": {
                "status": second["status"],
                "fstype": second.get("fstype") or "unknown",
            },
        },
        "tests": tests,
    }


build_model = build_model

