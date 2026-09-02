"""Isolated SYN-0019 sandbox: clean manifest plus planted-defect mutations."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
SYN = REPO / "tools" / "synthesis"
for p in (str(CC), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import manifest_gate as gate  # noqa: E402
from synthesis.report_writer import write_completion_report  # noqa: E402

FIXTURE_SCHEMA = HERE / "fixtures" / "entry.schema.json"
WINDOW = 30
MIN_BYTES = 16
REPORT_NAME = "completion-report.json"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def populate(root: Path) -> Path:
    """Write a three-entry manifest whose files exist, parse, and match hashes."""
    shutil.copy(FIXTURE_SCHEMA, root / "entry.schema.json")
    goods = {
        "good.json": {"kind": "artifact", "id": "alpha"},
        "other.json": {"kind": "artifact", "id": "beta"},
    }
    entries = []
    for name, payload in goods.items():
        raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (root / name).write_bytes(raw)
        digest, size = gate.lf_digest(raw)
        entries.append(
            {
                "path": name,
                "sha256": digest,
                "bytes": size,
                "schema": "entry.schema.json",
                "min_bytes": MIN_BYTES,
            }
        )
    note = "# fixture note\n\nThis is a non-JSON contracted sibling.\n"
    (root / "note.md").write_text(note, encoding="utf-8", newline="\n")
    digest, size = gate.lf_digest(note.encode("utf-8"))
    entries.append(
        {
            "path": "note.md",
            "sha256": digest,
            "bytes": size,
            "min_bytes": 8,
        }
    )
    manifest = {
        "schema_version": 1,
        "contract": "SYN-0019-fixture",
        "artifacts": entries,
    }
    path = root / "ARTIFACT-MANIFEST.json"
    _write(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


@contextmanager
def sandbox(prefix: str = "syn0019-") -> Iterator[Path]:
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        populate(tmp)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _attempt_write(
    root: Path,
    verification: dict[str, Any],
    *,
    write_time: datetime | None = None,
    window: int = WINDOW,
) -> dict[str, Any]:
    dest = root / REPORT_NAME
    if dest.exists():
        dest.unlink()
    return write_completion_report(
        dest,
        {
            "report": "SYN-0019-control",
            "verified_at": verification.get("verified_at"),
        },
        verification,
        write_time=write_time,
        freshness_window_seconds=window,
    )


def slim_entries(verification: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in verification.get("entries") or []:
        rows.append(
            {
                "path": item.get("path"),
                "bytes": item.get("bytes"),
                "hash": item.get("hash"),
                "parse_verdict": item.get("parse_verdict"),
                "blocking_conditions": item.get("blocking_conditions") or [],
                "present": item.get("present"),
                "failed_never_skipped": item.get("failed_never_skipped"),
            }
        )
    return rows


def record(
    run_id: str,
    verification: dict[str, Any],
    writer: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": run_id,
        "verdict": writer.get("verdict"),
        "timestamp": writer.get("write_time") or verification.get("verified_at"),
        "verified_at": verification.get("verified_at"),
        "exit_code": writer.get("exit_code"),
        "gate_exit_code": verification.get("exit_code"),
        "wrote": bool(writer.get("wrote")),
        "output_exists": bool(writer.get("output_exists")),
        "blocking_conditions": list(writer.get("blocking_conditions") or [])
        or list(verification.get("blocking_conditions") or []),
        "verification_blocking_conditions": list(
            verification.get("blocking_conditions") or []
        ),
        "wall_clock_gap_seconds": writer.get("wall_clock_gap_seconds"),
        "freshness_window_seconds": writer.get("freshness_window_seconds")
        or verification.get("freshness_window_seconds"),
        "entries": slim_entries(verification),
    }


def run_clean(root: Path, *, window: int = WINDOW) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    verification = gate.verify_manifest(
        root,
        root / "ARTIFACT-MANIFEST.json",
        verified_at=now,
        freshness_window_seconds=window,
        default_min_bytes=MIN_BYTES,
    )
    writer = _attempt_write(root, verification, write_time=now, window=window)
    return record("clean", verification, writer)


def run_deletion(root: Path, *, window: int = WINDOW) -> dict[str, Any]:
    target = root / "good.json"
    target.unlink()
    now = datetime.now(timezone.utc)
    verification = gate.verify_manifest(
        root,
        root / "ARTIFACT-MANIFEST.json",
        verified_at=now,
        freshness_window_seconds=window,
        default_min_bytes=MIN_BYTES,
    )
    writer = _attempt_write(root, verification, write_time=now, window=window)
    rec = record("planted-deletion", verification, writer)
    rec["deleted_path"] = "good.json"
    rec["deleted_still_absent"] = not target.exists()
    return rec


def run_truncation(root: Path, *, window: int = WINDOW) -> dict[str, Any]:
    target = root / "other.json"
    target.write_bytes(b"")
    now = datetime.now(timezone.utc)
    verification = gate.verify_manifest(
        root,
        root / "ARTIFACT-MANIFEST.json",
        verified_at=now,
        freshness_window_seconds=window,
        default_min_bytes=MIN_BYTES,
    )
    writer = _attempt_write(root, verification, write_time=now, window=window)
    rec = record("planted-truncation", verification, writer)
    rec["truncated_path"] = "other.json"
    rec["truncated_bytes"] = target.stat().st_size
    rec["entry_conditions"] = [
        c
        for e in verification.get("entries") or []
        if e.get("path") == "other.json"
        for c in (e.get("blocking_conditions") or [])
    ]
    return rec


def run_staleness(root: Path, *, window: int = WINDOW) -> dict[str, Any]:
    verified_at = datetime.now(timezone.utc)
    verification = gate.verify_manifest(
        root,
        root / "ARTIFACT-MANIFEST.json",
        verified_at=verified_at,
        freshness_window_seconds=window,
        default_min_bytes=MIN_BYTES,
    )
    write_time = verified_at + timedelta(seconds=window + 1)
    writer = _attempt_write(
        root, verification, write_time=write_time, window=window
    )
    rec = record("staleness-control", verification, writer)
    rec["verification_verdict"] = verification.get("verdict")
    rec["verification_exit_code"] = verification.get("exit_code")
    rec["write_time"] = writer.get("write_time")
    return rec


def run_unreadable_not_skipped(root: Path) -> dict[str, Any]:
    """A path that cannot be stat-ed (ENOTDIR) is FAILED in the table, never omitted."""
    blocker = root / "notdir"
    blocker.write_text("file-not-directory\n", encoding="utf-8")
    manifest = json.loads((root / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    phantom = {
        "path": "notdir/nested.json",
        "sha256": "0" * 64,
        "bytes": 32,
        "min_bytes": MIN_BYTES,
    }
    manifest["artifacts"] = list(manifest["artifacts"]) + [phantom]
    verification = gate.verify_manifest(
        root,
        manifest,
        freshness_window_seconds=WINDOW,
        default_min_bytes=MIN_BYTES,
    )
    paths = [e.get("path") for e in verification.get("entries") or []]
    nested = next(
        e
        for e in verification["entries"]
        if e.get("path") == "notdir/nested.json"
    )
    return {
        "path_in_table": "notdir/nested.json" in paths,
        "parse_verdict": nested.get("parse_verdict"),
        "blocking_conditions": nested.get("blocking_conditions"),
        "failed_never_skipped": nested.get("failed_never_skipped") is True,
        "entry_count": verification.get("entry_count"),
        "verdict": verification.get("verdict"),
    }


def reserved_prefix_probe() -> dict[str, Any]:
    sample = Path(r"C:\repo\NUL")
    extended = gate.extended_length_path(sample)
    return {
        "reserved_nul": gate.is_reserved_device_name("NUL"),
        "reserved_nul_txt": gate.is_reserved_device_name("NUL.txt"),
        "reserved_com1": gate.is_reserved_device_name("COM1"),
        "not_reserved": not gate.is_reserved_device_name("good.json"),
        "extended_prefix": str(extended).startswith("\\\\?\\"),
        "extended": str(extended),
        "windows_stat_target": str(
            gate.stat_target(sample, reserved=True, windows=True)
        ).startswith("\\\\?\\"),
        "linux_stat_target_unchanged": str(
            gate.stat_target(Path("/tmp/NUL"), reserved=True, windows=False)
        )
        == "/tmp/NUL",
    }
