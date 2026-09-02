"""Both-states test of the red-proof's OWN pin guard.

The guard added after the control self-invalidated must do more than exist: it has to
FIRE when the pin is pointed at a commit that already carries W7. Without this, the fix
for a silent-degradation bug would itself be unproven -- which is the shape that produced
the bug in the first place.

  state A (correct pin, pre-W7)  -> exit 0, discrimination holds
  state B (pin moved onto W7)    -> exit 2, and it SAYS the control is a copy of the
                                    treatment rather than reporting a pass
"""

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w7_redproof  # noqa: E402

GOOD = w7_redproof.BEFORE_REV
BAD = "HEAD"  # HEAD carries W7 now -- the exact regression the guard exists to refuse


def _has_w7(rev: str) -> bool:
    p = subprocess.run(
        ["git", "show", f"{rev}:{w7_redproof.CHECKER_REL}"],
        cwd=w7_redproof.ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode == 0 and w7_redproof.W7_CODE in p.stdout


# CONTROL on the control: the two revs must genuinely differ in whether they carry W7,
# or this probe is comparing a state against itself.
good_has, bad_has = _has_w7(GOOD), _has_w7(BAD)
print(f"CONTROL  {GOOD} carries W7={good_has}   {BAD} carries W7={bad_has}")
if good_has or not bad_has:
    print("FAILED:pin-failsclosed the two states are not distinguishable")
    raise SystemExit(2)

print(f"\n-- state A: pin = {GOOD} (pre-W7) --")
w7_redproof.BEFORE_REV = GOOD
rc_a = w7_redproof.main()
print(f"--> exit={rc_a} (expect 0)")

print(f"\n-- state B: pin = {BAD} (already carries W7) --")
w7_redproof.BEFORE_REV = BAD
rc_b = w7_redproof.main()
print(f"--> exit={rc_b} (expect 2, NOT 0)")

ok = rc_a == 0 and rc_b == 2
print(
    f"\nDISCRIMINATION: good-pin={rc_a} bad-pin={rc_b} -> "
    f"{'guard fails closed' if ok else 'GUARD IS INERT'}"
)
if not ok:
    print("FAILED:pin-failsclosed")
    raise SystemExit(1)
print("SUCCESS:pin-failsclosed a re-pointed pin is refused, not silently accepted")
