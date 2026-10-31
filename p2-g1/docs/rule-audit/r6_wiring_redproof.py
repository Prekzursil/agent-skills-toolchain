#!/usr/bin/env python3
"""RED-PROOF for the rule-audit reachability guard: drive the REAL suite to red.

WHY THIS EXISTS
---------------
``ci/tests/test_rule_audit_ci_wiring.py`` pins that ``.github/workflows/rule-audit.yml``
still invokes the lane's ten gates.  Its in-file controls feed the *predicate* a broken
document, which proves the predicate discriminates -- but it never proves that the SUITE,
run as a process by a runner, actually goes red when the workflow is genuinely gone from
the tree.  A guard that has only ever been seen green is indistinguishable from a no-op
(``rules/common/ci-hygiene.md`` section 1), and this program has shipped that exact shape
before.

So this script builds throwaway trees on disk, copies the real suite into each one, and
runs ``pytest`` against them as a subprocess -- real argv, real file reads, real exit code.

WHAT IT ASSERTS, and why each arm is not decoration
---------------------------------------------------
* **A / control (unmutated copy) must be GREEN.**  This is the arm that makes every other
  arm mean something.  If the harness itself were broken -- a bad copy, a missing file, a
  wrong REPO_ROOT -- every arm would go red and the script would "prove" the guard fires
  when in fact nothing was ever measured.  A is what separates those two hypotheses.
* **B / the whole workflow deleted** -- the headline regression, and the one the in-file
  controls can only simulate by passing ``""`` to a function.
* **C / the workflow kept but the blocking gate step removed** -- the subtler shape, where
  the file still exists so a "does it exist" check would pass.
* **D / quality.yml stops naming the suite** -- the guard leaves the push path, which is
  how it would silently stop protecting anything on the event this repo actually uses.
* **E / the push trigger removed** -- the workflow runs on PRs only, so a direct push to
  main carries no rule-audit gate at all.

Every arm asserts on the exit code AND on a NAMED violation string, so an arm cannot pass
because pytest happened to fail for an unrelated reason (a syntax error, a missing import).

THE TREE IS SYNTHESIZED, NOT THE LIVE REPO.  Nothing here mutates a tracked file: each arm
gets its own temp directory.  ``REPO_ROOT`` in the suite is ``parents[2]`` of the test
file, so placing the copy at ``<tmp>/ci/tests/`` makes ``<tmp>`` the repo root and every
path the suite reads resolves inside the throwaway tree.

Run::

    python docs/rule-audit/r6_wiring_redproof.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

SUITE_REL = pathlib.PurePosixPath("ci/tests/test_rule_audit_ci_wiring.py")
WF_DIR_REL = pathlib.PurePosixPath(".github/workflows")

# Everything the suite reads. Copied verbatim so an arm mutates a COPY, never the tree.
#
# The gate DIRECTORY, not just ci_gate.py: the suite asserts that every script CI_PLAN
# names exists on disk, so a tree holding only ci_gate.py makes the control arm fail for a
# reason that has nothing to do with the wiring. That is not hypothetical -- the first run
# of this script failed exactly there, and the control arm is the only thing that
# distinguished "the guard fires" from "my harness is broken".
SOURCES = [
    SUITE_REL,
    WF_DIR_REL / "rule-audit.yml",
    WF_DIR_REL / "quality.yml",
    WF_DIR_REL / "skill-dual-write.yml",
]
GATE_DIR_REL = pathlib.PurePosixPath("docs/rule-audit")

GATE_CMD = "run: python docs/rule-audit/ci_gate.py"
THIS_SUITE_CMD = "python -m pytest ci/tests/test_rule_audit_ci_wiring.py -q"


def _read(path: pathlib.Path) -> str:
    # newline="" so a CRLF working-tree file round-trips byte-for-byte; reading without it
    # rewrites line endings and turns a one-line mutation into a whole-file rewrite.
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path: pathlib.Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _drop_exact_lines(text: str, target: str) -> str:
    """Remove every line whose stripped form equals ``target``. Fails closed."""
    lines = text.splitlines(keepends=True)
    kept = [ln for ln in lines if ln.strip() != target]
    if len(kept) == len(lines):
        raise SystemExit(f"FAILED:r6_wiring_redproof mutation found no line {target!r}")
    return "".join(kept)


def build_tree(root: pathlib.Path) -> None:
    for rel in SOURCES:
        src = REPO / rel
        if not src.is_file():
            raise SystemExit(f"FAILED:r6_wiring_redproof missing source {src}")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    gate_src = REPO / GATE_DIR_REL
    gate_dst = root / GATE_DIR_REL
    gate_dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for script in sorted(gate_src.glob("*.py")):
        shutil.copy2(script, gate_dst / script.name)
        copied += 1
    # Fail closed on an empty walk: "no gate scripts" and "the glob broke" look identical.
    if copied < 8:
        raise SystemExit(
            f"FAILED:r6_wiring_redproof copied only {copied} gate scripts from {gate_src}"
        )


def run_suite(root: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(root / SUITE_REL),
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def arm(label: str, mutate, *, want_red: bool, needle: str | None) -> bool:
    """Run one arm. Returns True if it behaved as required."""
    with tempfile.TemporaryDirectory(prefix="r6-wiring-") as tmp:
        root = pathlib.Path(tmp)
        build_tree(root)
        if mutate is not None:
            mutate(root)
        rc, out = run_suite(root)

    red = rc != 0
    ok = red == want_red
    if ok and want_red and needle is not None:
        ok = needle in out
    state = "RED" if red else "GREEN"
    want = "RED" if want_red else "GREEN"
    detail = "" if ok else f"   <-- wanted {want}"
    if not ok and want_red and needle is not None and red:
        detail = f"   <-- went red, but not for {needle!r} (wrong reason)"
    print(f"  [{'ok' if ok else 'XX'}] {label:<46} {state:<5} rc={rc}{detail}")
    if not ok:
        tail = "\n".join(out.strip().splitlines()[-6:])
        print(f"        tail: {tail}")
    return ok


# ------------------------------------------------------------------ the mutations
def _delete_workflow(root: pathlib.Path) -> None:
    (root / WF_DIR_REL / "rule-audit.yml").unlink()


def _delete_gate_step(root: pathlib.Path) -> None:
    path = root / WF_DIR_REL / "rule-audit.yml"
    _write(path, _drop_exact_lines(_read(path), GATE_CMD))


def _unname_suite_in_quality(root: pathlib.Path) -> None:
    path = root / WF_DIR_REL / "quality.yml"
    _write(path, _drop_exact_lines(_read(path), THIS_SUITE_CMD))


def _drop_push_trigger(root: pathlib.Path) -> None:
    path = root / WF_DIR_REL / "rule-audit.yml"
    text = _read(path)
    mutated = text.replace("  push:\n    branches: [main]\n", "", 1)
    if mutated == text:
        mutated = text.replace("  push:\r\n    branches: [main]\r\n", "", 1)
    if mutated == text:
        raise SystemExit("FAILED:r6_wiring_redproof could not remove the push trigger")
    _write(path, mutated)


def main() -> int:
    print("== r6 wiring red-proof: the reachability guard, driven as a process ==")
    results = [
        # The control FIRST. Every red below is meaningless if this one is not green.
        arm("A control: unmutated copy", None, want_red=False, needle=None),
        arm(
            "B rule-audit.yml DELETED",
            _delete_workflow,
            want_red=True,
            needle="workflow-missing",
        ),
        arm(
            "C gate step removed, workflow kept",
            _delete_gate_step,
            want_red=True,
            needle="gate-command-missing",
        ),
        arm(
            "D quality.yml stops naming the suite",
            _unname_suite_in_quality,
            want_red=True,
            needle="wiring-suite-not-named",
        ),
        arm(
            "E push trigger removed",
            _drop_push_trigger,
            want_red=True,
            needle="not-push-triggered",
        ),
    ]
    good = sum(1 for r in results if r)
    if good != len(results):
        print(f"FAILED:r6_wiring_redproof {good}/{len(results)} arms behaved")
        return 1
    print(
        f"SUCCESS:r6_wiring_redproof {good}/{len(results)} arms behaved; the guard goes "
        "red when rule-audit.yml is deleted, weakened, unnamed or de-triggered"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
