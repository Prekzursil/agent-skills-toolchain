#!/usr/bin/env python3
"""The rule-audit lane's CI entry point: make the shipped gates REACHABLE, and turn the
audit's two central measured facts into invariants a runner can enforce.

WHY THIS EXISTS.  Four rounds of audit + three adversarial rounds produced eight executable
gates in this directory, and **nothing in the repository ran any of them**.  Measured before
this file was written, with the search controlled in both directions (the same search finds
the wired ``test_rules_integrity`` in quality.yml, and is silent on a bogus token):

    rule_audit.py  lazy_predict.py  r2_control_count_gate.py  r2_failclosed_mutation.py
    r2_pathrefs.py  r3_corpus_parity_gate.py  r4_credential_rule_gate.py
    r4_receipt_argv_gate.py
        -> zero matches in .github/**, ci/**, and every *.toml/*.cfg in the repo.

A gate nobody invokes is indistinguishable from one that does not exist.

WHAT IT ASSERTS, in order:

  1. NO SILENT SHRINK.  Every ``*.py`` here is in ``CI_PLAN`` (with an expected exit code) or
     in ``EXCLUDED`` (with a written reason).  A file in neither fails the run, so the plan
     cannot quietly decay into "whatever still happened to pass".
  2. EVERY PLANNED GATE'S REAL EXIT CODE, captured per child.  A shell pipeline reports the
     LAST command's status, so ``gate.py | tail`` turns a red gate green; nothing here pipes.
  3. ALWAYS-ON SET (DoD-1).  The repo's always-on rules must be exactly ``ALWAYS_ON``.  This is
     the invariant the lane charter warns about from the wrong-intuition side: adding
     ``paths: ["**/*"]`` to a rule DEMOTES it out of the turn-0 prompt.  Nothing detected that
     before; a rule could gain or lose a ``paths:`` key and every one of the 167 rules tests
     would stay green, because none of them assert on load semantics.
  4. LOAD-SEMANTICS PARITY between the two IN-REPO trees.  ``rules/`` is deployed by
     scripts/sync-rules.ps1; ``agent-self/config/rules/`` is deployed by agent-self/bootstrap.ps1
     (``Copy-Item (Join-Path $Self 'config\\*') $ClaudeHome -Recurse -Force``).  Two deploy
     sources for one live tree, and they DISAGREE on three files -- measured, not assumed:
     common/git-workflow.md, common/hooks.md and common/security.md are paths-scoped (lazy) in
     ``rules/`` and carry no frontmatter (always-on) in ``agent-self/``.  Running bootstrap
     therefore silently PROMOTES three lazy rules into every turn-0 prompt.  The three are
     allowlisted with that reason; a fourth fails the run, and so does one disappearing --
     a fixed divergence must be recorded, not silently absorbed.

WHY 3 AND 4 ARE THE ONES WORTH GATING.  They need no ``~/.claude`` and no tokenizer, so they
mean the same thing on a runner as on the owner's box.  Everything that compares against the
LIVE tree cannot run in CI at all (see EXCLUDED), which is exactly why the repo-vs-live drift
grew from 28 to 29 files while 167 tests stayed green.

PLATFORM AND DEPENDENCY, MEASURED NOT ASSUMED.  Every gate here was authored on Windows.
Measured under WSL Ubuntu 24.04 (python 3.12.3) with HOME redirected to an empty dir, i.e. the
runner's world:
  * ``rule_audit.py --self-test`` fails 2/19 controls -- ``encoder is tiktoken/cl100k_base``
    and ``known string -> known count`` -- because ``Counter`` degrades to ``ESTIMATE chars/4``
    when tiktoken is absent, and ``round(len("hello world")/4) == 3 != 2``.  Those two controls
    exist precisely to stop estimate-derived token numbers being certified as exact.
  * ``r2_control_count_gate.py`` and ``r2_failclosed_mutation.py`` cascade red off that same
    self-test; the latter correctly reports ``control is inert`` rather than a pass, because
    its clean arm and its mutant arm both fail and it can no longer tell them apart.
  => The workflow installs tiktoken.  UNVERIFIED end-to-end: this box's WSL has no DNS
  (``Temporary failure in name resolution``), so "with tiktoken installed, Linux goes 19/19"
  is derived from the mechanism above plus Windows-with-tiktoken measuring 19/19, NOT executed
  on Linux.  Settling experiment: the first run of .github/workflows/rule-audit.yml on a
  runner, which has network -- that step's log settles it either way.

NO PRODUCER-DETERMINISM CHECK, deliberately.  The sibling mcp-audit gate re-runs its producers
and demands byte-identity with the committed artifact.  ``rule-audit.json`` cannot be checked
that way: it embeds live-tree counts and tiktoken token numbers, so it is not reproducible on
a runner at all.  Claiming that check here would be a control that cannot distinguish its two
hypotheses.

LANE-SCOPED NAME.  ``command-center/mcp-audit/ci_gate.py`` exists and is a DIFFERENT gate: it
wires that lane's 14 gates, pins historical blobs, and byte-checks two producers.  It shares
no code with this one -- it hardcodes its own directory, its own CI_PLAN and its own EXCLUDED
reasons, so there is nothing to import.  Same role, same naming convention, deliberately
separate implementations: the convention this repo already uses for ``_i1_ci_portability.py``
and ``_i3_redproof.py`` in two lanes each.

Run::

    python docs/rule-audit/ci_gate.py
    python docs/rule-audit/ci_gate.py --self-test
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SELF = pathlib.Path(__file__).name

sys.path.insert(0, str(HERE))
import rule_audit  # noqa: E402  (same-directory sibling; the audit's own classifier)

# --------------------------------------------------------------------------- the plan
# (label, argv, expected exit code).  Chosen from measurement -- see the module docstring.
CI_PLAN: list[tuple[str, list[str], int]] = [
    ("rule_audit --self-test (19 controls)", ["rule_audit.py", "--self-test"], 0),
    ("r2_pathrefs --self-test (6 gate states)", ["r2_pathrefs.py", "--self-test"], 0),
    ("r2_control_count_gate", ["r2_control_count_gate.py"], 0),
    ("r2_failclosed_mutation", ["r2_failclosed_mutation.py"], 0),
    ("r4_receipt_argv_gate", ["r4_receipt_argv_gate.py"], 0),
    # BOTH STATES.  The credential inversion in agent-self/config/AGENTS.md is REAL, unfixed,
    # and deliberately left to the owner (AGENTS.md section 9 -- credential policy is not this
    # lane's to change).  Pinning it at rc=1 keeps a known defect TRACKED instead of silently
    # tolerated: the day it is repaired this entry goes red, and whoever repaired it has to
    # promote the gate to a blocking rc=0 in the same change.
    (
        "r4_credential_rule_gate (must FAIL: owner action)",
        ["r4_credential_rule_gate.py"],
        1,
    ),
]

# --------------------------------------------------- the invariants (DoD-1 and deploy parity)
# The repo's always-on rules: no frontmatter at all, therefore loaded at launch with CLAUDE.md
# priority.  Reproduced twice this round (17,107 tok over these 8; 63,294 over all 88).
ALWAYS_ON: set[str] = {
    "common/agents.md",
    "common/bash-hud-and-terminal-emit.md",
    "common/cross-vendor-dispatch.md",
    "common/fan-out-contract.md",
    "common/harness-vcs-hygiene.md",
    "common/single-signal-verification.md",
    "common/stale-megapr-reconcile.md",
    "common/windows-shell.md",
}

# rel-path -> why the two in-repo deploy sources are allowed to disagree about load semantics.
ALLOWED_LOAD_DIVERGENCE: dict[str, str] = {
    "common/git-workflow.md": (
        "agent-self copy carries no frontmatter (always-on); rules/ copy is paths-scoped "
        "(lazy). bootstrap.ps1 would promote it into every turn-0 prompt."
    ),
    "common/hooks.md": (
        "same shape: no frontmatter in agent-self, paths-scoped in rules/. Its selectors "
        "(**/hooks/**, **/settings*.json, **/.claude/**) are why it stays absent until one "
        "of those is touched -- the negative control the grounding round used."
    ),
    "common/security.md": (
        "same shape. The always-on security floor is AGENTS.md section 9; this file is the "
        "code-turn-scoped checklist, so paths-scoping it in rules/ is the deliberate form."
    ),
}

# ------------------------------------------------------------------------------ excluded
# Every remaining *.py, with the reason it is NOT a per-PR gate.  A file in neither table
# fails the run -- silence is not an acceptable classification.
_LIVE_DEP = (
    "reads the live ~/.claude tree; measured rc 0 -> 1 with HOME redirected to an empty dir "
    "(_i1_ci_portability.json), so on a runner it fails closed and cannot be a CI gate"
)
_LANE_PROBE = "one-shot lane probe retained as the evidence trail; a measurement, not a per-PR assertion"

EXCLUDED: dict[str, str] = {
    SELF: "this gate itself",
    # --- shipped gates that genuinely cannot run on a runner -------------------------
    "lazy_predict.py": _LIVE_DEP
    + " (FAILED:lazy_predict live rules tree scanned to zero)",
    "r3_corpus_parity_gate.py": _LIVE_DEP
    + " (FAILED:r3_corpus_parity the mutation did not turn the gate red -- gate inert)",
    # --- probes that read the live tree ----------------------------------------------
    "_adv3_deploydrift.py": _LIVE_DEP,
    "_adv3_probe.py": _LIVE_DEP,
    "_adv_indep_classify.py": _LIVE_DEP,
    "_r4_mention_composition.py": _LIVE_DEP,
    "_verify_pathrefs.py": _LIVE_DEP,
    "_r5_grounding_probe.py": _LIVE_DEP + "; round-5 grounding probe",
    "_i1_ci_portability.py": (
        "one-shot portability MEASUREMENT (27 scripts x {real HOME, empty HOME}); it CHOSE "
        "this CI_PLAN and must not run per PR -- it spawns every script in this directory"
    ),
    # --- writes to tracked files: never run unattended --------------------------------
    "_r4_mark_mentions.py": "mutates tracked markdown in place; never run in CI",
    # --- round-1..4 lane probes -------------------------------------------------------
    "_adv2_probe.py": _LANE_PROBE,
    "_adv3_baseattr.py": _LANE_PROBE,
    "_adv_readme_block.py": _LANE_PROBE,
    "_probe_alwayson_diff.py": _LANE_PROBE,
    "_probe_alwayson_tokens.py": _LANE_PROBE,
    "_probe_bootstrap_delta.py": _LANE_PROBE,
    "_probe_lazy_observed.py": _LANE_PROBE,
    "_probe_rule_inventory.py": _LANE_PROBE,
    "_probe_semantics_disagree.py": _LANE_PROBE,
    "_probe_summarize.py": _LANE_PROBE,
    "_probe_threeway.py": _LANE_PROBE,
    "_r2_blobcheck.py": _LANE_PROBE + "; needs `uvx ruff@0.15.17`",
    "_r4_inventory_probe.py": _LANE_PROBE,
    "_verify_failclosed.py": _LANE_PROBE
    + "; its both-states case was folded into rule_audit --self-test in round 2",
    # --- build round 1: the measurements that chose the plan above ---------------------
    "_b1_gate_runner.py": (
        "BUILD-R1: ran all 8 gates bare to find which execute at all (5 pass, 2 slow-but-"
        "finite, 1 fails). Spawns every gate; a measurement, not an assertion"
    ),
    "_b2_slowgate_probe.py": (
        "BUILD-R1: distinguished HUNG from SLOW for the two gates that hit a 120 s cap "
        "(r2_pathrefs 110.5 s rc=2, r3_corpus_parity 89.0 s rc=0)"
    ),
    "_b3_portability.py": (
        "BUILD-R1: bare-argv x {Windows, Linux} x no-HOME sweep; the gaps _i1 left open. "
        "Chose the argv in CI_PLAN and found rule_audit.py bare is fail-OPEN on a runner"
    ),
    "_b4_read_i1.py": "BUILD-R1: reads _i1_ci_portability.json; a formatter, asserts nothing",
    "_b5_tiktoken.py": (
        "BUILD-R1: reports whether tiktoken is importable and what Counter falls back to; "
        "the direct second signal for the encoder-control failure"
    ),
    "_b9_preflight.py": (
        "BUILD-R1: computes the POST-COMMIT tracked *.py set and runs classify() against it, "
        "so an EXCLUDED-but-uncommitted probe (a ghost on a fresh clone) is caught before the "
        "commit rather than by a red runner. Working-tree green is not clone green"
    ),
    "_b8_redproof.py": (
        "BUILD-R1 RED-PROOF for invariants 3 and 4: copies both in-repo rule trees to a temp "
        "dir, mutates the copies (demote / promote / new divergence / repaired divergence / "
        "empty tree) and requires measure_trees() to fire on each and stay silent on the "
        "untouched control. It repoints rule_audit.TREES, so it runs alone, not per PR"
    ),
    "_b7_normalize_lf.py": (
        "BUILD-R1: strips CR bytes from a file (windows-shell section 3, agent-written .sh "
        "under real WSL bash); a utility, asserts nothing"
    ),
}


# --------------------------------------------------------------------- pure predicates
def classify(present: set[str]) -> tuple[list[str], list[str]]:
    """(files in neither table, files in a table but absent from disk)."""
    planned = {argv[0] for _, argv, _ in CI_PLAN}
    known = planned | set(EXCLUDED)
    return sorted(present - known), sorted(known - present)


def verdict(results: list[dict[str, Any]]) -> list[str]:
    """Labels whose REAL exit code did not match the expected one."""
    return [r["label"] for r in results if r["rc"] != r["expect"]]


def always_on_problems(measured: set[str], expected: set[str]) -> list[str]:
    """DoD-1 invariant. Both directions: a promotion AND a demotion must both be caught."""
    problems = []
    for rel in sorted(measured - expected):
        problems.append(
            f"always-on set GAINED {rel!r}: it lost its `paths:` selector, so it is now in "
            "every turn-0 prompt. Intentional? add it to ALWAYS_ON"
        )
    for rel in sorted(expected - measured):
        problems.append(
            f"always-on set LOST {rel!r}: it gained a `paths:` selector, which DEMOTES it out "
            'of the turn-0 prompt (adding `paths: ["**/*"]` does this). Intentional? remove '
            "it from ALWAYS_ON"
        )
    return problems


def divergence_problems(measured: set[str], allowed: set[str]) -> list[str]:
    """Deploy-source parity. A NEW divergence fails; a REPAIRED one fails too, so that the
    repair is recorded rather than silently absorbed into the allowlist's silence."""
    problems = []
    for rel in sorted(measured - allowed):
        problems.append(
            f"NEW load-semantics divergence {rel!r} between rules/ and agent-self/config/rules/"
            " -- one tree would deploy it always-on and the other lazy"
        )
    for rel in sorted(allowed - measured):
        problems.append(
            f"allowlisted divergence {rel!r} is GONE -- the two trees now agree. Good: drop it "
            "from ALLOWED_LOAD_DIVERGENCE in the same change"
        )
    return problems


