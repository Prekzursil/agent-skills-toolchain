#!/usr/bin/env python3
"""Ratchet the repo->live rule DEPLOY DRIFT, the one hole every prior round left open.

WHY THIS EXISTS.  ``ci_gate.py`` states the gap in its own docstring::

    Everything that compares against the LIVE tree cannot run in CI at all (see EXCLUDED),
    which is exactly why the repo-vs-live drift grew from 28 to 29 files while 167 tests
    stayed green.

and ``RULE-AUDIT-BUILD-R2.md`` closes with it unresolved: "Repo/live drift (29/88 files, 7/8
always-on) is still neither gated nor fixed."  Four audit rounds, three adversarial rounds and
two build rounds measured this number; nothing ever ASSERTED on it, so it moved 28 -> 29
silently while 167 rules tests stayed green.  Every one of those tests reads ``rules/`` and
``agent-self/config/rules/``; none reads the deployed tree.

WHY THE OTHER LIVE-TREE GATES COULD NOT DO THIS.  ``lazy_predict.py`` and
``r3_corpus_parity_gate.py`` are EXCLUDED from CI because they fail CLOSED when ``~/.claude``
is absent -- correct for them, since "zero files scanned" is a broken detector.  A drift gate
has a legitimate THIRD state that those two do not: the comparison is not merely failed, it is
UNPERFORMABLE, and saying so is the honest answer rather than either a pass or a failure.  So
this gate reports three outcomes, and only one of them is a clean bill of health:

    live tree ABSENT   -> rc=0, marker says NOT-CHECKED and names the world.  It asserts
                          NOTHING about drift; a runner cannot see the owner's home directory.
    drift == BASELINE  -> rc=0.  The known, owner-visible deploy debt is unchanged.
    drift != BASELINE  -> rc=1, in BOTH directions (see below).

FOUR AXES, not one.  Content drift is only the obvious axis; the other three are the ones that
move silently: which files exist on each side, and -- the axis nothing in this repo checked --
whether the DEPLOYED copy of a rule carries the same ``paths:`` frontmatter as the repo copy.
``ci_gate`` invariant 4 compares load semantics between the two IN-REPO deploy sources and stops
there, so a deploy that stripped or added frontmatter would change the live turn-0 set with no
gate anywhere noticing.  Measured this round with a control: repo always-on=8, live always-on=8,
sets identical, so that baseline is EMPTY and any entry is a failure.

BOTH DIRECTIONS, because a repair that nobody records is how an allowlist rots into silence --
the same discipline ``ci_gate.divergence_problems`` already applies to the two in-repo trees:

  * drift GREW  -> a rule was edited in the repo and never deployed, or edited in the live tree
    and never reconciled (``harness-vcs-hygiene``: live-only is drift, not a resting state).
  * drift SHRANK -> somebody deployed.  Good -- and the baseline below must shrink in the same
    change, so the ledger reflects it instead of quietly absorbing it.

SEVERITY IS NOT UNIFORM, so the always-on subset is tracked separately.  A rule with no
``paths:`` frontmatter is injected at turn 0 into EVERY agent on this box; a lazy one costs
nothing until a matching file is touched.  Drift in an always-on rule is therefore a wrong
instruction being read by every session right now, which is what makes ``common/harness-vcs-
hygiene.md`` the highest-severity row in the baseline: the deployed copy still tells agents that
``-Report json`` inspects, when ``scripts/sync-from-live.ps1:477`` gates every write on
``$writeAllowed = (-not $WhatIf -and -not $Drift)`` -- ``Report`` is absent from that
expression, so mode is ``sync`` (``:499``) and ``Copy-Item -Force`` overwrites repo files
(``:601``, ``:670``).  The repo copy carries the correction; the deployed copy does not.

WHAT THIS GATE DOES NOT DO.  It does not deploy.  Writing to ``~/.claude`` changes what every
concurrently-running agent on this box reads, mid-flight; two prior rounds classified that as an
owner-visible action rather than a build-lane side effect, and this round does not overturn that.
The gate makes the debt LOUD and non-growing.  Paying it stays the owner's call.

COMPARISON SEMANTICS.  Content is compared LF-normalised (``rule_audit.read_lf``), because this
estate's recurring false positive is CRLF phantom drift.  The raw-byte count is measured too and
reported alongside, so a future reader can see at a glance whether line endings are driving the
number instead of having to re-derive it.  No path under the home directory is ever printed: a
CI log is a published artifact and the home directory is an identity disclosure.

Run::

    python docs/rule-audit/r5_deploy_drift_gate.py
    python docs/rule-audit/r5_deploy_drift_gate.py --self-test
    python docs/rule-audit/r5_deploy_drift_gate.py --print-measured
    python docs/rule-audit/r5_deploy_drift_gate.py --repo-root A --live-root B   # red-proof
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

sys.path.insert(0, str(HERE))
import rule_audit  # noqa: E402  (same-directory sibling; the audit's own reader/parser)

DEFAULT_REPO_RULES = REPO / "rules"
DEFAULT_LIVE_RULES = pathlib.Path.home() / ".claude" / "rules"

# --------------------------------------------------------------------------- the baseline
# The measured, currently-unpaid deploy debt.  Generated by --print-measured and pinned here
# rather than in a data file, so that re-pinning is a source edit visible in review -- the same
# convention ci_gate.py uses for ALWAYS_ON and ALLOWED_LOAD_DIVERGENCE.
#
# ALWAYS-ON entries are listed first and separately: those are in every turn-0 prompt.
# Measured 2026-08-14 on this box: repo=88 live=88 .md files, name sets IDENTICAL (nothing is
# missing from either side), 29 files differ LF-normalised.  The raw-byte differ is 83 -- so 54
# of the 83 are pure CRLF phantoms and a naive byte-compare ratchet would be ~65% false positive.
#
# 7 of the 8 always-on rules are drifted; only common/stale-megapr-reconcile.md matches.  These
# seven are read at turn 0 by every agent on this box, so each is a WRONG INSTRUCTION IN FORCE,
# not a cosmetic diff.  The one that motivated this gate:
#   common/harness-vcs-hygiene.md -- deployed copy says "`-Report json` to see drift"; the repo
#   copy carries the correction that bare -Report json WRITES (sync-from-live.ps1:477/:499/:601).
BASELINE_ALWAYS_ON_DRIFT: set[str] = {
    "common/agents.md",
    "common/bash-hud-and-terminal-emit.md",
    "common/cross-vendor-dispatch.md",
    "common/fan-out-contract.md",
    "common/harness-vcs-hygiene.md",
    "common/single-signal-verification.md",
    "common/windows-shell.md",
}
BASELINE_LAZY_DRIFT: set[str] = {
    "README.md",
    "common/ci-hygiene.md",
    "common/code-review.md",
    "common/coding-style.md",
    "common/development-workflow.md",
    "common/git-workflow.md",
    "common/hooks.md",
    "common/owner-ops-authorization.md",
    "common/patterns.md",
    "common/performance.md",
    "common/security.md",
    "common/static-analyzer.md",
    "common/testing.md",
    "dart/patterns.md",
    "java/testing.md",
    "perl/patterns.md",
    "php/coding-style.md",
    "python/security.md",
    "rust/hooks.md",
    "typescript/coding-style.md",
    "typescript/hooks.md",
    "web/hooks.md",
}
BASELINE_ONLY_IN_REPO: set[str] = set()
BASELINE_ONLY_IN_LIVE: set[str] = set()

# LOAD-SEMANTICS PARITY, repo vs LIVE.  ci_gate invariant 4 checks this between the two IN-REPO
# deploy sources and stops there; nothing checked it against the deployed tree, which is the one
# agents actually read.  If a deployed file gained or lost `paths:` frontmatter, the live
# always-on set would differ from the repo one -- and the always-on set is the whole of DoD-1.
#
# It also protects THIS gate from being quietly wrong about itself: the always-on/lazy severity
# split above is computed from the REPO copy's frontmatter, so a live-side demotion would file a
# lazy rule under "read by every session right now" and nobody would notice.
#
# Measured 2026-08-14, with a control proving the classifier can disagree at all (a bare file
# and a paths-scoped file classify True/False): repo always-on=8, live always-on=8, sets
# IDENTICAL -- zero promotions, zero demotions.  The drift is content-only.  Baseline is
# therefore EMPTY and any entry at all is a failure.
BASELINE_LOAD_CLASS_DIVERGENCE: set[str] = set()


# --------------------------------------------------------------------------- measurement
def _md_files(root: pathlib.Path) -> dict[str, pathlib.Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*.md"))
        if p.is_file()
    }


def measure(repo_root: pathlib.Path, live_root: pathlib.Path) -> dict[str, object]:
    """Compare the two trees.  Returns sets of rel-paths, never absolute paths.

    Fails CLOSED on an empty repo scan: "zero files differ" and "zero files looked at" are the
    same output from a clean run and from a broken detector, and only one of them is good news.
    """
    repo_files = _md_files(repo_root)
    if not repo_files:
        raise RuntimeError(
            "repo rules tree scanned to ZERO .md files -- detector broken, refusing to "
            "report drift (a clean run and a broken walk look identical here)"
        )
    live_files = _md_files(live_root)
    if not live_files:
        raise RuntimeError(
            "live rules tree scanned to ZERO .md files -- detector broken, refusing to "
            "report drift"
        )

    always_on, lazy, raw_differ, load_class = set(), set(), set(), set()
    for rel, rpath in repo_files.items():
        lpath = live_files.get(rel)
        if lpath is None:
            continue
        if rpath.read_bytes() != lpath.read_bytes():
            raw_differ.add(rel)
        repo_text = rule_audit.read_lf(rpath)
        live_text = rule_audit.read_lf(lpath)
        repo_fm, _ = rule_audit.parse_frontmatter(repo_text)
        if repo_text != live_text:
            (lazy if repo_fm else always_on).add(rel)
        # Load class is compared even when the CONTENT matches: a file could differ only in its
        # frontmatter block and still be byte-different, but the reverse is what matters here --
        # this is the axis, not a by-product of the content check.
        live_fm, _ = rule_audit.parse_frontmatter(live_text)
        if repo_fm != live_fm:
            load_class.add(rel)

    return {
        "always_on_drift": always_on,
        "lazy_drift": lazy,
        "load_class_divergence": load_class,
        "only_in_repo": set(repo_files) - set(live_files),
        "only_in_live": set(live_files) - set(repo_files),
        "repo_count": len(repo_files),
        "live_count": len(live_files),
        # Disclosed so nobody has to re-derive whether line endings drive the number.
        "raw_byte_differ": len(raw_differ),
        "lf_normalised_differ": len(always_on) + len(lazy),
    }


# ---------------------------------------------------------------------- pure predicates
def _delta(measured: set[str], baseline: set[str], what: str) -> list[str]:
    """Both directions.  A repair is reported as loudly as a regression, because an
    unrecorded repair is how a baseline decays into a rubber stamp."""
    out = []
    for rel in sorted(measured - baseline):
        out.append(
            f"{what} GREW: {rel!r} now differs repo-vs-live and is not in the baseline. "
            "Either deploy it (scripts/sync-rules.ps1) or add it with the reason"
        )
    for rel in sorted(baseline - measured):
        out.append(
            f"{what} SHRANK: {rel!r} was baselined as drifted and now matches -- somebody "
            "deployed. Good: drop it from the baseline in the same change"
        )
    return out


def problems(measured: dict[str, object]) -> list[str]:
    return (
        _delta(measured["always_on_drift"], BASELINE_ALWAYS_ON_DRIFT, "ALWAYS-ON drift")
        + _delta(measured["lazy_drift"], BASELINE_LAZY_DRIFT, "lazy drift")
        + _delta(measured["only_in_repo"], BASELINE_ONLY_IN_REPO, "undeployed-file set")
        + _delta(
            measured["only_in_live"], BASELINE_ONLY_IN_LIVE, "unreconciled-file set"
        )
        + _delta(
            measured["load_class_divergence"],
            BASELINE_LOAD_CLASS_DIVERGENCE,
            "repo-vs-live LOAD CLASS divergence (the deployed turn-0 set differs from the repo's)",
        )
    )


# -------------------------------------------------------------------------- self-test
def _tree(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    return root


def self_test() -> int:
    """Both states for every check, and -- the part that matters -- an END-TO-END red-proof
    against real temp trees, not only the pure predicates.

    A predicate-only self-test proves the comparator can say NO about two sets handed to it.
    It does NOT prove ``measure()`` builds those sets from the filesystem correctly, which is
    the half that actually failed elsewhere in this program (a control that confirms the
    instrument ran is not a control that distinguishes the two hypotheses).
    """
    print("== r5_deploy_drift self-test (each check: FIRE broken, SILENT good) ==")
    cases: list[tuple[str, bool, bool]] = []

    base = {"common/a.md", "common/b.md"}
    cases.append(("delta / unchanged", bool(_delta(base, base, "x")), False))
    cases.append(
        ("delta / GREW", bool(_delta(base | {"common/c.md"}, base, "x")), True)
    )
    cases.append(
        (
            "delta / SHRANK (a repair)",
            bool(_delta(base - {"common/a.md"}, base, "x")),
            True,
        )
    )
    cases.append(("delta / empty vs empty", bool(_delta(set(), set(), "x")), False))

    always_on_body = "# no frontmatter -- turn-0\n"
    lazy_body = '---\npaths: ["**/*.py"]\n---\n# lazy\n'

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)

        # --- identical trees: the gate must be SILENT -------------------------------
        r = _tree(tmp / "r1", {"common/a.md": always_on_body, "common/b.md": lazy_body})
        live = _tree(
            tmp / "l1", {"common/a.md": always_on_body, "common/b.md": lazy_body}
        )
        m = measure(r, live)
        clean = not (
            m["always_on_drift"]
            or m["lazy_drift"]
            or m["only_in_repo"]
            or m["only_in_live"]
        )
        cases.append(("measure / identical trees report no drift", not clean, False))

        # --- CRLF ONLY: must NOT be reported as drift (the estate's phantom) ---------
        live_crlf = tmp / "l2"
        _tree(live_crlf, {"common/a.md": always_on_body, "common/b.md": lazy_body})
        (live_crlf / "common/a.md").write_bytes(
            always_on_body.replace("\n", "\r\n").encode()
        )
        m = measure(r, live_crlf)
        cases.append(
            (
                "measure / CRLF-only difference is NOT drift",
                bool(m["always_on_drift"]),
                False,
            )
        )
        cases.append(
            (
                "measure / ...but raw-byte counter still SEES it",
                m["raw_byte_differ"] == 0,
                False,
            )
        )

        # --- a real content change in an ALWAYS-ON rule ------------------------------
        live_ch = _tree(
            tmp / "l3",
            {"common/a.md": always_on_body + "CHANGED\n", "common/b.md": lazy_body},
        )
        m = measure(r, live_ch)
        cases.append(
            (
                "measure / always-on content change lands in always_on_drift",
                m["always_on_drift"] == {"common/a.md"},
                True,
            )
        )
        cases.append(
            ("measure / ...and NOT in lazy_drift", bool(m["lazy_drift"]), False)
        )

        # --- a real content change in a LAZY rule ------------------------------------
        live_lz = _tree(
            tmp / "l4",
            {"common/a.md": always_on_body, "common/b.md": lazy_body + "CHANGED\n"},
        )
        m = measure(r, live_lz)
        cases.append(
            (
                "measure / lazy content change is classified lazy",
                m["lazy_drift"] == {"common/b.md"},
                True,
            )
        )
        cases.append(
            ("measure / ...and NOT always-on", bool(m["always_on_drift"]), False)
        )

        # --- membership differences ---------------------------------------------------
        live_missing = _tree(tmp / "l5", {"common/b.md": lazy_body})
        m = measure(r, live_missing)
        cases.append(
            (
                "measure / undeployed file lands in only_in_repo",
                m["only_in_repo"] == {"common/a.md"},
                True,
            )
        )
        live_extra = _tree(
            tmp / "l6",
            {
                "common/a.md": always_on_body,
                "common/b.md": lazy_body,
                "common/z.md": "# live-only\n",
            },
        )
        m = measure(r, live_extra)
        cases.append(
            (
                "measure / live-only file lands in only_in_live",
                m["only_in_live"] == {"common/z.md"},
                True,
            )
        )

        # --- LOAD CLASS: the deployed copy changed what it costs at turn 0 ------------
        # The severity split above is computed from the REPO frontmatter, so without this the
        # gate could file a live-lazy rule under "read by every session right now".
        live_promoted = _tree(
            tmp / "l7",
            {
                "common/a.md": always_on_body,
                "common/b.md": "# frontmatter STRIPPED in deploy\n",
            },
        )
        m = measure(r, live_promoted)
        cases.append(
            (
                "measure / live copy PROMOTED to always-on is caught",
                m["load_class_divergence"] == {"common/b.md"},
                True,
            )
        )
        live_demoted = _tree(
            tmp / "l8",
            {
                "common/a.md": '---\npaths: ["**/*"]\n---\n# demoted\n',
                "common/b.md": lazy_body,
            },
        )
        m = measure(r, live_demoted)
        cases.append(
            (
                "measure / live copy DEMOTED out of turn-0 is caught",
                m["load_class_divergence"] == {"common/a.md"},
                True,
            )
        )
        m = measure(r, live_ch)
        cases.append(
            (
                "measure / a pure CONTENT change is NOT a load-class change",
                bool(m["load_class_divergence"]),
                False,
            )
        )

        # --- FAIL CLOSED on an empty walk ---------------------------------------------
        # The control that matters most: a broken walk and a clean tree produce the same
        # "0 differ", and this is the only check that can tell them apart.
        for label, a, b in (
            ("empty REPO tree", _tree(tmp / "e1", {}), live),
            ("empty LIVE tree", r, _tree(tmp / "e2", {})),
        ):
            try:
                measure(a, b)
                fired = False
            except RuntimeError:
                fired = True
            cases.append((f"measure / {label} fails CLOSED", fired, True))

    bad = [name for name, got, want in cases if got != want]
    for name, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {name:56} fired={got} want={want}")
    if bad:
        print(f"FAILED:r5_deploy_drift self-test {bad}")
        return 1
    print(f"SUCCESS:r5_deploy_drift self-test {len(cases)}/{len(cases)} checks behaved")
    return 0


# ------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="repo->live rule deploy-drift ratchet")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--print-measured", action="store_true", help="dump the measured sets as JSON"
    )
    ap.add_argument("--repo-root", type=pathlib.Path, default=DEFAULT_REPO_RULES)
    ap.add_argument("--live-root", type=pathlib.Path, default=DEFAULT_LIVE_RULES)
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.live_root.is_dir():
        # NOT a pass. The comparison was not performed, and the marker says so.
        print(
            "SUCCESS:r5_deploy_drift NOT-CHECKED -- live rules tree ABSENT (runner world). "
            "This run asserted NOTHING about repo-vs-live drift."
        )
        return 0

    try:
        m = measure(args.repo_root, args.live_root)
    except RuntimeError as exc:
        print(f"FAILED:r5_deploy_drift {exc}")
        return 1

    if args.print_measured:
        print(
            json.dumps(
                {k: (sorted(v) if isinstance(v, set) else v) for k, v in m.items()},
                indent=1,
            )
        )
        return 0

    print("== repo -> live rule deploy-drift ratchet ==")
    print("   world: live ~/.claude rules tree PRESENT")
    print(
        f"   scanned repo={m['repo_count']} live={m['live_count']} .md files; "
        f"LF-normalised differ={m['lf_normalised_differ']} "
        f"(raw-byte differ={m['raw_byte_differ']} -- the gap is line endings, not content)"
    )
    print(
        f"   always-on drift={len(m['always_on_drift'])} (every turn-0 prompt) · "
        f"lazy drift={len(m['lazy_drift'])} · only-in-repo={len(m['only_in_repo'])} · "
        f"only-in-live={len(m['only_in_live'])} · "
        f"load-class divergence={len(m['load_class_divergence'])}"
    )

    probs = problems(m)
    if probs:
        for p in probs:
            print(f"  FAIL {p}")
        print(
            f"FAILED:r5_deploy_drift {len(probs)} change(s) against the pinned baseline"
        )
        return 1

    for rel in sorted(m["always_on_drift"]):
        print(f"  pinned ALWAYS-ON drift (read by every session right now): {rel}")
    print(
        f"SUCCESS:r5_deploy_drift baseline holds: {len(m['always_on_drift'])} always-on + "
        f"{len(m['lazy_drift'])} lazy rules still undeployed, unchanged. "
        "Still DRIFTED, not fixed -- deploying is an owner action."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
