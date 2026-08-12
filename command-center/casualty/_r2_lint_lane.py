r"""Bring this lane to ruff-green WITHOUT destroying the dead agents' provenance.

Main is broadly CI-red on the pinned ruff (145 files repo-wide, 29 lint errors); 41 of those
files and 10 of those errors are this lane's. This script fixes the lane's share.

THE CONFLICT, and why it is resolved this way rather than by running ruff over the directory.
Five scripts under probes/ are BYTE-IDENTICAL to the dead agents' scratch originals, and the
adversarial audit's "prior work recovered, not redone" finding rests on exactly that sha256
match. Reformatting them would satisfy a style gate by destroying the evidence that the work was
recovered rather than re-authored. They are excluded, verified locked BEFORE and AFTER, and the
residual is reported instead of hidden: the durable fix is an extend-exclude entry in the ROOT
ruff.toml, which is outside this lane's file scope.

Terminal: SUCCESS:r2-lint-lane / FAILED:r2-lint-lane <reason>
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
LANE = ROOT / "command-center" / "casualty"
SCRATCH = Path(
    "C:/Users/Prekzursil/AppData/Local/Temp/claude/C--Users-Prekzursil"
    "/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/scratchpad"
)
RUFF = ["uvx", "ruff@0.15.17"]

LOCKED = [
    "adv0021_probe1.py",
    "adv0021_probe2.py",
    "adv0021_probe2b.py",
    "adv0022_escape_harness.py",
    "adv0022_probe2.py",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def locked_state() -> dict:
    out = {}
    for name in LOCKED:
        lane, scr = LANE / "probes" / name, SCRATCH / name
        out[name] = {
            "lane": sha(lane) if lane.is_file() else None,
            "scratch": sha(scr) if scr.is_file() else None,
        }
        out[name]["match"] = (
            out[name]["lane"] == out[name]["scratch"] and out[name]["lane"]
        )
    return out


def run(argv: list[str]) -> tuple[int, str]:
    r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).replace("\r\n", "\n")


def main() -> int:
    before = locked_state()
    n_locked = sum(1 for v in before.values() if v["match"])
    print(
        f"provenance BEFORE: {n_locked}/{len(LOCKED)} probe scripts byte-identical to the "
        f"dead agents' scratch originals"
    )
    if n_locked != len(LOCKED):
        print(
            "FAILED:r2-lint-lane provenance is already broken; refusing to format anything"
        )
        return 1

    targets = sorted(
        p
        for p in LANE.rglob("*.py")
        if "__pycache__" not in p.parts and p.name not in LOCKED
    )
    rel = [str(p.relative_to(ROOT)).replace("\\", "/") for p in targets]
    print(
        f"formatting {len(rel)} lane python files (excluding {len(LOCKED)} provenance-locked)"
    )

    rc1, out1 = run([*RUFF, "check", "--fix", *rel])
    print(out1.strip().splitlines()[-1] if out1.strip() else "check: clean")
    rc2, out2 = run([*RUFF, "format", *rel])
    print(out2.strip().splitlines()[-1] if out2.strip() else "format: clean")

    after = locked_state()
    still = all(after[n]["lane"] == before[n]["lane"] for n in LOCKED)
    print(f"provenance AFTER : unchanged={still}")

    rc3, out3 = run([*RUFF, "check", *rel])
    rc4, out4 = run([*RUFF, "format", "--check", *rel])
    print(
        f"re-check  rc={rc3}: {out3.strip().splitlines()[-1] if out3.strip() else 'clean'}"
    )
    print(
        f"re-format rc={rc4}: {out4.strip().splitlines()[-1] if out4.strip() else 'clean'}"
    )

    rc5, out5 = run([*RUFF, "format", "--check", "command-center/casualty/"])
    residual = [
        ln.split("Would reformat: ")[-1]
        for ln in out5.splitlines()
        if ln.startswith("Would reformat")
    ]
    print(
        f"\nRESIDUAL still red in the lane: {len(residual)} file(s) -- these are the "
        f"provenance-locked originals, deliberately untouched:"
    )
    for r in residual:
        print(f"   {r}")
    print(
        "   FIX (outside this lane's file scope): add "
        "'command-center/casualty/probes/' to extend-exclude in the ROOT ruff.toml."
    )

    ok = still and rc3 == 0 and rc4 == 0
    print("SUCCESS:r2-lint-lane" if ok else "FAILED:r2-lint-lane")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
