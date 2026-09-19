#!/usr/bin/env python3
"""AUD-0096 named probe 1: measure the harness load set in a clean profile.

A brand-new scratch directory is created and used as a synthetic $HOME. The
tests_required control is executed FIRST (not a separate afterthought): the
scratch dir's harness-state directories (.cursor, .claude, .codex) must be
proven absent/empty BEFORE the census runs, otherwise a leaked profile would
make the clean and current measurements identical by construction. If that
precondition fails, the probe reports ok=false rather than measuring anyway.

HONESTY NOTE (the real headline caveat, not smoothed over): this substrate
cannot spawn a genuinely fresh Cursor Cloud agent session against a synthetic
$HOME -- that would require restarting the harness daemon against an
alternate profile, which is out of scope and could mutate live state (catalog
retry_policy: "a failed run here may have mutated the tree ... restore from
the AUD-0092 backup"). What this probe actually measures is a FILESYSTEM
CENSUS of a directory this run created and fully controls, standing in for
"what a harness would load from a $HOME with none of the operator's
side-loaded skill packs, plugin cache, or hooks" -- it is a real, reproducible
measurement, but it is not an executed-and-observed fresh harness boot. That
gap is why this unit's `all_documented_steps_passed`-style claim is bounded,
and is recorded verbatim in the packed receipt's residual_unknowns.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _profile_check import census_load_set, is_profile_clean  # noqa: E402

OUT_JSON = Path(__file__).resolve().parent / "probe1-clean-profile-load.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-clean-profile-load.raw.txt"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines: list[str] = [
        "AUD-0096 NAMED PROBE 1: harness load set in a clean profile",
        f"started_at={started}",
    ]

    scratch_home = Path(tempfile.mkdtemp(prefix="aud-0096-clean-home-"))
    raw_lines.append(f"scratch_home={scratch_home}")

    clean_check = is_profile_clean(scratch_home)
    raw_lines.append(f"clean_precheck={json.dumps(clean_check)}")

    if not clean_check["clean"]:
        doc = {
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ok": False,
            "error": "clean-profile precondition failed: harness state leaked into scratch home",
            "scratch_home": str(scratch_home),
            "clean_check": clean_check,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        raw_lines.append("FAILED:AUD-0096-probe1 clean-profile precondition unmet")
        OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print("\n".join(raw_lines[-4:]))
        shutil.rmtree(scratch_home, ignore_errors=True)
        return 1

    census = census_load_set(scratch_home)
    raw_lines.append(f"census={json.dumps(census)}")

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "started_at": started,
        "ended_at": ended,
        "ok": True,
        "scratch_home": str(scratch_home),
        "clean_check": clean_check,
        "census": census,
        "measurement_kind": (
            "filesystem-census-of-controlled-scratch-dir, NOT an executed "
            "fresh-harness-boot observation (see residual_unknowns in the "
            "packed receipt)"
        ),
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines.append(
        f"total_skill_count={census['total_skill_count']} "
        f"total_file_count={census['total_file_count']} "
        f"total_bytes={census['total_bytes']}"
    )
    raw_lines.append("SUCCESS:AUD-0096-probe1")
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    # The artifact is the JSON/raw measurement, not the scratch tree itself.
    shutil.rmtree(scratch_home, ignore_errors=True)

    print(
        f"unit=AUD-0096 probe1 clean={clean_check['clean']} "
        f"total_skill_count={census['total_skill_count']} "
        f"total_file_count={census['total_file_count']} ok={doc['ok']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
