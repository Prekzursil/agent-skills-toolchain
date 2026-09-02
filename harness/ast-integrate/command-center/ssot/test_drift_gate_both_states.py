"""Both-states test for ssot_drift_gate.py.

A gate that has only ever been observed PASSING is not evidence. Per the estate rule: before a
gate's silence counts as "the fleet is current", the gate must be run against a KNOWN-BROKEN
state and confirmed to FIRE there. This harness does that, using real revisions of this repo --
no mocks, no fabricated fixtures.

STATE 1 (known-CLEAN, the live configuration)
    ref = origin/main. Expect exit 0. Independently corroborated: all five commits that ever
    touched the executed surface are ancestors of the executed HEAD, and the diff is 0 in BOTH
    directions (so a diff-direction bug cannot be hiding behind the zero).

STATE 2 (known-BROKEN, synthesised from real history)
    ref = the parent of a commit that genuinely modified the executed surface. The executed
    checkout then provably differs from the reference under a directory the live fleet loads
    from -- exactly the production hazard -- so the gate MUST exit 1 and name the files.

STATE 3 (degenerate)
    ref = the executed HEAD itself. A zero here is the CORRECT answer rather than a blind
    differ, and the gate must say so explicitly instead of claiming a meaningful pass.

The test asserts the gate DISTINGUISHES these. A gate returning the same verdict for states 1
and 2 would be inert -- it would pass in the field and be recorded as diligence while measuring
nothing, which is the specific failure this file exists to rule out.
"""

from __future__ import annotations

import subprocess
import sys

EXECUTED = "C:/Users/Prekzursil/source/agent-skills-toolchain"
GATE = "command-center/ssot/ssot_drift_gate.py"

# A real commit that modified tools/mcp/** -- its parent is therefore a reference against which
# the executed checkout is genuinely stale on the executed surface.
BREAKING_COMMIT = "89d20e64"


def run_gate(ref: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, GATE, "--executed", EXECUTED, "--ref", ref],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def head_of(repo: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def main() -> int:
    failures: list[str] = []
    executed_head = head_of(EXECUTED)

    print("=" * 72)
    print("STATE 1 -- known-CLEAN (live config, ref=origin/main): expect exit 0")
    print("=" * 72)
    rc1, out1 = run_gate("origin/main")
    clean_ok = rc1 == 0 and "drift=0" in out1
    print(out1.strip()[-700:])
    print(f"\n  -> exit {rc1}  {'PASS' if clean_ok else 'FAIL'}")
    if not clean_ok:
        failures.append(f"state1 expected exit 0 with drift=0, got {rc1}")

    print()
    print("=" * 72)
    print(
        f"STATE 2 -- known-BROKEN (ref={BREAKING_COMMIT}~1, a real commit that touched"
    )
    print("           the executed surface): expect exit 1 and the stale files named")
    print("=" * 72)
    rc2, out2 = run_gate(f"{BREAKING_COMMIT}~1")
    fired = rc2 == 1 and "FAILED:ssot-drift-gate drift=" in out2
    named = "DRIFT" in out2
    print(out2.strip()[-1400:])
    print(
        f"\n  -> exit {rc2}  fired={fired}  named-files={named}  "
        f"{'PASS' if fired and named else 'FAIL'}"
    )
    if not fired:
        failures.append(
            f"state2 expected exit 1 (drift detected), got {rc2} -- GATE IS INERT"
        )
    if not named:
        failures.append("state2 fired but named no stale file -- diagnostic is empty")

    print()
    print("=" * 72)
    print("STATE 3 -- degenerate (ref = executed HEAD): expect exit 0 AND an explicit")
    print(
        "           statement that zero-everywhere is correct here, not a blind differ"
    )
    print("=" * 72)
    rc3, out3 = run_gate(executed_head)
    honest = rc3 == 0 and "control N/A" in out3
    print(out3.strip()[-600:])
    print(
        f"\n  -> exit {rc3}  discloses-degenerate={honest}  "
        f"{'PASS' if honest else 'FAIL'}"
    )
    if not honest:
        failures.append(
            f"state3 expected exit 0 with the control-N/A disclosure, got {rc3}"
        )

    print()
    print("=" * 72)
    distinguishes = rc1 != rc2
    print(
        f"DISCRIMINATION: state1 exit={rc1} vs state2 exit={rc2} -> "
        f"{'the gate distinguishes the two hypotheses' if distinguishes else 'INERT GATE'}"
    )
    if not distinguishes:
        failures.append(
            "gate returns the same verdict clean vs broken -- it measures nothing"
        )

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        print("FAILED:drift-gate-both-states")
        return 1
    print("\nAll three states behaved as required; the gate fires only when it should.")
    print("SUCCESS:drift-gate-both-states states=3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
