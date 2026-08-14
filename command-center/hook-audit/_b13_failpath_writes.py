"""Find probes that OVERWRITE a committed evidence file on a FAILURE path.

The defect this exists for (verifier item V3, CONFIRMED deterministically):
`_r4_githygiene_range.py` writes its `out` dict over `R4-GITHYGIENE-RANGE.json` in the
INCONCLUSIVE branch and then returns 1. `out` at that point holds a strict SUBSET of the
keys a successful run produces, so re-running the probe in a state where its arms cannot
separate REPLACES the committed measurement with a truncated one -- six top-level keys
gone, and the citation gate goes from 0 unbacked to 18 unbacked. Verifying a claim by
re-running its probe is supposed to be free; here it destroys the evidence.

(The verifier measured 15. It is 18 now because BUILD-R4 pinned three more claims to the
same file. A defect of this shape gets worse the longer it is left.)

This scan asks whether any SIBLING probe shares the shape, because remediating only the
first symptom of a confirmed defect is the blast-radius failure (AGENTS.md 9b).

WHAT COUNTS AS THE SHAPE. In one statement list, in this order:
  1. a write to a path that resolves to a file TRACKED IN GIT under this directory, and
  2. a later `return <non-zero>` / `sys.exit(<non-zero>)` in that SAME statement list.
That is the exact V3 construction. Writes on a success path are not flagged; writes to
untracked scratch are not flagged, because destroying scratch is not destroying evidence.

CONTROLS (all five must hold or the scan refuses to publish):
  C1 positive -- a FIXTURE carrying the exact broken shape MUST be flagged. A scan that
     cannot see the defect it was written for measures nothing.

     C1 pinned the LIVE `_r4_githygiene_range.py` in this probe's first version. That is a
     control that rots the moment the defect is fixed: the scan would have started failing
     its own control precisely because the tree got better, and this lane has already paid
     for that shape once (commit d2177dd3, "my both-states control pinned itself to HEAD
     and rotted on the next run"). Repointed to a fixture BEFORE the fix landed, so the
     positive arm keeps testing the detector rather than the tree.
  C2 negative -- a synthetic twin whose write sits only on the success path MUST NOT be
     flagged. Without it, "everything is flagged" is indistinguishable from a real finding.
  C3 discrimination on the TRACKED axis -- a synthetic file that writes an UNTRACKED name
     on a fail path MUST NOT be flagged. This is the control that separates "writes on a
     fail path" (common and harmless) from "destroys committed evidence" (the claim).
  C4 non-empty -- at least 20 python files scanned and at least 5 tracked JSON evidence
     files resolved, else exit 2. A zero from a blind walker is not a clean bill.
  C5 baseline intact -- the three PINNED pre-fix blobs must still show the defect. Without
     it the "3 -> 0" claim loses its 'before' the moment the fix is committed.
  C6 SCOPE BOUNDARY, and the most important one to read before quoting "0 offenders". A
     probe that writes a COMPLETE record and only afterwards decides a non-zero exit -- the
     `write(...)` then `if not ok: return 1` shape used by `_b10_ci_proof.py` and by this
     file itself -- must NOT be flagged. C6 pins that as deliberate, not as a miss.

     The distinction being measured is TRUNCATE-AND-BAIL, not write-then-fail. Widening the
     rule to every write-then-fail would flag the honest "record the failure completely"
     pattern and turn this scan into the kind of noise the audit's own axes complain about.
     The residual that leaves open is real and is disclosed in BUILD-R5.md section 4: a
     complete-record write still REPLACES committed evidence on a failing run, so a cited
     boolean can flip. It is a smaller hazard than key loss, and it is not zero.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "B13-FAILPATH-WRITES.json"

MIN_PY_FILES = 20
MIN_TRACKED_JSON = 5

# The three probes as they stood BEFORE round 5's fix, pinned by blob sha so the baseline
# survives the commit that fixes them. Scanning HEAD instead would silently become a scan of
# the FIXED tree the moment the fix lands, and the baseline would read 0 offenders -- the
# same self-erasing-control shape C1 was repointed away from.
PREFIX_BLOBS = {
    "_r4_githygiene_range.py": "1294fa1aaef5202a0d355bacb23c780b6ab9aade",
    "_r4_budget_ceiling.py": "1be929b1c0853aa3602a150f956c372ee2979d43",
    "_r4_wire_exit.py": "3347ae67e9e333b928c2f9f99e32fd3db7752648",
}


def tracked_json_names() -> set[str]:
    """Basenames of git-TRACKED .json files under this directory."""
    p = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--", "command-center/hook-audit"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        print(f"FAILED:b13 git ls-files exited {p.returncode}")
        raise SystemExit(2)
    return {
        Path(line).name
        for line in (p.stdout or "").splitlines()
        if line.strip().lower().endswith(".json")
    }


def _string_constants(node: ast.AST) -> list[str]:
    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _is_write(stmt: ast.stmt) -> bool:
    """Does this statement perform a filesystem write?"""
    for n in ast.walk(stmt):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in {"write_text", "write_bytes"}:
                return True
            if (
                n.func.attr == "dump"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "json"
            ):
                return True
    return False


def _nonzero_exit(stmt: ast.stmt) -> bool:
    """Is this statement a `return <nonzero>` or `sys.exit(<nonzero>)` / `raise SystemExit(<nonzero>)`?"""
    if isinstance(stmt, ast.Return):
        v = stmt.value
        return isinstance(v, ast.Constant) and isinstance(v.value, int) and v.value != 0
    for n in ast.walk(stmt):
        if isinstance(n, ast.Call):
            name = None
            if isinstance(n.func, ast.Attribute):
                name = n.func.attr
            elif isinstance(n.func, ast.Name):
                name = n.func.id
            if name in {"exit", "SystemExit"} and n.args:
                a = n.args[0]
                if (
                    isinstance(a, ast.Constant)
                    and isinstance(a.value, int)
                    and a.value != 0
                ):
                    return True
    return False


def scan_source(src: str, tracked: set[str]) -> list[dict]:
    """Return findings: a tracked-evidence write followed by a nonzero exit in the same block."""
    findings: list[dict] = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            writes: list[tuple[ast.stmt, list[str]]] = []
            for stmt in block:
                if not isinstance(stmt, ast.stmt):
                    continue
                if _is_write(stmt):
                    hits = [s for s in _string_constants(stmt) if s in tracked]
                    if hits:
                        writes.append((stmt, hits))
                elif writes and _nonzero_exit(stmt):
                    for wstmt, hits in writes:
                        findings.append(
                            {
                                "write_line": wstmt.lineno,
                                "exit_line": stmt.lineno,
                                "evidence_files": sorted(set(hits)),
                            }
                        )
                    writes = []
    return findings


# --- controls -------------------------------------------------------------------

# The exact V3 construction, as a fixture rather than a pin on a live file.
C1_SRC = """
from pathlib import Path
def main() -> int:
    out = {}
    if not discriminates:
        out["verdict"] = "INCONCLUSIVE"
        Path("R4-GITHYGIENE-RANGE.json").write_text("{}")
        print("FAILED:x")
        return 1
    return 0