# ------------------------------------------------------------------------- measurement
def measure_trees() -> tuple[set[str], set[str]]:
    """(repo always-on set, repo-vs-agent-self load-semantics divergence set).

    Touches ONLY the two in-repo trees -- never ``~/.claude`` -- so it means the same thing on
    a runner as on the owner's box.  Uses the audit's own classifier rather than a second
    implementation of the frontmatter rules.
    """
    counter = rule_audit.Counter()
    repo = rule_audit.scan_tree(rule_audit.TREES["repo"], counter)
    agent_self = rule_audit.scan_tree(rule_audit.TREES["agent-self"], counter)
    if not repo:
        raise RuntimeError("repo rules/ tree scanned to zero files -- detector broken")
    if not agent_self:
        raise RuntimeError(
            "agent-self rules tree scanned to zero files -- detector broken"
        )
    always_on = {
        rel
        for rel, info in repo.items()
        if info["load"] in ("always_on_no_frontmatter", "frontmatter_without_paths")
    }
    diverge = set(rule_audit.diff_trees(repo, agent_self)["load_semantics_differs"])
    return always_on, diverge


def run(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, *argv],
        cwd=HERE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    marker = next(
        (ln for ln in reversed(out) if ln.startswith(("SUCCESS:", "FAILED:"))),
        (out[-1] if out else "<no stdout>"),
    )
    if proc.returncode != 0 and (proc.stderr or "").strip():
        marker = f"{marker}  |stderr| {proc.stderr.strip().splitlines()[-1][:110]}"
    return proc.returncode, marker.strip()[:190]


