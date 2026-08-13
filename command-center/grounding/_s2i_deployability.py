"""Is the INTEGRATE edit deployable, or does it add to the orphan-tree pile?

The audit's REAL DEFECT (D1) was that the builder's 7 DESCRIPTION edits made 6
previously-IDENTICAL vault files DIVERGED, which the deploy hop refuses by
design -- so the edit permanently widened the very orphan tree the lane existed
to diagnose.  This asks the same question of MY edit.

RULE-3c CONTROL, stated before the run:
  H1  an append-only body insertion classifies RIGHT-AHEAD (deployable) while a
      description MODIFY classifies DIVERGED (refused).
  H2  the reporter is inert here and just says RIGHT-AHEAD for whatever it sees.
Under H2 both my file and the builder's edited files read the same.  Under H1
they differ.  So the control is the BUILDER'S files measured in the SAME run --
if they do not come back DIVERGED, my RIGHT-AHEAD means nothing.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "_drift", REPO / "ci" / "check_skill_deploy_drift.py"
)
assert spec and spec.loader
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)

LIVE = {
    "skills.daily": Path("C:/Users/Prekzursil/.claude/skills.daily"),
    "vault(.agents/skills)": Path("C:/Users/Prekzursil/.agents/skills"),
}
MINE = "writing-skills"
# The builder's 7 description edits -- the audit measured 6 of them going DIVERGED.
BUILDER = [
    "transcribe",
    "tdd-workflow",
    "security-review",
    "screenshot",
    "e2e-testing",
    "python-testing",
    "research-ops",
]


def pre_edit_verdict(live_root: Path) -> str:
    """Classify the live copy against the COMMITTED (pre-edit) repo blob."""
    blob = subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:skills/{MINE}/SKILL.md"],
        capture_output=True,
    )
    if blob.returncode != 0:
        return "NO-BLOB"
    tmp = REPO / "command-center" / "grounding" / "_s2i_tmp_head_SKILL.md"
    tmp.write_bytes(blob.stdout)
    try:
        return drift.classify_pair(live_root / MINE / "SKILL.md", tmp)
    finally:
        tmp.unlink(missing_ok=True)


out: dict[str, object] = {}
for label, root in LIVE.items():
    if not root.is_dir():
        out[label] = {"error": "live root absent"}
        continue
    report = drift.reconcile(root, REPO / "skills")
    skills = report["skills"]
    assert isinstance(skills, dict)
    summary = report["summary"]

    mine_now = skills.get(MINE, {}).get("verdict", "NOT-SHARED")
    mine_before = pre_edit_verdict(root)
    control = {
        name: skills.get(name, {}).get("verdict", "NOT-SHARED") for name in BUILDER
    }
    verdict_set = set(control.values()) | {mine_now}

    out[label] = {
        "summary": summary,
        "MINE_writing-skills_now": mine_now,
        "MINE_writing-skills_before_my_edit": mine_before,
        "CONTROL_builder_description_edits": control,
        "verdicts_are_distinguishable": len(verdict_set) > 1,
    }

    print(f"=== {label}")
    print(f"    summary                       : {summary}")
    print(f"    MINE {MINE} BEFORE my edit : {mine_before}")
    print(f"    MINE {MINE} AFTER  my edit : {mine_now}")
    print("    CONTROL (builder description edits):")
    for name, verdict in control.items():
        print(f"      {name:18s} {verdict}")
    print(f"    verdicts distinguishable?     : {len(verdict_set) > 1}")
    deployable = mine_now in (drift.RIGHT_AHEAD, drift.IDENTICAL)
    print(f"    => my edit deployable         : {deployable}")

(REPO / "command-center" / "grounding" / "S2I-DEPLOYABILITY.json").write_text(
    json.dumps(out, indent=2, sort_keys=True), encoding="utf-8"
)
print("\nwrote command-center/grounding/S2I-DEPLOYABILITY.json")
