"""INTEGRATE / step I3 -- prove the wiring has teeth, in a fresh LF clone.

The claim under test is NOT "the gate passes". A gate that has never gone red is
indistinguishable from a no-op, and a gate whose red is already produced by some OTHER CI
step adds nothing. So five controls, and T3 is the one that decides whether the
integration was worth wiring:

  T1  clone at HEAD, gate               -> expect rc 0 (green: it does not red main)
  T2  same clone + ONE injected NEW violation, gate
                                        -> expect rc 1 (red: it can fail)
  T3  the SAME injected violation, run every EXISTING gate that could plausibly see it
      (ruff check, ruff format --check at the CI pin, and the no-runtime-junk tracked-junk
      logic) BEFORE and AFTER the injection
                                        -> expect IDENTICAL verdicts, i.e. the pre-existing
                                           CI is blind to it. Without the new step the
                                           defect ships.
  T4  a baseline row that no longer violates
                                        -> expect rc 1 (the ratchet cannot drift into slack)
  T5  a corpus that yields zero commands, in a throwaway repo
                                        -> expect rc 1 (fail-closed, not silent-pass)

Working-tree green != clone green != CI green, so every reading here comes from a fresh
`git clone -c core.autocrlf=false -c core.eol=lf`, never from this worktree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SRC = "C:/Users/Prekzursil/source/ast-integrate"
GATE = "command-center/slop-report/check_published_commands.py"
BASELINE = "command-center/slop-report/published-commands-baseline.json"
OUT = os.path.join(SRC, "command-center/slop-report/_i3_integration_redproof.out.json")

# A tracked corpus document to inject into. Owned by this lane, so the injection never
# touches a sibling's bytes even inside a throwaway clone.
INJECT_INTO = "command-center/slop-report/SLOP-REPORT.md"


def run(cmd, cwd, timeout=1800):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def gate(cwd, *args):
    r = run([sys.executable, GATE, *args], cwd)
    return r


def ruff(cwd, *args):
    return run(["uvx", "ruff@0.15.17", *args], cwd)


def junk_gate(cwd):
    """The no-runtime-junk detection logic, re-implemented exactly as the workflow runs it."""
    bad_dirs = {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
    }
    bad_names = {"installed.json"}
    files = run(["git", "ls-files", "-z"], cwd)["out"].split("\0")
    v = [
        p
        for p in files
        if p and (bad_dirs.intersection(p.split("/")) or p.split("/")[-1] in bad_names)
    ]
    return {"rc": 1 if v else 0, "violations": len(v)}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="i3_redproof_")
    clone = os.path.join(tmp, "c")
    res: dict = {"src_head": run(["git", "rev-parse", "HEAD"], SRC)["out"].strip()}
    try:
        c = run(
            [
                "git",
                "clone",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "--single-branch",
                SRC,
                clone,
            ],
            tmp,
        )
        if c["rc"] != 0:
            raise SystemExit(f"clone failed: {c['err'][:400]}")
        res["clone_head"] = run(["git", "rev-parse", "HEAD"], clone)["out"].strip()

        # PRECONDITION, loud. The first run of this probe recorded a T1 "reading" against a
        # clone that contained neither the gate nor its baseline, because both were still
        # untracked -- python exited 2 and the result would have been filed as a number.
        # A missing instrument must abort, never produce a datum.
        for need in (GATE, BASELINE):
            if not (Path(clone) / need).is_file():
                raise SystemExit(
                    f"FAILED:i3 precondition -- {need} is NOT in the clone at "
                    f"{res['clone_head']}. Commit it before proving anything about it."
                )

        # EOL pin control: the clone must be LF, or every byte-level reading below is wrong.
        pyfiles = [
            p
            for p in run(["git", "ls-files"], clone)["out"].splitlines()
            if p.endswith(".py")
        ]
        crlf = sum(1 for p in pyfiles if b"\r\n" in (Path(clone) / p).read_bytes())
        res["control_eol"] = {
            "tracked_py": len(pyfiles),
            "with_crlf": crlf,
            "pass": crlf == 0,
        }

        # ---------------- T1: green at HEAD -------------------------------------------
        g1 = gate(clone)
        res["T1_gate_at_head"] = {
            "rc": g1["rc"],
            "tail": g1["out"].strip().splitlines()[-1:],
        }

        # ---------------- pre-injection readings of the EXISTING gates -----------------
        before = {
            "ruff_check_rc": ruff(clone, "check", ".")["rc"],
            "ruff_format_rc": ruff(clone, "format", "--check", ".")["rc"],
            "no_runtime_junk_rc": junk_gate(clone)["rc"],
        }
        res["T3_existing_gates_before"] = before

        # ---------------- T2: inject ONE new violation and commit ----------------------
        absent = f"command-center/slop-report/_zz_absent_{uuid.uuid4().hex}.py"
        doc = Path(clone) / INJECT_INTO
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + f"\n\nRegenerate with `python {absent}`.\n",
            encoding="utf-8",
            newline="\n",
        )
        run(
            [
                "git",
                "-c",
                "user.email=i3@local",
                "-c",
                "user.name=i3",
                "commit",
                "-q",
                "-m",
                "inject",
                "--",
                INJECT_INTO,
            ],
            clone,
        )
        res["injected_target"] = absent
        res["injection_committed"] = (
            run(["git", "status", "--porcelain"], clone)["out"].strip() == ""
        )

        g2 = gate(clone)
        res["T2_gate_after_injection"] = {
            "rc": g2["rc"],
            "names_the_target": absent in g2["out"],
            "says_NEW": "NEW published command" in g2["out"],
            "tail": g2["out"].strip().splitlines()[-4:],
        }

        # ---------------- T3: are the EXISTING gates blind to it? ----------------------
        after = {
            "ruff_check_rc": ruff(clone, "check", ".")["rc"],
            "ruff_format_rc": ruff(clone, "format", "--check", ".")["rc"],
            "no_runtime_junk_rc": junk_gate(clone)["rc"],
        }
        res["T3_existing_gates_after"] = after
        res["T3_existing_gates_blind"] = before == after
        res["T3_new_step_is_the_only_detector"] = (
            before == after and g1["rc"] == 0 and g2["rc"] == 1
        )

        # ---------------- T4: a stale baseline row must FAIL ---------------------------
        run(["git", "checkout", "-q", "--", INJECT_INTO], clone)
        run(
            [
                "git",
                "-c",
                "user.email=i3@local",
                "-c",
                "user.name=i3",
                "reset",
                "-q",
                "--hard",
                "HEAD~1",
            ],
            clone,
        )
        bp = Path(clone) / BASELINE
        data = json.loads(bp.read_text(encoding="utf-8"))
        data["entries"].append(
            {
                "citer": INJECT_INTO,
                "target": f"platform/lib/_zz_never_{uuid.uuid4().hex}.py",
                "owner": "T4 synthetic",
                "why": ["control"],
                "settling_action": ["control"],
            }
        )
        bp.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
        run(
            [
                "git",
                "-c",
                "user.email=i3@local",
                "-c",
                "user.name=i3",
                "commit",
                "-q",
                "-m",
                "stale",
                "--",
                BASELINE,
            ],
            clone,
        )
        g4 = gate(clone)
        res["T4_stale_baseline"] = {
            "rc": g4["rc"],
            "says_stale": "STALE BASELINE ROW" in g4["out"],
            "tail": g4["out"].strip().splitlines()[-3:],
        }

        # ---------------- T5: fail-closed on a corpus with zero commands ---------------
        mini = os.path.join(tmp, "mini")
        os.makedirs(os.path.join(mini, "command-center", "slop-report"))
        run(["git", "init", "-q"], mini)
        shutil.copy(os.path.join(SRC, GATE), os.path.join(mini, GATE))
        Path(mini, BASELINE).write_text(
            '{"entries": []}\n', encoding="utf-8", newline="\n"
        )
        Path(mini, "command-center", "EMPTY.md").write_text(
            "no commands here at all\n", encoding="utf-8", newline="\n"
        )
        run(["git", "add", "-A"], mini)
        run(
            [
                "git",
                "-c",
                "user.email=i3@local",
                "-c",
                "user.name=i3",
                "commit",
                "-q",
                "-m",
                "mini",
            ],
            mini,
        )
        g5 = gate(mini)
        res["T5_fail_closed_empty_corpus"] = {
            "rc": g5["rc"],
            "says_zero": "ZERO published commands" in g5["out"],
        }

        checks = {
            "control_eol_lf": res["control_eol"]["pass"],
            "T1_green_at_head": res["T1_gate_at_head"]["rc"] == 0,
            "T2_red_on_new_violation": res["T2_gate_after_injection"]["rc"] == 1,
            "T2_names_the_target": res["T2_gate_after_injection"]["names_the_target"],
            "T3_existing_ci_is_blind": res["T3_existing_gates_blind"],
            "T3_new_step_is_only_detector": res["T3_new_step_is_the_only_detector"],
            "T4_stale_row_fails": res["T4_stale_baseline"]["rc"] == 1
            and res["T4_stale_baseline"]["says_stale"],
            "T5_fail_closed": res["T5_fail_closed_empty_corpus"]["rc"] == 1
            and res["T5_fail_closed_empty_corpus"]["says_zero"],
        }
        res["checks"] = checks
        res["verdict"] = "INTEGRATION-PROVEN" if all(checks.values()) else "FAILED"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    print(f"\nwrote {OUT}")
    return 0 if res["verdict"] == "INTEGRATION-PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main())
