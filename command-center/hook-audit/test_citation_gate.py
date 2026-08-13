#!/usr/bin/env python3
r"""test_citation_gate.py -- both-states proof for the three round-3 holes in
`check_citations.py`. Standalone: `python test_citation_gate.py`.

Every case runs TWICE: once against the PRE-ROUND-3 gate (extracted from git history) and
once against the shipped one. A case only counts if the old gate behaves the way the defect
says it did -- otherwise "the new gate passes" would be indistinguishable from "the case
does not exercise anything". The old gate hardcoded an absolute repo path, so for H1/H3 it
is retargeted at the fixture by rewriting that one line; H2 is measured with the line left
exactly as it shipped, because pointing at the wrong repo IS the defect.

  H1 EVIDENCE-DRIFT   committed blob says 1.0, worktree says 2.0, document prints 2.0.
                      old: SUCCESS (reads the worktree only)   new: FAIL
  H2 WRONG REPO       run from a fixture that has its own docs.
                      old: reports on ast-integrate's documents (names a file the fixture
                      does not contain)                        new: reads the fixture
  H3 PER-DOC FLOOR    one annotated doc + one un-annotated doc.
                      old: SUCCESS (global floor satisfied)    new: FAIL
  CLEAN               blob == worktree == document              both: SUCCESS
                      (the control that stops "always red" from passing for H1/H3)
  UNTRACKED           evidence file never committed             new: FAIL (regression
                      guard on round 2's fix)
  BADROOT             HOOK_AUDIT_REPO with no docs/hook-audit    new: FAIL closed

ROUND 4 adds H4, the hole that let the flagship deliverable publish 7 unbacked numbers with
the gate GREEN: a table carrying no marker was not "unbacked", it was invisible. The control
here is the PRE-ROUND-4 gate (pinned blob), which must PASS the uncited table -- otherwise
"the new gate fails it" would not be evidence that anything changed. Four scoping controls
run beside it, because a rule that fails every table would also fail this one:

  H4 UNCITED TABLE    annotated doc + a measurement table with no marker
                      old: SUCCESS          new: FAIL naming UNCITED-MEASUREMENT-TABLE
  H4 CITED INSIDE     the same table with a cite: marker in a cell        new: SUCCESS
  H4 WAIVER           the same table under `uncited-table: reason=...`    new: SUCCESS
  H4 WAIVER NO REASON the same waiver with the reason omitted             new: FAIL
  H4 PROSE TABLE      a table with no measurement in it                   new: SUCCESS
  H4 CLASSIFIER       the gate's own both-states self-check               (True, True)
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
GATE = HERE / "check_citations.py"
REPO = HERE.parents[1]

DOC = """# fixture

