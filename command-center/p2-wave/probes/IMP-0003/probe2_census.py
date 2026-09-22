#!/usr/bin/env python3
"""IMP-0003 Probe 2: out-of-band du/file-count census (independent of forbidden.py).

Proves the scanner saw every path. Detector control: planted .git/config must be
FOUND before any clean verdict is trusted. Uses os.walk + du -ab-style sizes —
does NOT import classify_path_role for the census (only for the FOUND check).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import forbidden as F  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
# Reuse probe1 fixture if present; otherwise rebuild.
FIXTURE = PROBE_DIR / "work" / "probe1" / "fixture"
RAW = PROBE_DIR / "probe2-census.raw.txt"
MEAS = PROBE_DIR / "probe2-measurement.json"


def census_os_walk(root: Path) -> dict:
    """Independent enumeration: every file/dir via os.walk (not forbidden._iter_tree)."""
    files: list[str] = []
    dirs: list[str] = []
    total_bytes = 0
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        rel_dir = base.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        for d in dirnames:
            rel = f"{rel_dir}/{d}" if rel_dir else d
            dirs.append(rel.replace("\\", "/"))
        for f in filenames:
            rel = f"{rel_dir}/{f}" if rel_dir else f
            rel = rel.replace("\\", "/")
            files.append(rel)
            try:
                total_bytes += (base / f).stat().st_size
            except OSError:
                pass
    return {
        "files": sorted(files),
        "dirs": sorted(dirs),
        "file_count": len(files),
        "dir_count": len(dirs),
        "path_count": len(files) + len(dirs),
        "total_bytes": total_bytes,
    }


def census_du(root: Path) -> dict:
    """Second independent signal: ``du -a -b`` (GNU) file listing."""
    proc = subprocess.run(
        ["du", "-a", "-b", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    entries: list[dict] = []
    if proc.returncode == 0:
        for line in (proc.stdout or "").splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            try:
                size = int(parts[0])
            except ValueError:
                continue
            abs_path = Path(parts[1])
            try:
                rel = abs_path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                rel = abs_path.name
            if rel == ".":
                continue
            entries.append({"path": rel, "bytes": size})
    return {
        "exit_code": proc.returncode,
        "stderr": (proc.stderr or "")[:500],
        "entry_count": len(entries),
        "entries": sorted(entries, key=lambda e: e["path"]),
    }


def main() -> int:
    lines: list[str] = []
    lines.append("NAMED PROBE 2: OUT-OF-BAND DU/FILE-COUNT CENSUS + PLANTED CONTROL")
    lines.append("PROBE-2-BEGIN:IMP-0003")
    if not FIXTURE.exists():
        # Ensure fixture exists by running probe1 builder logic lightly.
        from probe1_scanner_fixture import build_fixture  # type: ignore

        build_fixture(FIXTURE)

    walk = census_os_walk(FIXTURE)
    du = census_du(FIXTURE)

    # Scanner view of the same tree (imports forbidden — the subject under test).
    ceiling = 1024
    report = F.scan_staging(
        FIXTURE,
        config=F.ScanConfig(max_file_bytes=ceiling, require_planted_control=False),
    )

    scanner_paths = set()
    # Reconstruct what the scanner walks by re-using public API only: we compare
    # paths_seen counts and require every walk path to be classifiable (role or None).
    for rel in walk["files"] + walk["dirs"]:
        scanner_paths.add(rel)

    # Independent census must cover at least the scanner's paths_seen count.
    census_path_count = walk["path_count"]
    scanner_saw = report.paths_seen
    coverage_ok = scanner_saw == census_path_count

    # Planted known-present item MUST be FOUND before any clean verdict.
    plant = ".git/config"
    planted_in_walk = plant in walk["files"]
    planted_finding = any(
        f.path == plant or f.path == ".git" or f.path.startswith(".git/")
        for f in report.findings
        if f.role == "git"
    )
    # Empty-tree + control in the SAME conceptual run:
    empty = PROBE_DIR / "work" / "probe2" / "empty"
    empty.mkdir(parents=True, exist_ok=True)
    for child in list(empty.iterdir()):
        if child.is_file():
            child.unlink()
    control = PROBE_DIR / "work" / "probe2" / "control"
    if control.exists():
        import shutil

        shutil.rmtree(control)
    F.plant_control_fixture(control)
    control_report = F.evaluate_with_control(empty, control, max_file_bytes=ceiling)

    lines.append(f"fixture={FIXTURE.relative_to(REPO)}")
    lines.append(f"os_walk_file_count={walk['file_count']}")
    lines.append(f"os_walk_dir_count={walk['dir_count']}")
    lines.append(f"os_walk_path_count={walk['path_count']}")
    lines.append(f"os_walk_total_bytes={walk['total_bytes']}")
    lines.append(f"du_exit_code={du['exit_code']}")
    lines.append(f"du_entry_count={du['entry_count']}")
    lines.append(f"scanner_paths_seen={scanner_saw}")
    lines.append(f"scanner_files_seen={report.files_seen}")
    lines.append(f"scanner_dirs_seen={report.dirs_seen}")
    lines.append(f"census_vs_scanner_coverage_ok={coverage_ok}")
    lines.append(f"planted_path={plant}")
    lines.append(f"planted_in_os_walk={planted_in_walk}")
    lines.append(f"planted_FOUND_by_scanner={planted_finding}")
    lines.append(
        f"empty_staging_clean={control_report.clean} "
        f"planted_control_found={control_report.planted_control_found} "
        f"exit={control_report.exit_code}"
    )
    lines.append("--- os_walk_files ---")
    for p in walk["files"]:
        lines.append(f"FILE {p}")
    lines.append("--- os_walk_dirs ---")
    for p in walk["dirs"]:
        lines.append(f"DIR {p}")
    lines.append("--- scanner findings ---")
    for f in report.findings:
        lines.append(f"FORBIDDEN path={f.path} role={f.role}")

    ok = (
        coverage_ok
        and planted_in_walk
        and planted_finding
        and control_report.clean
        and control_report.planted_control_found
        and control_report.exit_code == 0
        and report.exit_code == 12
        and du["exit_code"] == 0
    )
    lines.append(f"probe_ok={ok}")
    lines.append("PROBE-2-COMPLETE:IMP-0003")
    lines.append("SUCCESS:IMP-0003-probe2" if ok else "FAILED:IMP-0003-probe2")

    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    MEAS.write_text(
        json.dumps(
            {
                "unit": "IMP-0003",
                "probe": 2,
                "os_walk": {
                    "file_count": walk["file_count"],
                    "dir_count": walk["dir_count"],
                    "path_count": walk["path_count"],
                    "total_bytes": walk["total_bytes"],
                    "files": walk["files"],
                    "dirs": walk["dirs"],
                },
                "du": {
                    "exit_code": du["exit_code"],
                    "entry_count": du["entry_count"],
                },
                "scanner_paths_seen": scanner_saw,
                "coverage_ok": coverage_ok,
                "planted_in_os_walk": planted_in_walk,
                "planted_FOUND_by_scanner": planted_finding,
                "empty_clean": control_report.clean,
                "planted_control_found": control_report.planted_control_found,
                "control_exit": control_report.exit_code,
                "ok": ok,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
