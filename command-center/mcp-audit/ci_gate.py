#!/usr/bin/env python3
"""The MCP-audit lane's CI entry point: make the shipped gates REACHABLE.

WHY THIS EXISTS.  Four rounds of defect closure produced 20-odd executable gates in this
directory -- a DoD ledger with seven negative controls, three invariant red-proofs, an
EOL both-states probe, a set-arithmetic overlap report -- and **nothing in the repository
ran any of them**.  `grep -rn mcp-audit .github/` returned zero matches.  A gate nobody
invokes is indistinguishable from a gate that does not exist: `disposition.json` could rot,
a mounted server could vanish from the inventory, a producer could stop reproducing its own
artifact, and every one of those would land on main green.

WHAT IT ASSERTS, in order:

  1. NO SILENT SHRINK.  Every ``*.py`` in this directory is either in ``CI_PLAN`` (with an
     expected exit code) or in ``EXCLUDED`` (with a written reason).  A file in neither
     fails the gate.  This is the invariant that stops the CI plan from quietly becoming
     "whatever still happened to pass" -- the exact way the round-3 DoD1 floor rotted.
  2. EVERY PLANNED GATE'S REAL EXIT CODE, captured per child.  A shell pipeline reports the
     LAST command's status, so `gate.py | tail` turns a red gate green; nothing here pipes.
  3. BOTH STATES.  ``_r2_dod_check.py 630bb8af`` is planned with expected rc **1**.  If that
     historical blob ever stops failing the ledger, the ledger has stopped measuring and the
     gate goes red -- silence on the current tree is only meaningful beside it.
  4. PRODUCER DETERMINISM.  ``rank_disposition.py`` and ``overlap_report.py`` are re-run into
     a temp file and compared BYTE-FOR-BYTE with the committed blob.  A hand-edited artifact,
     or a producer that no longer reproduces what shipped, is drift and fails.

PLATFORM.  Every gate here was authored on Windows; four of them failed on Linux when first
measured (``_i1_ci_portability.py``, 11/15).  The four causes were fixed -- host-flavour path
binding in ``dod1``, an unobservable Windows ``.cmd`` shim state in two controls, and a
blindness test contaminated by that same path bug -- and re-measured at 15/15 on Ubuntu
24.04 before this file was written.  The plan below is therefore chosen from measurement,
not from reading the source.

Run::

    python command-center/mcp-audit/ci_gate.py [--rev SHA]
    python command-center/mcp-audit/ci_gate.py --self-test
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SELF = pathlib.Path(__file__).name

# (label, argv with {REV} substituted, expected exit code)
CI_PLAN: list[tuple[str, list[str], int]] = [
    ("probe_capability --control", ["probe_capability.py", "--control"], 0),
    ("redproof_control", ["redproof_control.py"], 0),
    # The fourth signal moved out of the producer and into committed data; these three
    # guard that data and the classifier that attributes it, and are deterministic over
    # committed inputs (unlike the dated census in _g3, which stays excluded).
    ("backend_map (C1/C2/C3 classifier)", ["backend_map.py"], 0),
    ("s4_evidence (validator both-states)", ["s4_evidence.py", "--self-test"], 0),
    ("b1_redproof_backend", ["_b1_redproof_backend.py"], 0),
    # Round 4: the fleet denominator stopped being UNMEASURED.  `unsampled_surface` carries
    # the 7 HTTP rows the stdio sweep cannot spawn, transcribed from the client's own
    # deferred-tool listing.  It belongs in CI_PLAN, not EXCLUDED, because it PROBES NOTHING
    # at run time -- the transcription is a committed constant and every guard reads only
    # committed files, so it is a pure function of the repo exactly like `backend_map`'s
    # tables.  (The dated liveness probes stay excluded because they re-assert a claim about
    # the world; this one fails closed against the matrix instead.)
    ("unsampled_surface (fleet-denominator rows)", ["unsampled_surface.py"], 0),
    (
        "unsampled_surface (both-states)",
        ["unsampled_surface.py", "--self-test"],
        0,
    ),
    ("cost_rank (invariants)", ["cost_rank.py"], 0),
    # Round 3: an audit CONFIRMED a share quoted without its denominator and a prose count
    # transposed across rows.  Both lived where no producer computes -- a percentage's
    # wording, and a sentence -- so both are now enforced by something that executes.
    ("cost_rank (C5 both-states)", ["cost_rank.py", "--self-test"], 0),
    ("claim_lint (prose counts vs surfaces)", ["claim_lint.py"], 0),
    (
        "claim_lint (both-states on the real defect)",
        ["claim_lint.py", "--self-test"],
        0,
    ),
    # Round 3B: the audit's SECOND overclaim, truncated out of round 3's handoff.  C5 above
    # scopes the per-ROW share; the aggregate feeding it was still labelled `fleet` while
    # summing 16 of 23 rows, and five prose sites copied it as a fleet total.  A control on
    # the share cannot see the scope of the aggregate, so the class gets its own reader.
    # Deterministic over committed inputs: it reads its figures OUT of cost-rank.json.
    ("scope_lint (aggregate scope in prose)", ["scope_lint.py"], 0),
    (
        "scope_lint (both-states on the real defect)",
        ["scope_lint.py", "--self-test"],
        0,
    ),
    ("render_table (G1-G5 both-states)", ["render_table.py", "--self-test"], 0),
    # INTEGRATE: round 4 MEASURED the 7 HTTP rows and nothing joined the number back, so
    # the deliverable still printed `--` in seven `tools` cells.  This gate proves the
    # join is reachable end to end -- the completeness invariant fires on the pinned
    # pre-join blob and is silent now, its integrity and empty-join limbs each fire in
    # isolation, and the RENDERED table went from 7 unmeasured cost rows to 0.  It reads
    # only committed blobs plus the artifact beside it, so it is deterministic per PR.
    ("i5_resident_join (join reachable, both-states)", ["_i5_resident_join.py"], 0),
    ("overlap_report", ["overlap_report.py", "capability-matrix-r2.json"], 0),
    ("r2_reproduce (round-1 defects)", ["_r2_reproduce.py"], 0),
    ("r2_redproof_invariants", ["_r2_redproof_invariants.py"], 0),
    ("r2_corroborate", ["_r2_corroborate.py"], 0),
    ("r3_redproof_liveness", ["_r3_redproof_liveness.py"], 0),
    ("r4_eol_probe", ["_r4_eol_probe.py"], 0),
    ("r4_grep_control", ["_r4_grep_control.py"], 0),
    ("r4_cr_settle", ["_r4_cr_settle.py"], 0),
    ("r4_redproof", ["_r4_redproof.py"], 0),
    ("r4_selfcheck (all blobs 0 CRLF)", ["_r4_selfcheck.py", "{REV}"], 0),
    ("dod_check @ rev", ["_r2_dod_check.py", "{REV}"], 0),
    # BOTH STATES.  Not decoration: green on the current tree measures nothing unless the
    # same ledger is observed going red on a blob that genuinely violates it.
    ("dod_check @ 630bb8af (must FAIL)", ["_r2_dod_check.py", "630bb8af"], 1),
    # Re-run with no -o, so it writes nothing; the determinism check below does the writing
    # into a temp file.  Here it only has to execute and hold its own invariants
    # (assert_reversible / assert_signal_consistency / assert_liveness_consistency).
    ("rank_disposition (invariants)", ["rank_disposition.py"], 0),
]

# Every remaining *.py, with the reason it is NOT a per-PR gate.  A file absent from both
# tables fails the run -- silence is not an acceptable classification.
EXCLUDED: dict[str, str] = {
    SELF: "this gate itself",
    "_i1_ci_portability.py": (
        "one-shot portability MEASUREMENT; run against a Linux clone to choose CI_PLAN, "
        "not per PR"
    ),
    "_i2_diag_posix.py": "one-shot diagnostic that isolated the two POSIX root causes",
    "_i3_redproof.py": (
        "the RED-PROOF for this wiring; it commits deliberate defects, so it must run in a "
        "THROWAWAY CLONE only, never against the repo CI is checking out. Lane-scoped name, "
        "distinct from command-center/p2-next/_i3_redproof.py which red-proofs a different gate"
    ),
    "_i4_determinism_diff.py": (
        "one-shot diagnostic that named the two host-sourced fields behind the cross-platform "
        "artifact drift; the determinism ASSERTION lives in this gate, this only explains it"
    ),
    "_diag_cmd_resolution.py": "one-shot diagnostic (PATHEXT); prints, asserts nothing",
    "_diag_mutation.py": "one-shot diagnostic (tuple-truthiness bug); asserts nothing",
    "_diag_popen_cmd.py": "one-shot diagnostic (CreateProcess/PATHEXT); asserts nothing",
    "_probe_leak_check.py": "grounding lane probe; scans the working tree, superseded in CI by quality.yml gitleaks",
    "_probe_matrix.py": "grounding lane probe; reads the LIVE mcpctl fleet on this box",
    "_probe_process_census.py": "grounding lane probe; reads the LIVE Windows process table",
    "_probe_three_signals.py": "grounding lane probe; shells to `claude mcp list` (live fleet)",
    "_probe_tool_cost.py": "grounding lane probe; reads the LIVE in-session tool registry",
    "_verify_blob_gate.py": "needs `uvx ruff@0.15.17`; quality.yml already runs pinned ruff over the whole tree",
    "_verify_secrets_gate.py": "needs `gitleaks`; quality.yml already runs it over the whole tree",
    "_r2_ruff_census.py": "needs uvx; a dated census, not an assertion",
    "_r3_gate_sweep.py": "the LOCAL superset sweep (Windows-semantics states included); this file is its CI-scoped sibling",
    "_r3_hunt.py": "exploratory hunt used to find round-3 defects; not an assertion",
    "_g2_drift_probe.py": (
        "grounding lane probe (round 2); one side of its comparison is a SESSION-OBSERVED "
        "namespace snapshot that CI cannot re-derive. Wiring it would assert a dated fleet "
        "shape forever and go red the first time the owner legitimately mounts a server"
    ),
    "_g3_backend_liveness.py": (
        "the dated per-backend CENSUS. It no longer owns the classifier or the probe "
        "verdicts -- those moved to backend_map.py and s4-evidence.json, both CI-wired "
        "above -- but its headline is still a dated liveness claim, and running it per "
        "PR would re-assert 2026-08-13 zombie counts indefinitely. Same split as "
        "_r2_ruff_census.py: assertions in CI, census out"
    ),
    "_g4_cost_rollup.py": (
        "grounding lane probe (round 2); a dated cost census over a committed artifact, "
        "not an assertion -- same class as _r2_ruff_census.py"
    ),
}


# --------------------------------------------------------------------- pure predicates
def classify(present: set[str]) -> tuple[list[str], list[str]]:
    """(files in neither table, files in a table but absent from disk)."""
    planned = {argv[0] for _, argv, _ in CI_PLAN}
    known = planned | set(EXCLUDED)
    unclassified = sorted(present - known)
    ghosts = sorted(known - present)
    return unclassified, ghosts


def verdict(results: list[dict[str, Any]]) -> list[str]:
    """Labels whose REAL exit code did not match the expected one."""
    return [r["label"] for r in results if r["rc"] != r["expect"]]


def drift(regenerated: bytes, committed: bytes) -> bool:
    """True when a producer no longer reproduces the artifact that shipped."""
    return regenerated != committed


# ------------------------------------------------------------------------- execution
def run(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, *argv], cwd=HERE, capture_output=True, text=True
    )
    out = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    marker = next(
        (ln for ln in reversed(out) if ln.startswith(("SUCCESS:", "FAILED:"))),
        (out[-1] if out else "<no stdout>"),
    )
    if proc.returncode != 0 and proc.stderr.strip():
        marker = f"{marker}  |stderr| {proc.stderr.strip().splitlines()[-1][:110]}"
    return proc.returncode, marker.strip()[:190]


def blob(rev: str, path: str) -> bytes | None:
    """The committed bytes, or None when the path does not exist at ``rev``.

    ``check=True`` here raised a raw CalledProcessError traceback the first time a new
    producer was added before its artifact was committed.  A gate that dies with a stack
    trace instead of a ``FAILED:`` line is harder to read in CI and, worse, is one
    refactor away from being caught by a bare ``except`` and silently skipped -- so the
    missing-blob case is now a reported problem rather than a crash.
    """
    proc = subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO, capture_output=True
    )
    return proc.stdout if proc.returncode == 0 else None


def determinism(rev: str) -> tuple[list[str], int]:
    """Re-run both producers into a temp dir; require byte-identity with the committed blob.

    Both write with ``newline="\\n"`` explicitly, so this is byte-exact on either platform --
    no line-ending normalisation, which would have hidden precisely the class of defect
    round 4 spent itself on.
    """
    problems: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mcpaudit-determinism-"))
    # (repo-relative committed path, argv, temp output).  The path is carried in full
    # rather than assembled from a fixed prefix: a produced artifact does not have to live
    # beside its producer, and DISPOSITION-TABLE.md -- the one that actually drifted --
    # lives under docs/.
    jobs = [
        (
            "command-center/mcp-audit/disposition.json",
            ["rank_disposition.py", "--base", str(HERE), "-o", str(tmp / "d.json")],
            tmp / "d.json",
        ),
        (
            "command-center/mcp-audit/overlap-report.json",
            [
                "overlap_report.py",
                "capability-matrix-r2.json",
                "-o",
                str(tmp / "o.json"),
            ],
            tmp / "o.json",
        ),
        (
            "command-center/mcp-audit/unsampled-surface.json",
            ["unsampled_surface.py", "--base", str(HERE), "-o", str(tmp / "u.json")],
            tmp / "u.json",
        ),
        (
            "command-center/mcp-audit/cost-rank.json",
            ["cost_rank.py", "--base", str(HERE), "-o", str(tmp / "c.json")],
            tmp / "c.json",
        ),
        (
            "docs/mcp-audit/DISPOSITION-TABLE.md",
            ["render_table.py", "--base", str(HERE), "-o", str(tmp / "t.md")],
            tmp / "t.md",
        ),
    ]
    for path, argv, out in jobs:
        name = path.rsplit("/", 1)[-1]
        rc, marker = run(argv)
        if rc != 0:
            problems.append(f"{name}: producer exited {rc} ({marker})")
            continue
        if not out.exists():
            problems.append(f"{name}: producer wrote nothing (fail closed)")
            continue
        regen = out.read_bytes()
        shipped = blob(rev, path)
        if shipped is None:
            problems.append(
                f"{name}: the producer runs but the artifact does not exist at {rev[:12]} "
                "-- commit it, or its determinism is unverifiable (fail closed)"
            )
            continue
        if drift(regen, shipped):
            problems.append(
                f"{name}: regenerated {len(regen)} B != committed {len(shipped)} B "
                "-- the artifact and its producer disagree"
            )
        else:
            print(
                f"  ok  {name:22} byte-identical to the committed blob ({len(regen)} B)"
            )
    return problems, len(jobs)


# ------------------------------------------------------------------------- self-test
def self_test() -> int:
    """Both states for every check this gate makes.  A gate never seen red is a no-op."""
    print("== ci_gate self-test (each check: must FIRE broken, stay SILENT good) ==")
    cases: list[tuple[str, bool, bool]] = []

    planned = {argv[0] for _, argv, _ in CI_PLAN}
    good_present = planned | set(EXCLUDED)
    u, g = classify(good_present)
    cases.append(("classify / complete inventory", bool(u or g), False))
    u, g = classify(good_present | {"_totally_new_gate.py"})
    cases.append(("classify / unclassified file", bool(u), True))
    u, g = classify(good_present - {"_r2_dod_check.py"})
    cases.append(("classify / planned file missing from disk", bool(g), True))

    ok_rows = [
        {"label": "a", "rc": 0, "expect": 0},
        {"label": "b", "rc": 1, "expect": 1},
    ]
    cases.append(("verdict / all as expected", bool(verdict(ok_rows)), False))
    cases.append(
        (
            "verdict / a gate went red",
            bool(verdict([{"label": "a", "rc": 1, "expect": 0}])),
            True,
        )
    )
    # The control's own control: a gate planned to FAIL that starts passing must be caught,
    # otherwise the both-states pair silently degrades into a one-state check.
    cases.append(
        (
            "verdict / an expected-FAIL gate started passing",
            bool(verdict([{"label": "b", "rc": 0, "expect": 1}])),
            True,
        )
    )

    cases.append(("drift / identical bytes", drift(b"{}\n", b"{}\n"), False))
    cases.append(("drift / one byte moved", drift(b"{}\n", b"{ }\n"), True))

    bad = [name for name, got, want in cases if got != want]
    for name, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {name:48} fired={got} want={want}")

    # A plan that has shrunk to nothing would pass every case above.
    if len(CI_PLAN) < 10:
        print(f"FAILED:mcp-audit-ci-gate self-test CI_PLAN shrank to {len(CI_PLAN)}")
        return 1
    if bad:
        print(f"FAILED:mcp-audit-ci-gate self-test {bad}")
        return 1
    print(
        f"SUCCESS:mcp-audit-ci-gate self-test {len(cases)}/{len(cases)} checks behaved"
    )
    return 0


# ------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{args.rev}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if resolved.returncode != 0:
        print(
            f"FAILED:mcp-audit-ci-gate rev {args.rev!r} does not resolve here "
            f"(fetch-depth?) -- {resolved.stderr.strip()[:120]}"
        )
        return 1
    rev = resolved.stdout.strip()
    print(
        f"== mcp-audit CI gate @ {rev[:12]} ({sys.platform}, py {sys.version.split()[0]}) =="
    )

    unclassified, ghosts = classify({p.name for p in HERE.glob("*.py")})
    if unclassified:
        print(
            "FAILED:mcp-audit-ci-gate new file(s) in neither CI_PLAN nor EXCLUDED: "
            f"{unclassified} -- add it to one, with a reason (fail closed)"
        )
        return 1
    if ghosts:
        print(f"FAILED:mcp-audit-ci-gate listed but absent from disk: {ghosts}")
        return 1
    print(
        f"  ok  inventory: {len(CI_PLAN)} planned runs over "
        f"{len({a[0] for _, a, _ in CI_PLAN})} gates, {len(EXCLUDED)} excluded with reasons"
    )

    results: list[dict[str, Any]] = []
    for label, argv_tmpl, expect in CI_PLAN:
        gate_argv = [rev if tok == "{REV}" else tok for tok in argv_tmpl]
        rc, marker = run(gate_argv)
        results.append({"label": label, "rc": rc, "expect": expect})
        print(
            f"  {'ok ' if rc == expect else 'BAD'} rc={rc} (want {expect})  {label:34} {marker}"
        )

    bad = verdict(results)
    print("  -- producer determinism --")
    det_problems, n_artifacts = determinism(rev)
    bad += det_problems

    if bad:
        for b in bad:
            print(f"  FAIL {b}")
        print(f"FAILED:mcp-audit-ci-gate {len(bad)} problem(s)")
        return 1
    # The artifact count is COUNTED, not typed: this line read "2/2" while a third
    # producer was being added, and a hardcoded total in a success message is the same
    # drift class as a legend that stops matching its field.
    print(
        f"SUCCESS:mcp-audit-ci-gate {len(results)}/{len(results)} gates behaved, "
        f"{n_artifacts}/{n_artifacts} artifacts byte-identical to their producers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
