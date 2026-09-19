#!/usr/bin/env python3
"""AUD-0096 tests_required control: the clean-profile detector must fire on a
leaked/contaminated profile and stay silent on a genuinely empty one.

catalog tests_required, verbatim: "control: the clean profile must be proven
clean - assert the harness state directories are absent or empty before the
measurement, otherwise a leaked profile makes the two runs identical by
construction." This reuses `is_profile_clean` from `_profile_check.py` -- the
SAME function probe1 calls as its own precondition gate -- so this control
proves that function actually discriminates, rather than re-implementing a
separate, potentially-diverging check.

Two fixtures, both real directories created and destroyed by this script
(never mutates any live profile):
  - good_fixture: a brand-new, genuinely empty scratch dir -> must report
    clean=True (the detector is not always-fires).
  - bad_fixture:  a scratch dir with ONE placeholder file planted at
    .cursor/skills-cursor/leaked-skill/SKILL.md, simulating a profile that
    was copied/leaked from a real one -> must report clean=False.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _profile_check import is_profile_clean  # noqa: E402

OUT_JSON = Path(__file__).resolve().parent / "control-profile-clean.json"
OUT_RAW = Path(__file__).resolve().parent / "control-profile-clean.raw.txt"


def main() -> int:
    raw_lines: list[str] = [
        "AUD-0096 CONTROL: clean-profile detector fires on leaked profile, "
        "silent on genuinely empty profile"
    ]

    good_home = Path(tempfile.mkdtemp(prefix="aud-0096-ctl-good-"))
    bad_home = Path(tempfile.mkdtemp(prefix="aud-0096-ctl-bad-"))
    try:
        leaked_skill_dir = bad_home / ".cursor" / "skills-cursor" / "leaked-skill"
        leaked_skill_dir.mkdir(parents=True, exist_ok=True)
        (leaked_skill_dir / "SKILL.md").write_text(
            "---\nname: leaked-skill\ndescription: planted-by-control-fixture\n---\n",
            encoding="utf-8",
        )

        good_result = is_profile_clean(good_home)
        bad_result = is_profile_clean(bad_home)

        raw_lines.append(f"good_home={good_home} good_result={json.dumps(good_result)}")
        raw_lines.append(f"bad_home={bad_home} bad_result={json.dumps(bad_result)}")

        fired_on_bad = bad_result["clean"] is False
        silent_on_good = good_result["clean"] is True
        ok = fired_on_bad and silent_on_good

        doc = {
            "ok": ok,
            "good_fixture": good_result,
            "bad_fixture": bad_result,
            "a_fires_on_bad": fired_on_bad,
            "a_silent_on_good": silent_on_good,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

        raw_lines.append(
            f"CONTROL fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} ok={ok}"
        )
        raw_lines.append(
            "SUCCESS:AUD-0096-control" if ok else "FAILED:AUD-0096-control"
        )
        OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print(OUT_RAW.read_text(encoding="utf-8"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(good_home, ignore_errors=True)
        shutil.rmtree(bad_home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