# --------------------------------------------------------------------------- self-test
def self_test() -> int:
    """Both states for every check this gate makes. A gate never seen red is a no-op."""
    print("== rule-audit ci_gate self-test (each check: FIRE broken, SILENT good) ==")
    cases: list[tuple[str, bool, bool]] = []

    planned = {argv[0] for _, argv, _ in CI_PLAN}
    good = planned | set(EXCLUDED)
    u, g = classify(good)
    cases.append(("classify / complete inventory", bool(u or g), False))
    cases.append(
        ("classify / unclassified file", bool(classify(good | {"_new.py"})[0]), True)
    )
    cases.append(
        (
            "classify / planned file absent from disk",
            bool(classify(good - {"rule_audit.py"})[1]),
            True,
        )
    )

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
    # Without this, the both-states pair silently degrades into a one-state check.
    cases.append(
        (
            "verdict / an expected-FAIL gate started passing",
            bool(verdict([{"label": "b", "rc": 0, "expect": 1}])),
            True,
        )
    )

    base = {"common/agents.md", "common/windows-shell.md"}
    cases.append(("always_on / unchanged", bool(always_on_problems(base, base)), False))
    cases.append(
        (
            "always_on / a rule was PROMOTED",
            bool(always_on_problems(base | {"common/x.md"}, base)),
            True,
        )
    )
    cases.append(
        (
            "always_on / a rule was DEMOTED by paths:",
            bool(always_on_problems(base - {"common/agents.md"}, base)),
            True,
        )
    )

    dv = {"common/hooks.md"}
    cases.append(("divergence / unchanged", bool(divergence_problems(dv, dv)), False))
    cases.append(
        (
            "divergence / a NEW one appeared",
            bool(divergence_problems(dv | {"common/y.md"}, dv)),
            True,
        )
    )
    cases.append(
        ("divergence / one was repaired", bool(divergence_problems(set(), dv)), True)
    )

    bad = [name for name, got, want in cases if got != want]
    for name, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {name:46} fired={got} want={want}")

    # A plan or an allowlist that shrank to nothing would pass every case above.
    if len(CI_PLAN) < 6:
        print(f"FAILED:rule-audit-ci-gate self-test CI_PLAN shrank to {len(CI_PLAN)}")
        return 1
    if len(ALWAYS_ON) < 8 or len(ALLOWED_LOAD_DIVERGENCE) != 3:
        print(
            f"FAILED:rule-audit-ci-gate self-test allowlists shrank "
            f"(always_on={len(ALWAYS_ON)}, divergence={len(ALLOWED_LOAD_DIVERGENCE)})"
        )
        return 1
    if not any(expect != 0 for _, _, expect in CI_PLAN):
        print(
            "FAILED:rule-audit-ci-gate self-test no expected-FAIL entry left -- both-states lost"
        )
        return 1
    if bad:
        print(f"FAILED:rule-audit-ci-gate self-test {bad}")
        return 1
    print(
        f"SUCCESS:rule-audit-ci-gate self-test {len(cases)}/{len(cases)} checks behaved"
    )
    return 0


