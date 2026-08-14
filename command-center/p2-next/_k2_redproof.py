"""Red-proof for C6: it must FIRE on the state that was actually shipped, and be REACHABLE.

Four legs, each of which fails a different way if the check is decorative:

  A  post-fix working tree                     -> SILENT      (the fix works)
  B  pre-fix COMMITTED blob, pinned to a SHA   -> FIRES        (the defect was real)
  C  declaration flipped to `down`             -> FIRES on the OWNING doc's own title
                                                  (the check reads the DECLARED field; it does not
                                                   treat the word DOWN as inherently wrong)
  D  the real CLI, `--doc` on a flipped copy   -> exit 1       (`ci-hygiene.md` §1: a detector
                                                  nothing invokes is not a detector)

Leg B is pinned to `0c64b983`, the last commit that touched the citing page, NOT to HEAD -- round
1 of this lane shipped a before/after probe pointed at HEAD and it went red the moment its own fix
landed. If that blob already carries the fix, this exits 2 rather than reporting a pass.

Run:  python command-center/p2-next/_k2_redproof.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OWNING = "command-center/CROSS-VENDOR-RAIL-STATUS.md"
CITING = "command-center/E2E-WAVE-STATUS.md"
PRE_FIX_REV = "0c64b983"
STALE = "The cross-vendor review rail is DOWN, and it gates 42 blocked units"

_spec = importlib.util.spec_from_file_location(
    "_rcg", Path(__file__).with_name("rail_count_gate.py")
)
_g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_g)


def blob(rev: str, rel: str) -> str:
    out = subprocess.run(
        ["git", "show", f"{rev}:{rel}"], cwd=REPO, capture_output=True, check=True
    )
    return out.stdout.decode("utf-8", "replace")


def main() -> int:
    results: dict[str, object] = {"pre_fix_rev": PRE_FIX_REV}
    owning_now = (REPO / OWNING).read_text(encoding="utf-8")
    citing_now = (REPO / CITING).read_text(encoding="utf-8")
    fields, block_problems = _g.parse_block(owning_now)
    declared, field_problems = _g.check_state_fields(fields)
    if block_problems or field_problems or declared != "up":
        print(
            f"FAILED:k2-redproof the working-tree block is not usable: {block_problems + field_problems} declared={declared!r}"
        )
        return 2

    citing_pre = blob(PRE_FIX_REV, CITING)
    if STALE not in citing_pre:
        print(
            f"FAILED:k2-redproof {PRE_FIX_REV}:{CITING} does not carry the stale assertion; "
            "it is not a before-state and this probe must not report a pass from it"
        )
        return 2

    legs = []

    a = _g.check_state_prose(owning_now, declared) + _g.check_state_prose(
        citing_now, declared, where=CITING
    )
    legs.append(("A post-fix working tree", a, False))

    b = _g.check_state_prose(citing_pre, declared, where=CITING)
    legs.append((f"B pre-fix blob @{PRE_FIX_REV}", b, True))

    c = _g.check_state_prose(owning_now, "down")
    legs.append(("C declaration flipped to down (control)", c, True))

    ok = True
    for label, problems, want_fire in legs:
        fired = bool(problems)
        good = fired == want_fire
        ok = ok and good
        print(
            f"  {'ok ' if good else 'BAD'} {label}: "
            f"{'FIRED' if fired else 'silent'} (want {'FIRE' if want_fire else 'SILENCE'})"
            + (f" -- {problems[0][:150]}" if problems else "")
        )
        results[label] = problems

    # Leg D: through the real CLI, so the check is proven WIRED and not merely importable.
    tmp = Path(tempfile.mkdtemp(prefix="k2_")) / "flipped.md"
    tmp.write_text(
        owning_now.replace("rail_state: up", "rail_state: down"),
        encoding="utf-8",
        newline="\n",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "command-center/p2-next/rail_count_gate.py"),
            "--doc",
            str(tmp),
        ],
        cwd=REPO,
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace")
    # `C6 rail verdict:` is the per-run SUMMARY line, not a problem. Counting it would inflate a
    # clean run to "1 problem" and make this receipt say something the gate did not.
    c6_lines = [
        ln.strip()
        for ln in out.splitlines()
        if ln.strip().startswith("C6 ")
        and not ln.strip().startswith("C6 rail verdict:")
    ]
    d_good = proc.returncode == 1 and bool(c6_lines)
    ok = ok and d_good
    print(
        f"  {'ok ' if d_good else 'BAD'} D real CLI on a flipped copy: exit {proc.returncode} "
        f"(want 1), {len(c6_lines)} C6 problem(s)"
        + (f" -- {c6_lines[0][:150]}" if c6_lines else "")
    )
    results["D cli"] = {"exit": proc.returncode, "c6": c6_lines}

    (REPO / "command-center/p2-next/K2-REDPROOF.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8", newline="\n"
    )
    if not ok:
        print("FAILED:k2-redproof a leg did not discriminate")
        return 1
    print(
        "SUCCESS:k2-redproof C6 fires on the shipped defect, is silent on the fix, and is wired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