"""

C2_SRC = """
from pathlib import Path
def main() -> int:
    out = {}
    if not ok:
        print("FAILED:x")
        return 1
    Path("R4-GITHYGIENE-RANGE.json").write_text("{}")
    return 0
"""

# Scope boundary: a COMPLETE record written before the exit decision. Deliberately not flagged.
C6_SRC = """
from pathlib import Path
def main() -> int:
    out = {"everything": 1, "controls": {}}
    Path("R4-GITHYGIENE-RANGE.json").write_text("{}")
    if not ok:
        print("FAILED:x")
        return 1
    return 0
"""

C3_SRC = """
from pathlib import Path
def main() -> int:
    if not ok:
        Path("_scratch_not_tracked.json").write_text("{}")
        return 1
    return 0
"""


def scan_prefix_baseline(tracked: set[str]) -> dict:
    """Scan the pinned pre-fix blobs so the 'before' number stays measurable after the fix."""
    per_file: dict[str, list[dict]] = {}
    sites = 0
    for name, blob in PREFIX_BLOBS.items():
        p = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-p", blob],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if p.returncode != 0:
            return {"readable": False, "blob": blob}
        f = scan_source(p.stdout, tracked)
        if f:
            per_file[name] = f
            sites += len(f)
    return {
        "readable": True,
        "n_offender_probes": len(per_file),
        "n_offending_sites": sites,
        "offenders": per_file,
    }


def main() -> int:
    tracked = tracked_json_names()
    files = sorted(p for p in HERE.glob("*.py"))

    per_file: dict[str, list[dict]] = {}
    unparsed: list[str] = []
    for p in files:
        try:
            src = p.read_text(encoding="utf-8")
        except OSError:
            unparsed.append(p.name)
            continue
        try:
            f = scan_source(src, tracked)
        except SyntaxError:
            unparsed.append(p.name)
            continue
        if f:
            per_file[p.name] = f

    # C1: a fixture carrying the broken shape must be flagged (never a live file -- see docstring).
    c1 = bool(scan_source(C1_SRC, tracked))
    # C2: a synthetic twin writing only on the success path must NOT be flagged.
    c2 = not scan_source(C2_SRC, tracked)
    # C3: a fail-path write to an UNTRACKED name must NOT be flagged.
    c3 = not scan_source(C3_SRC, tracked)
    # C4: the walk must be non-empty on both axes.
    c4 = len(files) >= MIN_PY_FILES and len(tracked) >= MIN_TRACKED_JSON

    baseline = scan_prefix_baseline(tracked)
    # C5: the pinned pre-fix blobs must still show the defect. If the baseline reads clean,
    # the "3 -> 0" claim has lost its 'before' and must not be published.
    c5 = bool(baseline.get("readable")) and baseline.get("n_offender_probes", 0) == 3
    # C6: the complete-record-then-exit shape is OUT of scope by design, not missed.
    c6 = not scan_source(C6_SRC, tracked)

    out = {
        "probe": "_b13_failpath_writes.py",
        "prefix_baseline": baseline,
        "py_files_scanned": len(files),
        "tracked_json_evidence_files": len(tracked),
        "unparsed": unparsed,
        "n_offenders": len(per_file),
        "offenders": per_file,
        "controls": {
            "C1_broken_shape_fixture_is_flagged": c1,
            "C2_success_path_write_not_flagged": c2,
            "C3_untracked_failpath_write_not_flagged": c3,
            "C4_walk_non_empty": c4,
            "C5_prefix_baseline_still_shows_the_defect": c5,
            "C6_complete_record_write_is_out_of_scope": c6,
        },
        "scope": (
            "TRUNCATE-AND-BAIL only: a partial payload written over committed evidence and a "
            "non-zero exit in the same statement list. A COMPLETE record written before the "
            "exit decision is out of scope by design (C6) and still replaces committed "
            "evidence on a failing run -- see BUILD-R5.md section 4."
        ),
    }
    ok = c1 and c2 and c3 and c4 and c5 and c6
    out["controls_all_pass"] = ok
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    if not ok:
        print("FAILED:b13-failpath controls did not hold -- no verdict may be cited")
        return 2
    print(
        f"SUCCESS:b13-failpath {len(per_file)} probe(s) overwrite committed evidence on a fail path"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