# -------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    print(
        f"== rule-audit CI gate ({sys.platform}, py {sys.version.split()[0]}, "
        f"encoder {rule_audit.Counter().name}) =="
    )

    unclassified, ghosts = classify({p.name for p in HERE.glob("*.py")})
    if unclassified:
        print(
            "FAILED:rule-audit-ci-gate new file(s) in neither CI_PLAN nor EXCLUDED: "
            f"{unclassified} -- add it to one, with a reason (fail closed)"
        )
        return 1
    if ghosts:
        print(f"FAILED:rule-audit-ci-gate listed but absent from disk: {ghosts}")
        return 1
    print(
        f"  ok  inventory: {len(CI_PLAN)} planned runs over "
        f"{len({a[0] for _, a, _ in CI_PLAN})} gates, {len(EXCLUDED)} excluded with reasons"
    )

    problems: list[str] = []
    results: list[dict[str, Any]] = []
    for label, gate_argv, expect in CI_PLAN:
        rc, marker = run(gate_argv)
        results.append({"label": label, "rc": rc, "expect": expect})
        print(
            f"  {'ok ' if rc == expect else 'BAD'} rc={rc} (want {expect})  {label:40} {marker}"
        )
    problems += verdict(results)

    print("  -- in-repo invariants (no ~/.claude, no tokenizer) --")
    try:
        measured_always_on, measured_divergence = measure_trees()
    except RuntimeError as exc:
        print(f"FAILED:rule-audit-ci-gate {exc}")
        return 1
    ao = always_on_problems(measured_always_on, ALWAYS_ON)
    dv = divergence_problems(measured_divergence, set(ALLOWED_LOAD_DIVERGENCE))
    if not ao:
        print(f"  ok  always-on set is exactly the expected {len(ALWAYS_ON)} rules")
    if not dv:
        print(
            f"  ok  load-semantics divergence is exactly the {len(ALLOWED_LOAD_DIVERGENCE)} "
            "allowlisted rules"
        )
    problems += ao + dv

    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        print(f"FAILED:rule-audit-ci-gate {len(problems)} problem(s)")
        return 1
    print(
        f"SUCCESS:rule-audit-ci-gate {len(results)}/{len(results)} gates behaved, "
        f"always-on={len(measured_always_on)}, divergence={len(measured_divergence)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
