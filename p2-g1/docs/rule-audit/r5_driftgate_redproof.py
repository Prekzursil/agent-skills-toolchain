#!/usr/bin/env python3
"""RED-PROOF for r5_deploy_drift_gate: drive its real ``main()`` to rc=1 in BOTH directions.

WHY A SEPARATE FILE, and why it is a CI gate rather than a lane probe.  ``r5_deploy_drift_gate``
can only enforce anything where ``~/.claude`` exists, i.e. never on a runner -- there it prints
NOT-CHECKED and exits 0 by design.  A gate that is inert in CI and has never been seen red in CI
is indistinguishable from a no-op, which is the failure ``ci-hygiene`` section 1 is about.

This file removes that hole WITHOUT needing a home directory: every tree it uses is synthesized
from the in-repo ``rules/`` tree, so it runs identically on this box and on a runner, and it
drives the gate's actual ``main()`` through ``subprocess`` -- real argv, real exit code, real
stdout -- rather than re-testing the pure predicates the gate's own ``--self-test`` covers.

The five states it forces:

  A  live tree ABSENT          -> rc=0, marker says NOT-CHECKED and does NOT claim the baseline
                                  holds.  The state a runner is actually in.
  B  live == an exact copy of  -> rc=1, every baselined file reports SHRANK.  This is the
     the repo tree                "somebody deployed" direction: the debt was paid and the
                                  baseline must be updated to match.
  C  B plus one NON-baselined  -> rc=1 AND a GREW line naming that file.  The "a rule drifted
     always-on rule mutated       and nobody noticed" direction -- the 28 -> 29 move that
                                  happened silently while 167 tests stayed green.
  D  repo tree EMPTY           -> rc=1, "detector broken".  Fail closed: a walk that found
                                  nothing must never be reported as a tree with no drift.
  E  a paths-scoped rule has   -> rc=1 AND a LOAD CLASS divergence line.  A deploy that strips
     its frontmatter stripped     or adds frontmatter changes the live turn-0 set, which no
     in the live copy             gate in this repo checked before BUILD-R3.  The rule to
                                  promote is chosen by measurement, not hardcoded, so the proof
                                  survives any single rule being re-scoped.

Plus the discrimination control that AGENTS-level rule 3c demands: state B must contain SHRANK
and NOT contain GREW, and state C must contain both.  If every run printed both words, the
direction claim would be decoration -- the control would prove only that the gate produced
output, not that it can tell a repair from a regression.

Run::

    python docs/rule-audit/r5_driftgate_redproof.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GATE = HERE / "r5_deploy_drift_gate.py"
REPO_RULES = REPO / "rules"

sys.path.insert(0, str(HERE))
import r5_deploy_drift_gate as gate  # noqa: E402
import rule_audit  # noqa: E402  (same reader/parser the gate itself uses)

# A rule that is always-on (no frontmatter) and is NOT in the drifted baseline, so mutating it
# must read as a NEW divergence rather than as a change to an already-known one.
UNDRIFTED_ALWAYS_ON = "common/stale-megapr-reconcile.md"


def run_gate(repo_root: pathlib.Path, live_root: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            str(GATE),
            "--repo-root",
            str(repo_root),
            "--live-root",
            str(live_root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    print(
        "== r5_deploy_drift RED-PROOF (drives the real main(), no ~/.claude needed) =="
    )
    baseline_n = len(gate.BASELINE_ALWAYS_ON_DRIFT) + len(gate.BASELINE_LAZY_DRIFT)
    if baseline_n == 0:
        print(
            "FAILED:r5_driftgate_redproof baseline is EMPTY -- nothing to prove against"
        )
        return 1
    if UNDRIFTED_ALWAYS_ON in gate.BASELINE_ALWAYS_ON_DRIFT:
        print(
            f"FAILED:r5_driftgate_redproof {UNDRIFTED_ALWAYS_ON} is now baselined as drifted; "
            "pick another undrifted always-on rule for the GREW arm"
        )
        return 1
    if not REPO_RULES.is_dir():
        print("FAILED:r5_driftgate_redproof in-repo rules/ tree missing")
        return 1

    checks: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)

        # ---- A: the runner's world -------------------------------------------------
        rc, out = run_gate(REPO_RULES, tmp / "does-not-exist")
        checks.append(("A rc==0 when live tree absent", rc == 0))
        checks.append(("A marker says NOT-CHECKED", "NOT-CHECKED" in out))
        checks.append(
            ("A does NOT claim the baseline holds", "baseline holds" not in out)
        )

        # ---- B: everything deployed (the repair direction) --------------------------
        mirror = tmp / "mirror"
        shutil.copytree(REPO_RULES, mirror)
        rc_b, out_b = run_gate(REPO_RULES, mirror)
        checks.append(("B rc==1 when the drift disappears", rc_b == 1))
        checks.append(("B reports SHRANK", "SHRANK" in out_b))
        checks.append(
            (
                f"B reports SHRANK for all {baseline_n} baselined files",
                out_b.count("SHRANK") == baseline_n,
            )
        )
        # Discrimination control: this arm must NOT also say GREW, or the direction is noise.
        checks.append(
            (
                "B does NOT report GREW (directions are distinguishable)",
                "GREW" not in out_b,
            )
        )

        # ---- C: a NEW always-on divergence appears ----------------------------------
        mutated = tmp / "mutated"
        shutil.copytree(REPO_RULES, mutated)
        target = mutated / UNDRIFTED_ALWAYS_ON
        if not target.is_file():
            print(
                f"FAILED:r5_driftgate_redproof {UNDRIFTED_ALWAYS_ON} not found in rules/"
            )
            return 1
        target.write_text(
            target.read_text(encoding="utf-8") + "\nAN UNDEPLOYED EDIT\n",
            encoding="utf-8",
            newline="\n",
        )
        rc_c, out_c = run_gate(REPO_RULES, mutated)
        checks.append(("C rc==1 when a new always-on rule drifts", rc_c == 1))
        checks.append(
            (
                "C names the newly drifted rule in an ALWAYS-ON GREW line",
                f"ALWAYS-ON drift GREW: '{UNDRIFTED_ALWAYS_ON}'" in out_c,
            )
        )
        checks.append(
            (
                "C reports BOTH directions in one run",
                "GREW" in out_c and "SHRANK" in out_c,
            )
        )

        # ---- E: the deployed copy changes its LOAD CLASS -----------------------------
        # Strip the frontmatter from a paths-scoped rule in the "live" copy: that rule would
        # then be injected at turn 0 by the deployed tree and not by the repo tree.  The file
        # is chosen by measurement, not hardcoded, so it survives a rule being re-scoped.
        promoted = tmp / "promoted"
        shutil.copytree(REPO_RULES, promoted)
        lazy_rel = next(
            (
                rel
                for rel in sorted(
                    p.relative_to(REPO_RULES).as_posix()
                    for p in REPO_RULES.rglob("*.md")
                )
                if rule_audit.parse_frontmatter(rule_audit.read_lf(REPO_RULES / rel))[0]
            ),
            None,
        )
        if lazy_rel is None:
            print("FAILED:r5_driftgate_redproof no paths-scoped rule found to promote")
            return 1
        (promoted / lazy_rel).write_text(
            "# frontmatter STRIPPED by a bad deploy\n", encoding="utf-8", newline="\n"
        )
        rc_e, out_e = run_gate(REPO_RULES, promoted)
        checks.append(("E rc==1 when the deployed copy changes load class", rc_e == 1))
        checks.append(
            (
                f"E names it as a LOAD CLASS divergence ({lazy_rel})",
                "LOAD CLASS divergence" in out_e and repr(lazy_rel) in out_e,
            )
        )

        # ---- D: fail closed on an empty walk ----------------------------------------
        empty_repo = tmp / "empty-repo"
        empty_repo.mkdir()
        rc_d, out_d = run_gate(empty_repo, mirror)
        checks.append(("D rc==1 on an empty repo tree", rc_d == 1))
        checks.append(("D says the detector is broken", "detector broken" in out_d))

    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'ok ' if ok else 'BAD'} {name}")
    if bad:
        print(f"FAILED:r5_driftgate_redproof {bad}")
        return 1
    print(
        f"SUCCESS:r5_driftgate_redproof {len(checks)}/{len(checks)} states forced; the ratchet "
        f"goes red in both directions against a {baseline_n}-file baseline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
