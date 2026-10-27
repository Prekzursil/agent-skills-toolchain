"""Control the .gitignore EXCEPTION 3 both ways.

A negation block is a claim that it is NARROW. That claim needs the failing half:
the seven cited scripts must become visible to git, AND an UNCITED sibling
matching the same `platform/**/_probe_*.py` rule must stay ignored. Without the
second half, a rule that accidentally un-ignored the whole tree would look
identical to a correctly scoped one.

Run:  python command-center/slop-report/_r3_ignore_control.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")

NEGATED = [
    "platform/architecture/_probe_crossvendor_alias_hole.py",
    "platform/architecture/_probe_dr_acyclic.py",
    "platform/architecture/_probe_dr_bucketedge.py",
    "platform/architecture/_probe_dr_catalog.py",
    "platform/architecture/_probe_dr_scheduling.py",
    "platform/council/presets/_probe_preset_validation.py",
    "platform/lib/workflows/_gen_bp5.py",
]


def is_ignored(rel: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", "--", rel], cwd=REPO, capture_output=True
        ).returncode
        == 0
    )


def main() -> int:
    on_disk = sorted(
        str(p.relative_to(REPO)).replace("\\", "/")
        for p in (REPO / "platform").rglob("_probe_*.py")
    )
    uncited = [p for p in on_disk if p not in NEGATED]
    still_ignored = [p for p in uncited if is_ignored(p)]
    leaked = [p for p in uncited if not is_ignored(p)]
    negated_visible = [p for p in NEGATED if not is_ignored(p)]

    checks = {
        "all_seven_now_visible": len(negated_visible) == 7,
        "uncited_population_nonempty": len(uncited) > 0,
        "every_uncited_sibling_still_ignored": not leaked,
    }
    payload = {
        "platform_probe_files_on_disk": len(on_disk),
        "negated": NEGATED,
        "negated_visible_n": len(negated_visible),
        "uncited_n": len(uncited),
        "uncited_still_ignored_n": len(still_ignored),
        "leaked": leaked,
        "checks": checks,
        "all_pass": all(checks.values()),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"platform `_probe_*.py` on disk: {len(on_disk)}")
    print(f"  negated and now visible: {len(negated_visible)}/7")
    print(f"  uncited siblings: {len(uncited)}, still ignored: {len(still_ignored)}")
    if leaked:
        print(f"  LEAKED (should still be ignored): {leaked}")
    for k, v in checks.items():
        print(f"  {'ok ' if v else 'BAD'} {k}: {v}")
    if not payload["all_pass"]:
        print("FAILED:r3-ignore-control the exception is not narrow")
        return 1
    print(f"SUCCESS:r3-ignore-control -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
