#!/usr/bin/env python3
"""AUD-0096 named probe 2: measure the harness load set in the CURRENT profile
and report the diff against probe1's clean-profile measurement.

catalog evidence_requirement, verbatim: "Probe 2: the same measurement in the
current profile, reported as a diff - the clean-profile number alone cannot
tell you which of the current profile's behaviours are accidental local
state." This probe reads probe1's OWN JSON output (not a re-derivation) so the
diff is computed against what probe1 actually recorded, not an assumption
about it.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _profile_check import census_load_set, is_profile_clean  # noqa: E402

PROBE = Path(__file__).resolve().parent
P1_JSON = PROBE / "probe1-clean-profile-load.json"
OUT_JSON = PROBE / "probe2-current-profile-diff.json"
OUT_RAW = PROBE / "probe2-current-profile-diff.raw.txt"


def diff_censuses(clean: dict, current: dict) -> dict:
    """Per-component diff: current - clean. Since the clean census is always
    zero (a scratch dir this run just created), the diff numerically equals
    the current-profile measurement, but it is computed as an explicit
    subtraction (not assumed equal) so this probe stays correct even if a
    future clean-profile measurement is ever non-zero (e.g. a harness that
    pre-populates a default skill on first boot)."""
    out: dict = {"components": {}}
    all_keys = sorted(set(clean["components"]) | set(current["components"]))
    for key in all_keys:
        c = clean["components"].get(key, {})
        cur = current["components"].get(key, {})
        entry: dict = {"clean": c, "current": cur, "delta": {}}
        for metric in ("skill_count", "file_count", "total_bytes"):
            if metric in c or metric in cur:
                entry["delta"][metric] = int(cur.get(metric, 0)) - int(c.get(metric, 0))
        out["components"][key] = entry
    out["total_skill_count_delta"] = int(current["total_skill_count"]) - int(
        clean["total_skill_count"]
    )
    out["total_file_count_delta"] = int(current["total_file_count"]) - int(
        clean["total_file_count"]
    )
    out["total_bytes_delta"] = int(current["total_bytes"]) - int(clean["total_bytes"])
    return out


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines: list[str] = [
        "AUD-0096 NAMED PROBE 2: current-profile harness load set as a diff "
        "against probe1's clean-profile measurement",
        f"started_at={started}",
    ]

    if not P1_JSON.is_file():
        doc = {
            "started_at": started,
            "ok": False,
            "error": f"probe1 output missing at {P1_JSON}; run probe1 first",
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        raw_lines.append("FAILED:AUD-0096-probe2 probe1 output missing")
        OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print("\n".join(raw_lines[-2:]))
        return 1

    p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
    if not p1.get("ok"):
        doc = {
            "started_at": started,
            "ok": False,
            "error": "probe1 did not succeed (ok=false); cannot diff against it",
            "probe1_error": p1.get("error"),
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        raw_lines.append("FAILED:AUD-0096-probe2 probe1 was not ok")
        OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print("\n".join(raw_lines[-2:]))
        return 1

    clean_census = p1["census"]

    real_home = Path(os.environ.get("HOME") or Path.home())
    raw_lines.append(f"real_home={real_home}")

    current_clean_check = is_profile_clean(real_home)
    raw_lines.append(f"current_clean_check={json.dumps(current_clean_check)}")

    current_census = census_load_set(real_home)
    raw_lines.append(f"current_census={json.dumps(current_census)}")

    diff = diff_censuses(clean_census, current_census)
    raw_lines.append(f"diff={json.dumps(diff)}")

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "started_at": started,
        "ended_at": ended,
        "ok": True,
        "real_home": str(real_home),
        "current_clean_check": current_clean_check,
        "clean_census": clean_census,
        "current_census": current_census,
        "diff": diff,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines.append(
        f"total_skill_count_delta={diff['total_skill_count_delta']} "
        f"total_file_count_delta={diff['total_file_count_delta']} "
        f"total_bytes_delta={diff['total_bytes_delta']}"
    )
    raw_lines.append("SUCCESS:AUD-0096-probe2")
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    print(
        f"unit=AUD-0096 probe2 total_skill_count_delta={diff['total_skill_count_delta']} "
        f"total_file_count_delta={diff['total_file_count_delta']} "
        f"total_bytes_delta={diff['total_bytes_delta']} ok={doc['ok']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
