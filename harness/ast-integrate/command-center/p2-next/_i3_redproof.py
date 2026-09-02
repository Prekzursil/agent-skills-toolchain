r"""RED-PROOF for the P2NEXT rail-count wiring, in a throwaway FULL CLONE.

The claim under test is not "the gate passes today". It is the integration claim:

    without this wiring the defect ships GREEN, and with it the build goes RED.

So every leg below is executed twice -- once against the known-GOOD tree and once against a
known-BROKEN one -- and the pre-existing CI gates are run against the SAME injected defect to show
they are blind to it. A gate that is redundant with an existing check buys nothing; a gate that has
only ever been seen passing is indistinguishable from a no-op.

Four injections, all drawn from what actually happened rather than invented:

  INJ-A  the OWNING doc rots while the JSON stays right -- the headline goes back to "43 blocked
         units". This is literally the state main was in before this lane: the artifact said
         41 of 51, the page said 43 of 47, and nothing compared them.
  INJ-B  a RECEIPT moves and no published copy follows -- `failure.blocked_on` is rewritten so a
         unit crosses the split. The receipt stays BLOCKED, stays schema-valid and claims no
         completion, so the delivery-predicate family has nothing to fire on. This is the round-1
         defect's exact mechanism.
  INJ-C  a receipt forges SUCCESS. Kept even though the PRE-EXISTING unitgate also catches it,
         because a red-proof built only on defects another gate already catches would prove the
         new gate redundant rather than necessary. Recorded, not counted as necessity.
  INJ-D  the CITING doc rots while the owning doc stays right. E2E-WAVE-STATUS.md states that its
         rail figure is anchored at CROSS-VENDOR-RAIL-STATUS.md:1, so fixing only the anchor moves
         the stale number one file over instead of retiring it.

NOTHING IS WRITTEN TO THE REAL REPO. The clone lives under the system temp dir and is deleted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "command-center" / "p2-next" / "I3-REDPROOF.json"

#: The files this lane adds or changes. Copied into the clone and committed there so the
#: `--basis committed` derivation sees them, exactly as CI will after this lane's commit.
LANE_FILES = [
    "command-center/p2-next/rail_count_gate.py",
    "command-center/p2-next/vendor_satisfiability.py",
    "command-center/CROSS-VENDOR-RAIL-STATUS.md",
    "command-center/E2E-WAVE-STATUS.md",
    ".github/workflows/p2next-rail-count.yml",
]

#: The four commands the new workflow runs, in order.
NEW_GATE = [
    ["python", "command-center/p2-next/rail_count_gate.py", "--self-test"],
    ["python", "command-center/p2-next/rail_count_gate.py"],
    [
        "python",
        "command-center/p2-next/vendor_satisfiability.py",
        "--basis",
        "committed",
    ],
    ["python", "command-center/p2-next/split_review_gate.py", "--basis", "committed"],
]

#: Pre-existing CI checks that a change to a command-center doc or receipt could plausibly reach.
#: If these stay green under the same injection, the new gate is not redundant.
PRE_EXISTING = [
    ["python", "command-center/slop-report/check_published_commands.py"],
    ["python", "tools/measure-guard/unitgate.py"],
]


def run(cmd: list[str], cwd: Path) -> dict:
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    tail = (p.stdout + p.stderr).strip().splitlines()
    return {
        "cmd": " ".join(cmd),
        "rc": p.returncode,
        "tail": tail[-8:] if tail else [],
    }


def bash_charter(cwd: Path) -> dict:
    for c in (r"C:\Program Files\Git\bin\bash.exe", "/usr/bin/bash"):
        if os.path.isfile(c):
            return run([c, ".quality/charter_check.sh"], cwd)
    return {"cmd": "charter_check.sh", "rc": -1, "tail": ["no bash found"]}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p2next-redproof-"))
    clone = tmp / "clone"
    result: dict = {
        "what_is_being_proven": (
            "the P2NEXT rail-count wiring goes RED on a defect the pre-existing CI ships GREEN"
        ),
        "clone": str(clone),
        "legs": {},
    }
    try:
        # Windows-style path on purpose: MSYS rewrites a /c/... argument and the clone silently
        # does not happen (windows-shell.md 11).
        r = run(["git", "clone", "--no-hardlinks", "-q", str(REPO), str(clone)], tmp)
        if r["rc"] != 0:
            print(f"FAILED:redproof clone {r}")
            return 1
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=clone,
            capture_output=True,
            text=True,
        ).stdout.strip()
        result["clone_head"] = head

        for rel in LANE_FILES:
            dst = clone / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / rel, dst)
        subprocess.run(["git", "add", "--"] + LANE_FILES, cwd=clone, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-m",
                "lane files under test",
            ],
            cwd=clone,
            check=True,
        )
        result["clone_head_with_lane_files"] = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=clone,
            capture_output=True,
            text=True,
        ).stdout.strip()

        doc = clone / "command-center" / "CROSS-VENDOR-RAIL-STATUS.md"
        pristine = doc.read_text(encoding="utf-8")

        # ---- leg 1: GOOD state. Everything must be green, or a later red proves nothing. ------
        result["legs"]["good"] = {
            "new_gate": [run(c, clone) for c in NEW_GATE],
            "pre_existing": [run(c, clone) for c in PRE_EXISTING]
            + [bash_charter(clone)],
        }

        # ---- leg 2: INJ-A, the doc rots ------------------------------------------------------
        assert "gates 42 blocked units" in pristine, (
            "headline anchor moved; fix this probe"
        )
        doc.write_text(
            pristine.replace("gates 42 blocked units", "gates 43 blocked units"),
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-a",
                "-m",
                "INJ-A doc rots back to 43",
            ],
            cwd=clone,
            check=True,
        )
        result["legs"]["inj_a_doc_rots"] = {
            "injection": "CROSS-VENDOR-RAIL-STATUS.md headline 42 -> 43 blocked units, committed",
            "new_gate": [run(c, clone) for c in NEW_GATE],
            "pre_existing": [run(c, clone) for c in PRE_EXISTING]
            + [bash_charter(clone)],
        }
        # Back to the good doc before the second injection, so INJ-B is measured alone.
        doc.write_text(pristine, encoding="utf-8", newline="\n")
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-a",
                "-m",
                "restore the good doc",
            ],
            cwd=clone,
            check=True,
        )

        # ---- leg 3: INJ-B, a receipt's blocked_on is rewritten -------------------------------
        # This is the round-1 mechanism EXACTLY, not an invented mutation: editing
        # `failure.blocked_on` so it no longer names the refuter vendor moves the unit from
        # RAIL_BLOCKED to SATISFIABLE. The receipt stays BLOCKED, claims no completion and stays
        # schema-valid, so nothing in the delivery-predicate family has anything to fire on -- the
        # published 42 is simply wrong from that commit onward. Chosen over "flip a receipt to
        # SUCCESS" precisely because that louder mutation IS caught by unitgate (measured, and
        # kept below as INJ-C), and a red-proof that only uses a defect another gate already
        # catches proves the new gate is redundant rather than necessary.
        art = json.loads(
            (clone / "command-center/p2-next/VENDOR-SATISFIABILITY.json").read_text(
                encoding="utf-8"
            )
        )
        victim = next(u for u in art["units"] if u["verdict"] == "SATISFIABLE_NOW")
        vpath = clone / victim["output_path"]
        rec = json.loads(vpath.read_text(encoding="utf-8"))
        rec["failure"]["blocked_on"] = (
            "one cross-vendor refuter re-deriving the finding from the raw tree"
        )
        vpath.write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-a",
                "-m",
                "INJ-B blocked_on no longer names the refuter vendor",
            ],
            cwd=clone,
            check=True,
        )
        # EFFECTIVENESS CONTROL on the injection itself. An injection that does not move the
        # derivation cannot prove anything, and a leg can otherwise "pass" on an unrelated red --
        # measured: an earlier INJ-B left the verdict unchanged and the leg still scored OK
        # because a different command in the same list was failing for its own reason.
        derived_after = run(
            [
                "python",
                "-c",
                "import importlib.util,pathlib,collections;"
                "s=importlib.util.spec_from_file_location('v',"
                "'command-center/p2-next/vendor_satisfiability.py');"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "r=m.load_units('committed');"
                "print('DERIVED',len(r),collections.Counter(x['verdict'] for x in r))",
            ],
            clone,
        )
        result["legs"]["inj_b_receipt_moves"] = {
            "injection": f"{victim['id']} ({victim['output_path']}) failure.blocked_on rewritten "
            f"to demand a cross-vendor refuter -- still BLOCKED, still schema-valid, "
            f"claims no completion, but the unit moves SATISFIABLE -> RAIL_BLOCKED so "
            f"the published 42/10 is wrong. No doc was touched.",
            "derivation_after_injection": derived_after["tail"],
            "new_gate": [run(c, clone) for c in NEW_GATE],
            "pre_existing": [run(c, clone) for c in PRE_EXISTING]
            + [bash_charter(clone)],
        }

        # ---- leg 4: INJ-C, the LOUD mutation, kept to show where the new gate is redundant ---
        subprocess.run(
            ["git", "checkout", "-q", "HEAD~1", "--", victim["output_path"]],
            cwd=clone,
            check=True,
        )
        rec = json.loads((clone / victim["output_path"]).read_text(encoding="utf-8"))
        rec["state"] = "SUCCESS"
        (clone / victim["output_path"]).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-a",
                "-m",
                "INJ-C a blocked receipt flips to SUCCESS",
            ],
            cwd=clone,
            check=True,
        )
        result["legs"]["inj_c_forged_success"] = {
            "injection": f"{victim['id']} state BLOCKED -> SUCCESS. Expected to be caught by the "
            f"PRE-EXISTING unitgate as well; recorded so the necessity claim is "
            f"scoped to INJ-A and INJ-B rather than overstated.",
            "new_gate": [run(c, clone) for c in NEW_GATE],
            "pre_existing": [run(c, clone) for c in PRE_EXISTING]
            + [bash_charter(clone)],
        }

        # ---- leg 5: INJ-D, the CITING doc rots while the owning doc stays right ---------------
        # The stale number's actual escape route. E2E-WAVE-STATUS.md states that its rail figure
        # is anchored at CROSS-VENDOR-RAIL-STATUS.md:1, so fixing only the anchor moves the wrong
        # number one file over rather than retiring it.
        subprocess.run(
            ["git", "checkout", "-q", "HEAD~2", "--", victim["output_path"]],
            cwd=clone,
            check=True,
        )
        cite = clone / "command-center" / "E2E-WAVE-STATUS.md"
        cite_txt = cite.read_text(encoding="utf-8")
        assert "gates 42 blocked units" in cite_txt, (
            "citing-doc anchor moved; fix this probe"
        )
        cite.write_text(
            cite_txt.replace("gates 42 blocked units", "gates 43 blocked units"),
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=redproof@local",
                "-c",
                "user.name=redproof",
                "commit",
                "-q",
                "-a",
                "-m",
                "INJ-D the citing status doc rots back to 43",
            ],
            cwd=clone,
            check=True,
        )
        result["legs"]["inj_d_citing_doc_rots"] = {
            "injection": "E2E-WAVE-STATUS.md rail line 42 -> 43 while CROSS-VENDOR-RAIL-STATUS.md "
            "stays correct; the receipts are restored so this is the ONLY defect",
            "new_gate": [run(c, clone) for c in NEW_GATE],
            "pre_existing": [run(c, clone) for c in PRE_EXISTING]
            + [bash_charter(clone)],
        }

        # ---- verdict -------------------------------------------------------------------------
        def gate_rc(leg: str) -> list[int]:
            return [s["rc"] for s in result["legs"][leg]["new_gate"]]

        def pre_rc(leg: str) -> list[int]:
            return [s["rc"] for s in result["legs"][leg]["pre_existing"]]

        checks = {
            "good: every new-gate command exits 0": all(
                rc == 0 for rc in gate_rc("good")
            ),
            "good: every pre-existing check exits 0": all(
                rc == 0 for rc in pre_rc("good")
            ),
            "INJ-A: rail_count_gate itself goes RED": (
                result["legs"]["inj_a_doc_rots"]["new_gate"][1]["rc"] != 0
            ),
            "INJ-A: pre-existing CI stays GREEN (blind)": all(
                rc == 0 for rc in pre_rc("inj_a_doc_rots")
            ),
            # Named to the SPECIFIC command, not "any red in the list". The list also contains
            # the producer check, so an "any" test can be satisfied by a failure that has nothing
            # to do with the injection -- which is exactly what happened on the previous run.
            "INJ-B: rail_count_gate itself goes RED": (
                result["legs"]["inj_b_receipt_moves"]["new_gate"][1]["rc"] != 0
            ),
            "INJ-B: the injection actually moved the derivation": any(
                "DERIVED 52" not in t
                for t in result["legs"]["inj_b_receipt_moves"][
                    "derivation_after_injection"
                ]
                if t.startswith("DERIVED")
            )
            or any(
                "'RAIL_BLOCKED': 43" in t
                for t in result["legs"]["inj_b_receipt_moves"][
                    "derivation_after_injection"
                ]
            ),
            "INJ-B: pre-existing CI stays GREEN (blind)": all(
                rc == 0 for rc in pre_rc("inj_b_receipt_moves")
            ),
            "INJ-C: the new gate goes RED too": any(
                rc != 0 for rc in gate_rc("inj_c_forged_success")
            ),
            "INJ-D: rail_count_gate itself goes RED on the CITING doc": (
                result["legs"]["inj_d_citing_doc_rots"]["new_gate"][1]["rc"] != 0
            ),
            "INJ-D: pre-existing CI stays GREEN (blind)": all(
                rc == 0 for rc in pre_rc("inj_d_citing_doc_rots")
            ),
        }
        # NOT a pass/fail condition -- recorded so the necessity claim stays scoped. If unitgate
        # also catches INJ-C, the honest statement is "necessary for the count-moving edits",
        # not "the only thing standing between main and this defect class".
        result["inj_c_pre_existing_also_red"] = any(
            rc != 0 for rc in pre_rc("inj_c_forged_success")
        )
        result["checks"] = checks
        result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
        OUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        for k, v in checks.items():
            print(f"  [{'OK' if v else 'XX'}] {k}")
        for leg in (
            "good",
            "inj_a_doc_rots",
            "inj_b_receipt_moves",
            "inj_c_forged_success",
            "inj_d_citing_doc_rots",
        ):
            print(
                f"  {leg:22} new_gate rc={gate_rc(leg)}  pre_existing rc={pre_rc(leg)}"
            )
        print(
            "  scope note: INJ-C is also caught by the pre-existing unitgate = "
            f"{result['inj_c_pre_existing_also_red']}"
        )
        print(f"  wrote {OUT.relative_to(REPO)}")
        if result["verdict"] != "PASS":
            print("FAILED:redproof the wiring is not proven")
            return 1
        print(
            "SUCCESS:redproof the wiring goes red on a defect the pre-existing CI ships green"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
