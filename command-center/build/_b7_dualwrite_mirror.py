"""B7: mirror the reconcile into the `skills/` projection, as D-001 --strict-parity requires.

D-001 makes `.agents/skills` canonical and `skills/` a generated projection; the CI gate
`ci/check_skill_dual_write.py --strict-parity` requires a changed path to have a BYTE-IDENTICAL
counterpart in the other root.  So the live->repo reconcile has to land in both roots.

SAFETY PRECONDITION, checked per file before any write: the projection copy must currently be
either ABSENT (pure addition, nothing to lose) or BYTE-IDENTICAL (after LF normalisation) to the
canonical copy AS IT WAS AT HEAD -- i.e. the projection holds no unique content of its own.  Any
file failing that precondition is REFUSED and reported, never overwritten.

Usage:  python _b7_dualwrite_mirror.py            # dry run
        python _b7_dualwrite_mirror.py --apply
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
CANON = REPO / ".agents" / "skills"
PROJ = REPO / "skills"

applied = json.loads(
    (REPO / "command-center" / "build" / "B5-reconcile-applied.json").read_text(encoding="utf-8")
)


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def head_blob(rel: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"HEAD:.agents/skills/{rel}"],
                       capture_output=True, cwd=str(REPO))
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    do = "--apply" in sys.argv
    ok, refused, skipped = [], [], []
    for rel in applied["copied"]:
        skill = rel.split("/")[0]
        if not (PROJ / skill).is_dir():
            skipped.append((rel, "no skills/ projection for this skill"))
            continue
        dst = PROJ / rel
        if dst.exists():
            was = head_blob(rel)
            if was is None:
                refused.append((rel, "projection exists but canonical had no HEAD blob"))
                continue
            if norm(dst.read_bytes()) != norm(was):
                refused.append((rel, "projection holds content unique vs canonical@HEAD"))
                continue
        ok.append(rel)
        if do:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DAILY / rel, dst)

    print(f"mirror {'APPLIED' if do else 'DRY-RUN'}: {len(ok)} files")
    print(f"skipped (no projection dir): {len(skipped)}")
    for rel, why in skipped[:10]:
        print(f"   - {rel}  [{why}]")
    print(f"REFUSED (projection has unique content -- needs a human merge): {len(refused)}")
    for rel, why in refused:
        print(f"   ! {rel}  [{why}]")
    (REPO / "command-center" / "build" / "B7-dualwrite-mirror.json").write_text(
        json.dumps({"applied": do, "mirrored": sorted(ok),
                    "refused": sorted(refused), "skipped": sorted(skipped)}, indent=1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
