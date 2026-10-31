#!/usr/bin/env python3
"""IMP-0010 probe2 (verifier): predict-vs-actual over a live dry-run deploy.

Mechanically different from probe1 (which runs the pytest suite): this probe
drives the projection directly against the real repo manifests, deploys into
a throwaway HOME, walks the resulting file listing, and requires exact set
equality. NEGATIVE CONTROL: dropping one skill entry makes exactly one
predicted path disappear.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin import projection_map as pm  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0010-p2-"))
    try:
        bundle = pm.load_bundle(REPO)
        home = work / "home"
        predicted = pm.predict(bundle, home)
        actual = pm.dry_run(bundle, home)
        landed = sorted(
            p.relative_to(home).as_posix()
            for p in home.rglob("*") if p.is_file()
        )
        # file-level sets: predicted identities collapse "#key" suffixes
        pred_files = sorted({p.split("#", 1)[0].replace(home.as_posix() + "/", "") for p in predicted})
        diff = pm.diff_sets(pred_files, landed)
        checks = {
            "predicted_absent_empty": diff["predicted_absent"] == [],
            "present_unpredicted_empty": diff["present_unpredicted"] == [],
            "count_matches": len(pred_files) == len(landed),
        }
        # NEGATIVE CONTROL: drop one skill, exactly one predicted path vanishes
        victim = bundle["skills"]["skills"][0]["name"]
        dropped = pm.drop_entry(bundle, "skill", victim)
        after = pm.predict(dropped, home)
        gone = set(predicted) - set(after)
        checks["exactly_one_disappeared"] = len(gone) == 1 and victim in gone.pop()
        out = {"unit_id": "IMP-0010", "probe": "probe2-dryrun-diff-live", "checks": checks,
               "predicted_count": len(predicted), "landed_count": len(landed),
               "negative_control_victim": victim, "pass": all(checks.values())}
        print(os.linesep.join(f"{k}={v}" for k, v in checks.items()))
        print(f"predicted={len(predicted)} landed={len(landed)} victim={victim}")
        if not all(checks.values()):
            print("FAILED:IMP-0010-probe2 " + repr(out))
            return 1
        print("SUCCESS:IMP-0010-probe2 live dry-run matches prediction; drop-one control exact")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
