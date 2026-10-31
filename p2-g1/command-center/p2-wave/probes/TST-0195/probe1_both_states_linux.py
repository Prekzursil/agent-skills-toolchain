#!/usr/bin/env python3
"""TST-0195 probe 1: both-states control on the linux policy leg.

Bad state : ./Skills/ against on-disk skills/ must exact-miss (ok=false,
            reason=exact-miss, resolved=null) - exact string comparison against
            the live directory listing, the semantic Path.exists carries on a
            case-sensitive FS.
Good state: ./skills/ resolves silently (ok=true, reason=ok-silent, warnings=[]).
Detector  : live os.listdir exact-membership is the independent signal that the
            mismatch is real on THIS host, independent of the policy code.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lookup import lookup  # noqa: E402

ROOT = HERE / "fixtures" / "plugin-root"


def main() -> int:
    good = lookup("./skills/", ROOT, "linux")
    bad = lookup("./Skills/", ROOT, "linux")

    exact_membership_skills = "skills" in os.listdir(ROOT)
    exact_membership_skills_upper = "Skills" in os.listdir(ROOT)

    checks = {
        "good_state_ok": good["ok"] is True and good["reason"] == "ok-silent" and good["warnings"] == [] and good["resolved"] == "skills",
        "bad_state_exact_miss": bad["ok"] is False and bad["reason"] == "exact-miss" and bad["resolved"] is None and bad["warnings"] == [],
        "live_exact_membership_skills": exact_membership_skills is True,
        "live_exact_membership_Skills_absent": exact_membership_skills_upper is False,
        "fixture_skill_md_present": (ROOT / "skills" / "skill.probe" / "SKILL.md").is_file(),
    }
    out = {
        "probe": "probe1_both_states_linux",
        "unit": "TST-0195",
        "linux_good": good,
        "linux_bad": bad,
        "live_os_exists_Skills": Path(str(ROOT / "Skills")).exists(),
        "live_os_exists_skills": (ROOT / "skills").exists(),
        "live_listdir_exact": {"skills": exact_membership_skills, "Skills": exact_membership_skills_upper},
        "checks": checks,
        "ok": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    (HERE / "probe1_both_states_linux.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
