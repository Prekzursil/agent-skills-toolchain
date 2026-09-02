#!/usr/bin/env python
"""_b10_ci_proof.py -- will `.github/workflows/hook-audit.yml` be green on a runner?

Working-tree green is not clone green and not CI green. This program has already shipped that
mistake (3,910 passed in a working tree vs 31 collection errors from a fresh clone of the same
commit), so every wired command is executed HERE the way the runner will execute them:

  * from a FRESH CLONE of HEAD -- so anything living only in this dirty worktree is absent,
  * with HOME and USERPROFILE redirected to a nonexistent directory -- so `~/.claude`, which
    the runner does not have, is not silently supplying an answer,
  * capturing each child's REAL exit code, never through a pipe (a pipeline reports the LAST
    command's status, which turns a red gate green).

CONTROLS, because green commands prove nothing on their own:
  C1 REDIRECTION BITES -- `Path.home()` must MOVE and `<home>/.claude` must report False inside
     the clone. A redirection that does not take effect makes every later "runner-safe" claim
     meaningless.
  C2 THE GATE CAN STILL FAIL IN THE CLONE -- one citation's expected value is mutated in the
     clone and the gate must go RED, then the file is restored and it must go GREEN again.
     Without this, "the gate passed on a runner" is indistinguishable from "the gate cannot
     fail on a runner" -- which is precisely the shape of the near-miss discovered while
     writing the workflow.

     THAT PARENTHETICAL SAID "zero tests collected, exit 0" UNTIL 2026-08-14 AND WAS FALSE.
     `pytest` on a standalone script exits **5** (EXIT_NOTESTSCOLLECTED), reproduced three
     times across two invocation forms with a control returning 0 in the same shell. The
     consequence inverts: the naive wiring would have turned CI RED without executing the
     cases, not silently green. Kept and corrected rather than swapped, because this exact
     sentence was already refuted once in `hook-audit.yml` and survived here.
  C3 THE CLONE IS REAL -- every wired file must exist in it.
  C4 WIRED MATCHES THE WORKFLOW -- the hand-maintained copy above must not have drifted from
     the steps the runner actually executes; unreadable workflow fails closed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)

WIRED = [
    ["python", "command-center/hook-audit/check_citations.py", "--self-test"],
    ["python", "command-center/hook-audit/test_citation_gate.py"],
    ["python", "command-center/hook-audit/check_citations.py"],
    [
        "python",
        "-m",
        "pytest",
        "command-center/hook-audit/test_hook_predeploy_gate.py",
        "-q",
    ],
    [
        "python",
        "-m",
        "pytest",
        "command-center/hook-audit/test_failpath_evidence.py",
        "-q",
    ],
]
NEEDED = [
    "command-center/hook-audit/check_citations.py",
    "command-center/hook-audit/test_citation_gate.py",
    "command-center/hook-audit/test_hook_predeploy_gate.py",
    "command-center/hook-audit/test_failpath_evidence.py",
    "command-center/hook-audit/hook_predeploy_gate.py",
]
WORKFLOW = REPO / ".github" / "workflows" / "hook-audit.yml"


def workflow_run_steps() -> list[str] | None:
    """The `run:` lines the workflow actually executes, for the C4 drift control.

    WIRED above is a hand-maintained COPY of the workflow. This lane has already been bitten
    by a hardcoded list standing in for the real set: `_r4_blobgate.py` walked an 8-entry
    PATHS list, so a file outside it read as clean rather than as unseen, and that is how a
    CI-red file stayed invisible for two commits. A copy is acceptable only if something
    notices when it stops matching, so C4 compares the two and fails closed if it cannot read
    the workflow at all.
    """
    try:
        text = WORKFLOW.read_text(encoding="utf-8")
    except OSError:
        return None
    steps = [
        line.split("run:", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().startswith("run:")
    ]
    return steps or None


def runner_env(fake_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    return env


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    return p.returncode, (tail[-1][:200] if tail else "")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="b10ci_"))
    clone = tmp / "clone"
    fake_home = tmp / "nohome"
    out: dict = {"probe": "_b10_ci_proof.py", "controls": {}, "wired": []}
    try:
        subprocess.run(
            ["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(clone)],
            check=True,
            capture_output=True,
        )
        out["clone_head"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()[:12]

        env = runner_env(fake_home)
        rc, home_line = run(
            [
                "python",
                "-c",
                "from pathlib import Path; print(Path.home(), (Path.home()/'.claude').exists())",
            ],
            clone,
            env,
        )
        c1 = (
            rc == 0
            and str(fake_home) in home_line
            and home_line.strip().endswith("False")
        )
        out["controls"]["C1_redirection_bites"] = c1
        out["controls"]["C1_observed"] = home_line

        c3 = all((clone / n).exists() for n in NEEDED)
        out["controls"]["C3_clone_has_wired_files"] = c3
        if not (c1 and c3):
            print(f"CONTROL C1 redirection bites = {c1}  ({home_line})")
            print(f"CONTROL C3 clone has files   = {c3}")
            print("FAILED:ci-proof control failed -- no runner verdict published")
            return 2

        for cmd in WIRED:
            rc, tail = run(cmd, clone, env)
            out["wired"].append({"cmd": " ".join(cmd[1:]), "rc": rc, "tail": tail})
            print(f"rc={rc}  {' '.join(cmd[1:])}\n      {tail}")

        # C2: the gate must still be able to FAIL inside the clone.
        #
        # THE ANCHOR IS DERIVED, NOT HARDCODED, and that is a fix rather than a style
        # choice. This control used to mutate the literal `id=R2-fmt-files ... value=2595`
        # in BUILD-R2.md. That citation was introduced in `b0cbfe28`, re-pointed in
        # `b99ee2e7` ("a pinned count that legitimately moves") and DELETED outright in
        # `01febbed` -- three commits of the same lane that wrote this probe. From
        # `01febbed` onward the anchor could never match, so the probe failed closed with
        # "mutation anchor not found" and stopped being usable as a runner-safety proof.
        # It failed closed rather than reporting a false green, which is the correct
        # direction, but a control anchored to content that legitimately moves is a
        # maintenance trap of exactly the kind this audit keeps finding.
        #
        # So: find ANY citation carrying a numeric `value=` in ANY scanned doc at run time
        # and mutate that. The control now survives any document being rewritten, and it
        # still fails closed when there is nothing to mutate.
        cite_num = re.compile(r"(<!--\s*cite:[^>]*?\bvalue=)(\d+)(\s*-->)")
        doc = None
        original = mutated = ""
        for cand in sorted((clone / "docs" / "hook-audit").glob("*.md")):
            text = cand.read_text(encoding="utf-8")
            m = cite_num.search(text)
            if not m:
                continue
            # Mutate to a value the evidence cannot possibly hold.
            new_val = str(int(m.group(2)) + 987654)
            doc = cand
            original = text
            mutated = text[: m.start(2)] + new_val + text[m.end(2) :]
            out["controls"]["C2_anchor"] = (
                f"{cand.name}: {m.group(0)[:60]} -> {new_val}"
            )
            break
        if doc is None or mutated == original:
            out["controls"]["C2_gate_can_fail_in_clone"] = False
            print("CONTROL C2 = FAIL (no numeric citation found to mutate)")
            print("FAILED:ci-proof could not mutate a citation -- control inert")
            return 2
        doc.write_text(mutated, encoding="utf-8", newline="")
        rc_hot, tail_hot = run(WIRED[2], clone, env)
        doc.write_text(original, encoding="utf-8", newline="")
        rc_cold, _ = run(WIRED[2], clone, env)
        c2 = rc_hot != 0 and rc_cold == 0
        out["controls"]["C2_gate_can_fail_in_clone"] = c2
        out["controls"]["C2_rc_mutated"] = rc_hot
        out["controls"]["C2_rc_restored"] = rc_cold
        print(f"CONTROL C1 redirection bites          = {c1}")
        print(
            f"CONTROL C2 gate goes RED when mutated = {c2} (rc {rc_hot} mutated / {rc_cold} restored)"
        )
        print(f"CONTROL C3 clone has the wired files  = {c3}")
        print(f"      C2 mutated-run tail: {tail_hot}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # C4: WIRED is a hand-maintained copy of the workflow; fail closed if it has drifted.
    steps = workflow_run_steps()
    if steps is None:
        c4 = False
        out["controls"]["C4_detail"] = "workflow unreadable"
    else:
        missing = [
            " ".join(c) for c in WIRED if not any(" ".join(c[1:]) in s for s in steps)
        ]
        extra = [
            s
            for s in steps
            if s.startswith("python") and not any(" ".join(c[1:]) in s for c in WIRED)
        ]
        c4 = not missing and not extra
        out["controls"]["C4_detail"] = {
            "missing_from_workflow": missing,
            "not_in_WIRED": extra,
        }
    out["controls"]["C4_wired_list_matches_workflow"] = c4
    print(f"CONTROL C4 WIRED matches the workflow   = {c4}")

    all_green = all(w["rc"] == 0 for w in out["wired"])
    out["all_wired_commands_green"] = all_green
    out["verdict"] = (
        "RUNNER-GREEN"
        if (all_green and out["controls"]["C2_gate_can_fail_in_clone"] and c4)
        else "RUNNER-RED"
    )
    (HERE / "B10-CI-PROOF.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    if out["verdict"] != "RUNNER-GREEN":
        print(f"FAILED:ci-proof {out['verdict']}")
        return 1
    print(
        f"SUCCESS:ci-proof {len(WIRED)}/{len(WIRED)} wired commands green in a fresh clone "
        f"at {out['clone_head']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