<!-- cite: id=F1 file=E.json path=metrics.value value={v} -->
The measured value is {v}.
"""

CASES: list[tuple[str, bool]] = []


def sh(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def make_fixture(
    tmp: Path, *, doc_value: str, blob_value: str, commit: bool = True
) -> Path:
    """A throwaway repo shaped like this one: docs/hook-audit + command-center/hook-audit."""
    root = tmp / "fixture"
    (root / "docs" / "hook-audit").mkdir(parents=True)
    (root / "command-center" / "hook-audit").mkdir(parents=True)
    ev = root / "command-center" / "hook-audit" / "E.json"
    doc = root / "docs" / "hook-audit" / "DOC.md"
    ev.write_text(
        json.dumps({"metrics": {"value": float(blob_value)}}), encoding="utf-8"
    )
    doc.write_text(DOC.format(v=blob_value), encoding="utf-8")
    sh(root, "git", "init", "-q")
    sh(root, "git", "config", "user.email", "fixture@local")
    sh(root, "git", "config", "user.name", "fixture")
    sh(root, "git", "config", "core.autocrlf", "false")
    if commit:
        sh(root, "git", "add", "-A")
        sh(root, "git", "commit", "-q", "-m", "fixture baseline")
    if doc_value != blob_value:
        # the exact shape of C3: evidence regenerated AFTER it was committed, document
        # updated to match the new run -- consistent on this disk, wrong in a clone.
        ev.write_text(
            json.dumps({"metrics": {"value": float(doc_value)}}), encoding="utf-8"
        )
        doc.write_text(DOC.format(v=doc_value), encoding="utf-8")
    return root


# The pre-round-3 gate, pinned as a BLOB sha (`6f30510a~1:.../check_citations.py`), not as
# `HEAD`. The first version of this file read HEAD, which was correct for exactly as long as
# it took to commit the fix -- after that the "old gate" control WAS the new gate and three
# cases went red. That is round 2's blob-gate defect (`HEAD~1 HEAD` drifting onto a sibling
# lane's commit) reproduced inside the test written to catch that family. A blob sha cannot
# drift; the guard below makes sure it is still the unfixed file.
PRE_R3_GATE_BLOB = "66855eed4857e47a7ea03c35e52d89812a605eac"

# The gate as it shipped at the END of round 3 -- the control for H4. Pinned as a blob for
# the same reason as above: `HEAD` would become the round-4 gate the moment this lands, and
# the control would be comparing the new gate with itself.
PRE_R4_GATE_BLOB = "b7262302f035576497a15955ec4fc78ca4b4315f"

MEASURE_TABLE = (
    "\n| check | budget | measured | % |\n|---|---|---|---|\n"
    "| wire-check | 25 s | 33,938 ms | 135.8% |\n"
)
PROSE_TABLE = "\n| half | state |\n|---|---|\n| PreCompact | NOT-WIRED |\n"


def pinned_gate(tmp: Path, blob: str, name: str, *, must_lack: str) -> Path:
    """Materialise a historical gate, refusing if it already contains the fix under test."""
    p = subprocess.run(
        ["git", "cat-file", "-p", blob], cwd=str(REPO), capture_output=True, timeout=60
    )
    src = p.stdout.decode("utf-8", "replace")
    if not src.strip():
        raise SystemExit(f"FAILED:cite-gate-test cannot read pinned blob {blob[:12]}")
    if must_lack in src:
        raise SystemExit(
            f"FAILED:cite-gate-test the pinned blob {blob[:12]} ALREADY contains "
            f"{must_lack!r} -- this control would compare the new gate with itself"
        )
    out = tmp / name
    out.write_text(src, encoding="utf-8")
    return out


def old_gate(tmp: Path, retarget: Path | None) -> Path:
    """The gate as it was before round 3, optionally pointed at the fixture."""
    p = subprocess.run(
        ["git", "cat-file", "-p", PRE_R3_GATE_BLOB],
        cwd=str(REPO),
        capture_output=True,
        timeout=60,
    )
    src = p.stdout.decode("utf-8", "replace")
    if not src.strip():
        raise SystemExit(
            f"FAILED:cite-gate-test cannot read the pinned pre-round-3 blob "
            f"{PRE_R3_GATE_BLOB[:12]}"
        )
    if "EVIDENCE-DRIFT" in src:
        raise SystemExit(
            "FAILED:cite-gate-test the pinned blob ALREADY contains the round-3 fix -- "
            "every control below would be comparing the new gate with itself"
        )
    if retarget is not None:
        # a lambda, not a template: a Windows path in a replacement STRING is parsed for
        # backslash escapes and dies on `\U` (measured -- re.PatternError: bad escape \U).
        target = str(retarget).replace("\\", "/")
        src, n = re.subn(
            r'REPO = Path\("[^"]*"\)',
            lambda _m: f'REPO = Path("{target}")',
            src,
            count=1,
        )
        if n != 1:
            raise SystemExit(
                "FAILED:cite-gate-test could not retarget the old gate -- its hardcoded "
                "REPO line is gone, so this control no longer measures what it claims"
            )
    out = tmp / f"old_gate_{'fix' if retarget else 'asis'}.py"
    out.write_text(src, encoding="utf-8")
    return out


def run_gate(gate: Path, root: Path, *, env_root: str | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    env.pop("HOOK_AUDIT_REPO", None)
    if env_root is not None:
        env["HOOK_AUDIT_REPO"] = env_root
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        [sys.executable, str(gate)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def case(name: str, got, want, note: str = "") -> None:
    ok = got == want
    CASES.append((name, ok))
    print(f"{'OK' if ok else 'XX'} [{name}] got={got!r} want={want!r} {note}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cite-gate-"))
    try:
        # ---- H1 EVIDENCE-DRIFT -------------------------------------------------
        drift = make_fixture(tmp / "h1", doc_value="2.0", blob_value="1.0")
        rc_old, out_old = run_gate(old_gate(tmp, drift), drift)
        case(
            "H1 control: the OLD gate passes a drifted blob",
            rc_old,
            0,
            "-- if this is not 0 the hole was already closed and H1 measures nothing",
        )
        rc_new, out_new = run_gate(GATE, drift, env_root=str(drift))
        case("H1 the new gate FAILS a drifted blob", rc_new, 1)
        case("H1 the failure names EVIDENCE-DRIFT", "EVIDENCE-DRIFT" in out_new, True)

        # ---- CLEAN control -----------------------------------------------------
        clean = make_fixture(tmp / "clean", doc_value="1.0", blob_value="1.0")
        rc_c, _ = run_gate(GATE, clean, env_root=str(clean))
        case(
            "CLEAN the new gate PASSES when blob == worktree",
            rc_c,
            0,
            "-- without this, H1 could pass by failing everything",
        )

        # ---- H2 WRONG REPO -----------------------------------------------------
        rc_o2, out_o2 = run_gate(old_gate(tmp, None), clean)
        case(
            "H2 control: the OLD gate reports on ANOTHER repo's documents",
            "ROUND2-CORRECTIONS.md" in out_o2,
            True,
            "-- a document that does not exist in this fixture",
        )
        _rc_n2, out_n2 = run_gate(GATE, clean, env_root=str(clean))
        case("H2 the new gate reports on the FIXTURE", "DOC.md" in out_n2, True)
        case(
            "H2 the new gate does NOT reach ast-integrate",
            "ROUND2-CORRECTIONS.md" not in out_n2,
            True,
        )

        # ---- H3 PER-DOC FLOOR --------------------------------------------------
        floor = make_fixture(tmp / "h3", doc_value="1.0", blob_value="1.0")
        (floor / "docs" / "hook-audit" / "UNGATED.md").write_text(
            "# ungated\n\nThe hook took 33,938 ms, which is 135.8% of budget.\n",
            encoding="utf-8",
        )
        sh(floor, "git", "add", "-A")
        sh(floor, "git", "commit", "-q", "-m", "add an unannotated doc")
        rc_o3, _ = run_gate(old_gate(tmp, floor), floor)
        case("H3 control: the OLD gate passes an unannotated document", rc_o3, 0)
        rc_n3, out_n3 = run_gate(GATE, floor, env_root=str(floor))
        case("H3 the new gate FAILS it", rc_n3, 1)
        case("H3 the failure names the document", "UNGATED.md" in out_n3, True)

        # ---- UNTRACKED (round-2 behaviour, regression guard) -------------------
        untr = make_fixture(
            tmp / "untr", doc_value="1.0", blob_value="1.0", commit=False
        )
        sh(untr, "git", "add", "docs")
        sh(untr, "git", "commit", "-q", "-m", "doc only, evidence left untracked")
        rc_u, out_u = run_gate(GATE, untr, env_root=str(untr))
        case("UNTRACKED evidence still fails", rc_u, 1)
        case("UNTRACKED failure says UNTRACKED", "UNTRACKED" in out_u, True)

        # ---- BADROOT fail-closed ------------------------------------------------
        bad = tmp / "bad"
        bad.mkdir()
        rc_b, out_b = run_gate(GATE, clean, env_root=str(bad))
        case("BADROOT the new gate fails closed", rc_b, 1)
        case("BADROOT says it refuses to guess", "refusing to guess" in out_b, True)

        # ---- H4 UNCITED MEASUREMENT TABLE ---------------------------------------
        # The doc keeps its valid citation, so the per-document floor is satisfied and the
        # ONLY rule that can fire is the new one. Without that, H4 would be re-testing H3.
        def with_table(sub: str, table: str) -> Path:
            root = make_fixture(tmp / sub, doc_value="1.0", blob_value="1.0")
            doc = root / "docs" / "hook-audit" / "DOC.md"
            doc.write_text(doc.read_text(encoding="utf-8") + table, encoding="utf-8")
            return root

        h4 = with_table("h4", MEASURE_TABLE)
        old4 = pinned_gate(
            tmp,
            PRE_R4_GATE_BLOB,
            "old_gate_r3.py",
            must_lack="UNCITED-MEASUREMENT-TABLE",
        )
        rc_o4, _ = run_gate(old4, h4, env_root=str(h4))
        case(
            "H4 control: the PRE-R4 gate PASSES an uncited measurement table",
            rc_o4,
            0,
            "-- if this is not 0 the hole was already closed and H4 measures nothing",
        )
        rc_n4, out_n4 = run_gate(GATE, h4, env_root=str(h4))
        case("H4 the new gate FAILS it", rc_n4, 1)
        case(
            "H4 the failure names the rule",
            "UNCITED-MEASUREMENT-TABLE" in out_n4,
            True,
        )

        cited = with_table(
            "h4cited",
            MEASURE_TABLE.replace(
                "| 135.8% |",
                "| 135.8% <!-- cite: id=T1 file=E.json path=metrics.value value=1.0 --> |",
            ),
        )
        rc_c4, _ = run_gate(GATE, cited, env_root=str(cited))
        case(
            "H4 CITED-INSIDE control: a marker in a cell PASSES",
            rc_c4,
            0,
            "-- stops the rule passing H4 by failing every table",
        )

        waived = with_table(
            "h4waived",
            "\n<!-- uncited-table: reason=quotes refuted wording verbatim -->"
            + MEASURE_TABLE,
        )
        rc_w4, _ = run_gate(GATE, waived, env_root=str(waived))
        case("H4 WAIVER with a reason PASSES", rc_w4, 0)

        noreason = with_table("h4noreason", "\n<!-- uncited-table: -->" + MEASURE_TABLE)
        rc_r4, out_r4 = run_gate(GATE, noreason, env_root=str(noreason))
        case("H4 WAIVER without a reason FAILS", rc_r4, 1)
        case("H4 that failure says so", "no reason=" in out_r4, True)

        prose = with_table("h4prose", PROSE_TABLE)
        rc_p4, _ = run_gate(GATE, prose, env_root=str(prose))
        case(
            "H4 PROSE-TABLE control: a table with no measurement PASSES",
            rc_p4,
            0,
            "-- the rule is scoped to measurements, not to tables",
        )

        # The classifier's own both-states control, called directly rather than inferred
        # from a green run: a silent classifier reports zero violations forever.
        sys.path.insert(0, str(HERE))
        import importlib

        cc = importlib.import_module("check_citations")
        case(
            "H4 CLASSIFIER fires on a measurement table",
            cc.classifier_selfcheck()[0],
            True,
        )
        case(
            "H4 CLASSIFIER silent on a prose table", cc.classifier_selfcheck()[1], True
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad_n = sum(1 for _n, ok in CASES if not ok)
    print(
        f"\nRESULT: {'ALL PASS' if not bad_n else 'FAILURES PRESENT'} "
        f"({len(CASES)} cases, {bad_n} failed)"
    )
    print("SUCCESS:cite-gate-test" if not bad_n else f"FAILED:cite-gate-test {bad_n}")
    return 1 if bad_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
