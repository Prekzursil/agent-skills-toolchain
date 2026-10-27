"""I1: prove the NEW ci/tests suite kills the two P4 mutants that the tool's own --self-test
lets live.

Both the independent audit and the adversarial verify measured M5 and M6 SURVIVING
`scripts/deploy-skills-daily.py --self-test`.  The claim under test here is narrow and
falsifiable: the pytest suite added in ci/tests kills them, and the built-in self-test still
does not.

Method: build a throwaway repo skeleton in a temp dir at the SAME depth the real tool assumes
(`<td>/scripts/deploy-skills-daily.py`, `<td>/ci/...`), drop in ONE mutation, then run two
mechanically different probes against it:

    probe A   the tool's own `--self-test`                 (the pre-existing gate)
    probe B   `pytest <td>/ci/tests/test_deploy_skills_daily.py`  (the new gate)

A CONTROL row runs both probes against an UNMUTATED copy.  If the control is not green on both
probes the harness is measuring its own sandbox, not the mutation, and no row may be read.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
SRC = REPO / "scripts" / "deploy-skills-daily.py"

# Only the behavioural tests: the wiring/reachability ones read the real repo and would fail in
# the sandbox for reasons that have nothing to do with the mutation.
KSELECT = "not workflow and not agent_facing"

M5_OLD = (
    "    if args.apply:\n"
    '        print("running --self-test before any write (P4)")\n'
    "        if self_test() != EXIT_OK:\n"
    '            print("FAILED:deploy-skills-daily self-test did not pass; refusing to deploy")\n'
    "            return EXIT_REFUSED\n"
    "        print()\n"
)
M5_NEW = (
    '    if args.apply:\n        print("running --self-test before any write (P4)")\n'
)

M6_OLD = (
    "    return deploy(source, target, apply=args.apply, only=set(args.only) or None)\n"
)
M6_NEW = "    return deploy(source, target, apply=True, only=set(args.only) or None)\n"

P2_OLD = (
    "    if not (target / skill).is_dir():\n"
    '        return "P2 would resurrect a skill absent from the curated tree"\n'
)
P2_NEW = '    if False:\n        return "disabled"\n'

MUTANTS: list[tuple[str, str | None, str | None]] = [
    ("CONTROL unmutated copy (must be GREEN on both probes)", None, None),
    ("M5 --apply no longer runs the self-test first", M5_OLD, M5_NEW),
    ("M6 dry-run default flipped (apply forced True)", M6_OLD, M6_NEW),
    ("M2 P2 skill-existence guard removed", P2_OLD, P2_NEW),
]


def build_sandbox(td: Path, text: str) -> Path:
    (td / "scripts").mkdir(parents=True, exist_ok=True)
    tool = td / "scripts" / "deploy-skills-daily.py"
    tool.write_text(text, encoding="utf-8")
    shutil.copytree(
        REPO / "ci", td / "ci", ignore=shutil.ignore_patterns("__pycache__")
    )
    return tool


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
    )
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode, (out[-1] if out else "")


def main() -> int:
    base = SRC.read_text(encoding="utf-8")
    rows = []
    for name, old, new in MUTANTS:
        text = base
        if old is not None:
            if old not in text:
                rows.append(
                    (name, "SKIP", "SKIP", "anchor not found -- mutation not applied")
                )
                continue
            text = text.replace(old, new or "")
        with tempfile.TemporaryDirectory() as tdname:
            td = Path(tdname)
            tool = build_sandbox(td, text)
            rc_a, tail_a = run([sys.executable, str(tool), "--self-test"], td)
            rc_b, tail_b = run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(td / "ci" / "tests" / "test_deploy_skills_daily.py"),
                    "-q",
                    "-k",
                    KSELECT,
                    "-p",
                    "no:cacheprovider",
                ],
                td,
            )
        a = "GREEN" if rc_a == 0 else "RED"
        b = "GREEN" if rc_b == 0 else "RED"
        rows.append((name, a, b, tail_b[:110]))

    print(f"{'probe A --self-test':>20} | {'probe B new pytest':>19} | mutant")
    print("-" * 96)
    for name, a, b, tail in rows:
        print(f"{a:>20} | {b:>19} | {name}")
        if tail:
            print(f"{'':>20} | {'':>19} |   pytest tail: {tail}")

    control = rows[0]
    if control[1] != "GREEN" or control[2] != "GREEN":
        print(
            "\nFAILED:i1-p4-mutation the CONTROL is not green on both probes; "
            "the harness is measuring its sandbox, not the mutations"
        )
        return 1

    survivors_b = [r[0] for r in rows[1:] if r[2] != "RED"]
    survivors_a = [r[0] for r in rows[1:] if r[1] != "RED"]
    print(
        f"\nprobe A (tool --self-test) survivors: {len(survivors_a)}/{len(rows) - 1} "
        f"{survivors_a}"
    )
    print(
        f"probe B (new ci/tests suite) survivors: {len(survivors_b)}/{len(rows) - 1} "
        f"{survivors_b}"
    )
    if survivors_b:
        print(
            f"\nFAILED:i1-p4-mutation new suite left {len(survivors_b)} mutant(s) alive"
        )
        return 1
    print(
        "\nSUCCESS:i1-p4-mutation new suite killed every mutant; "
        f"the pre-existing self-test left {len(survivors_a)} alive"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
