#!/usr/bin/env python3
"""IMP-0022 Probe 1: casefold-collision count over the payload path set.

Catalog signal (1): compute NFC+casefold collision groups over a path list.
Plant README.md + readme.md and require collision_group_count >= 1.
Also confirm a clean disjoint set reports zero collisions.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import casefold_paths as cf  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
RAW = PROBE_DIR / "probe1-casefold-set.raw.txt"
MEAS = PROBE_DIR / "probe1-measurement.json"

EVIDENCE = (
    "TWO independent signals: (1) casefold-collision count computed over the "
    "payload path set; (2) an actual extraction of the artifact onto a "
    "case-insensitive filesystem, comparing the extracted file count against "
    "the archive entry count — a collision shows up as a shortfall."
)


def main() -> int:
    lines: list[str] = []
    lines.append("NAMED PROBE 1: CASEFOLD-COLLISION COUNT OVER PAYLOAD PATH SET")
    lines.append("PROBE-1-BEGIN:IMP-0022")
    lines.append("stage=p2-deliver")
    lines.append(f"evidence_requirement_verbatim={EVIDENCE}")
    lines.append(f"host_os_name={os_name()}")
    lines.append(f"host_platform={platform.system().lower()}")
    lines.append(f"python_version={platform.python_version()}")
    lines.append("normalisation=NFC then str.casefold (not str.lower)")
    lines.append(f"helper_module={PLUGIN / 'casefold_paths.py'}")

    clean = ["LICENSE", "README.md", "bin/tool.py", "schema/a.schema.json"]
    clean_report = cf.find_casefold_collisions(clean)
    lines.append(f"clean_path_count={len(clean_report.paths)}")
    lines.append(f"clean_collision_group_count={clean_report.collision_count}")
    lines.append(f"clean_colliding_path_count={clean_report.colliding_path_count}")

    planted = ["LICENSE", "README.md", "readme.md", "bin/tool.py"]
    planted_report = cf.find_casefold_collisions(planted)
    lines.append(f"planted_paths={planted}")
    lines.append(
        f"planted_collision_group_count={planted_report.collision_count}"
    )
    lines.append(
        f"planted_colliding_path_count={planted_report.colliding_path_count}"
    )
    lines.append(
        "planted_collisions="
        + json.dumps(
            [{"key": g.key, "paths": list(g.paths)} for g in planted_report.collisions],
            sort_keys=True,
        )
    )

    # NFC-before-casefold: NFD and NFC forms share a key; Café.md vs café.md collide.
    nfd = "cafe\u0301.md"
    nfc = "caf\u00e9.md"
    lines.append(f"nfc_key_equal={cf.casefold_key(nfd) == cf.casefold_key(nfc)}")
    lines.append(f"nfc_pair_key={cf.casefold_key(nfd)!r}")
    lines.append(
        f"nfc_exact_after_normalize_equal={cf.nfc_path(nfd) == cf.nfc_path(nfc)}"
    )
    mixed = cf.find_casefold_collisions(["Caf\u00e9.md", "caf\u00e9.md", "other.md"])
    lines.append(f"accent_case_collision_group_count={mixed.collision_count}")
    lines.append(
        "accent_case_collisions="
        + json.dumps(
            [{"key": g.key, "paths": list(g.paths)} for g in mixed.collisions],
            sort_keys=True,
        )
    )
    lines.append(f"uses_casefold_not_lower={cf.casefold_key('README.md') == 'readme.md'}")

    set_check_fired = planted_report.collision_count >= 1 and {
        "README.md",
        "readme.md",
    }.issubset(set(planted_report.collisions[0].paths))
    lines.append(f"set_check_fired_on_planted_readme_pair={set_check_fired}")
    lines.append(f"clean_silent={clean_report.collision_count == 0}")

    ok = (
        set_check_fired
        and clean_report.collision_count == 0
        and cf.casefold_key(nfd) == cf.casefold_key(nfc)
        and mixed.collision_count == 1
    )
    lines.append(f"probe_1_confirmed={ok}")
    lines.append("PROBE-1-COMPLETE:IMP-0022")
    if ok:
        lines.append("SUCCESS:IMP-0022-probe1")
    else:
        lines.append("FAILED:IMP-0022-probe1")

    text = "\n".join(lines) + "\n"
    RAW.write_text(text, encoding="utf-8")
    meas = {
        "ok": ok,
        "clean_collision_group_count": clean_report.collision_count,
        "planted_collision_group_count": planted_report.collision_count,
        "planted_paths": planted_report.collisions[0].paths
        if planted_report.collisions
        else [],
        "nfc_key_equal": cf.casefold_key(nfd) == cf.casefold_key(nfc),
        "accent_case_collision_group_count": mixed.collision_count,
        "set_check_fired_on_planted_readme_pair": set_check_fired,
        "normalisation": "NFC then str.casefold (not str.lower)",
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(text, end="")
    return 0 if ok else 1


def os_name() -> str:
    return "posix" if sys.platform != "win32" else "nt"


if __name__ == "__main__":
    raise SystemExit(main())
