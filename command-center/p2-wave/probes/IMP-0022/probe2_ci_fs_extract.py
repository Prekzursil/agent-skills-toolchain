#!/usr/bin/env python3
"""IMP-0022 Probe 2: extract planted archive onto a case-insensitive filesystem.

Catalog signal (2): extract the artifact onto a *real* case-insensitive
filesystem and compare extracted file count to archive entry count. A planted
README.md + readme.md pair must produce a shortfall on CI-FS.

On this Linux/ext4 worker the default filesystem is case-sensitive. Without an
authorized case-insensitive mount (NTFS/APFS/ciopfs/etc.), the probe fails
closed and records the missing substrate — it does not invent a shortfall.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import casefold_paths as cf  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
WORK = PROBE_DIR / "work" / "probe2"
RAW = PROBE_DIR / "probe2-ci-fs-extract.raw.txt"
MEAS = PROBE_DIR / "probe2-measurement.json"

EVIDENCE = (
    "TWO independent signals: (1) casefold-collision count computed over the "
    "payload path set; (2) an actual extraction of the artifact onto a "
    "case-insensitive filesystem, comparing the extracted file count against "
    "the archive entry count — a collision shows up as a shortfall."
)


def main() -> int:
    lines: list[str] = []
    lines.append(
        "NAMED PROBE 2: EXTRACT ONTO CASE-INSENSITIVE FS; COUNT SHORTFALL"
    )
    lines.append("PROBE-2-BEGIN:IMP-0022")
    lines.append("stage=p2-deliver")
    lines.append(f"evidence_requirement_verbatim={EVIDENCE}")
    lines.append(f"host_os_name={'posix' if os.name == 'posix' else os.name}")
    lines.append(f"host_platform={platform.system().lower()}")
    lines.append(f"python_version={platform.python_version()}")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    archive = cf.write_collision_zip(
        [("README.md", b"UPPER-README\n"), ("readme.md", b"lower-readme\n")],
        WORK / "planted-readme-pair.zip",
    )
    lines.append(f"archive={archive.relative_to(REPO)}")
    lines.append("planted_members=['README.md','readme.md']")

    # Set check still fires on the planted pair (shared with probe1 / negative control).
    set_report = cf.find_casefold_collisions(["README.md", "readme.md"])
    lines.append(f"set_check_collision_group_count={set_report.collision_count}")
    lines.append(f"set_check_fired={set_report.collision_count >= 1}")

    # Optional override: IMP0022_CI_FS_ROOT may point at a real CI-FS mount.
    override = os.environ.get("IMP0022_CI_FS_ROOT", "").strip()
    dest_parent = Path(override) if override else (WORK / "extract-parent")
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / "extract"
    if dest.exists():
        shutil.rmtree(dest)

    host_ci = cf.filesystem_is_case_insensitive(dest_parent)
    lines.append(f"IMP0022_CI_FS_ROOT={override or ''}")
    lines.append(f"dest_parent={dest_parent}")
    lines.append(f"dest_parent_case_insensitive={host_ci}")

    shortfall_observed = False
    extract_error: str | None = None
    extract_dict: dict = {}
    try:
        result = cf.extract_and_count(
            archive, dest, require_case_insensitive=True
        )
        extract_dict = result.as_dict()
        shortfall_observed = result.collision_shortfall_observed
        lines.append(f"archive_entry_count={result.archive_entry_count}")
        lines.append(f"extracted_file_count={result.extracted_file_count}")
        lines.append(f"shortfall={result.shortfall}")
        lines.append(
            f"collision_shortfall_observed={result.collision_shortfall_observed}"
        )
    except RuntimeError as exc:
        extract_error = str(exc)
        lines.append(f"extract_error={extract_error}")
        # Diagnostic extraction on the case-sensitive host (must NOT claim signal 2).
        diag = cf.extract_and_count(
            archive, dest, require_case_insensitive=False
        )
        extract_dict = diag.as_dict()
        lines.append("diagnostic_case_sensitive_extract=true")
        lines.append(f"diagnostic_archive_entry_count={diag.archive_entry_count}")
        lines.append(
            f"diagnostic_extracted_file_count={diag.extracted_file_count}"
        )
        lines.append(f"diagnostic_shortfall={diag.shortfall}")
        lines.append(
            "diagnostic_note=on case-sensitive FS both members land; "
            "shortfall stays 0 — cannot satisfy catalog signal (2) here"
        )

    missing_substrate = not host_ci
    lines.append(f"missing_case_insensitive_filesystem={missing_substrate}")
    lines.append(f"extraction_count_check_fired={shortfall_observed}")
    # Probe 2 is only CONFIRMED when a real CI-FS shortfall is observed.
    ok = (not missing_substrate) and shortfall_observed and set_report.collision_count >= 1
    lines.append(f"probe_2_confirmed={ok}")
    lines.append("PROBE-2-COMPLETE:IMP-0022")
    if ok:
        lines.append("SUCCESS:IMP-0022-probe2")
    else:
        lines.append(
            "BLOCKED:IMP-0022-probe2 missing-case-insensitive-filesystem-substrate"
        )
        lines.append("FAILED:IMP-0022-probe2")

    text = "\n".join(lines) + "\n"
    RAW.write_text(text, encoding="utf-8")
    meas = {
        "ok": ok,
        "missing_case_insensitive_filesystem": missing_substrate,
        "set_check_fired": set_report.collision_count >= 1,
        "extraction_count_check_fired": shortfall_observed,
        "extract_error": extract_error,
        "extract": extract_dict,
        "blocked_on": (
            "case-insensitive-filesystem-mount"
            if missing_substrate
            else None
        ),
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(text, end="")
    # Non-zero when substrate missing: honest fail-closed for signal (2).
    return 0 if ok else 22


if __name__ == "__main__":
    raise SystemExit(main())
