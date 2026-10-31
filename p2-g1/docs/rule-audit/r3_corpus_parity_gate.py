"""R3 gate: the sweep's corpus and the audit's DECLARED corpus must be the same set of trees.

The CONFIRMED defect of round 2 was not a wrong sentence and not broken code -- it was a silent
divergence between the two. ``rule_audit.TREES`` declares the corpus as three rule trees (repo,
agent-self, live) and every DoD-1 count in the artifact is derived from it: 254 files. Meanwhile
``r2_pathrefs.TREES`` held two. The sweep then reported ``scanned=176`` and the artifact reported
"MEASURED: no tenth contradiction", and nothing anywhere connected those two numbers, so the
sentence was free to be wider than the instrument. Widening the sweep found a real broken pointer
in the excluded third of the corpus (``RULE-AUDIT.md`` §3.10).

Round 2 met the control-count overclaim by binding the prose to the tool's own output. This is the
same medicine for the corpus dimension: bind the SWEEP to the AUDIT, so the two cannot drift apart
again without a gate going red.

Two mechanically independent bindings, because either one alone has a blind spot:

    paths   ``rule_audit.TREES`` == ``r2_pathrefs.TREES``, compared as resolved paths. Catches a
            tree added to one module and not the other -- the exact round-2 defect.
    count   the ``*.md`` count ``r2_pathrefs`` REPORTS at runtime == the count ``rule_audit``'s own
            scanner enumerates over its trees. Catches what a path comparison cannot: identical
            tree sets where one module's walk silently visits fewer files (a changed glob, an
            early ``continue``, a skipped subdirectory).

BOTH STATES, in one invocation. A parity gate that only ever sees a matching pair proves nothing,
so this does not merely assert -- it RE-CREATES the round-2 defect by reducing the sweep's trees
to ``{live, repo}`` and re-running the real sweep, and requires the checker to go red on both
bindings. If that mutation does not fire, the gate is inert and says so.

Fails closed on an empty tree map, an unparseable sweep, or a zero-file corpus.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

rule_audit = importlib.import_module("rule_audit")
r2_pathrefs = importlib.import_module("r2_pathrefs")

SCANNED_RE = re.compile(r"rule files scanned: (\d+) across (\d+) trees")


def resolved(trees: dict[str, Path]) -> dict[str, str]:
    return {name: Path(root).resolve().as_posix() for name, root in trees.items()}


def sweep_scanned() -> int | None:
    """Run the real sweep and read the file count IT reports having visited.

    Exit code is deliberately ignored: the sweep exits 2 while a tracked out-of-scope defect is
    live, and that is orthogonal to whether its corpus matches the audit's.
    """
    with contextlib.redirect_stdout(io.StringIO()) as out:
        r2_pathrefs.main()
    match = SCANNED_RE.search(out.getvalue())
    return int(match.group(1)) if match else None


def audit_corpus_size() -> int:
    """How many rule files the AUDIT tool's own scanner enumerates over its own trees."""
    counter = rule_audit.Counter()
    return sum(
        len(rule_audit.scan_tree(root, counter)) for root in rule_audit.TREES.values()
    )


def violations(
    audit_trees: dict[str, str],
    sweep_trees: dict[str, str],
    audit_n: int,
    sweep_n: int | None,
) -> list[str]:
    """The pure checker. Called on the real pair AND on a deliberately broken one."""
    bad: list[str] = []
    for name in sorted(set(audit_trees) - set(sweep_trees)):
        bad.append(
            f"tree {name!r} is in the declared corpus but NOT swept "
            f"({audit_trees[name]}) -- this is the round-2 defect"
        )
    for name in sorted(set(sweep_trees) - set(audit_trees)):
        bad.append(f"tree {name!r} is swept but is not part of the declared corpus")
    for name in sorted(set(audit_trees) & set(sweep_trees)):
        if audit_trees[name] != sweep_trees[name]:
            bad.append(
                f"tree {name!r} resolves differently: audit {audit_trees[name]} "
                f"vs sweep {sweep_trees[name]}"
            )
    if sweep_n is None:
        bad.append("the sweep printed no scanned-file count -- cannot bind the corpora")
    elif sweep_n != audit_n:
        bad.append(
            f"file counts disagree: the audit enumerates {audit_n}, the sweep visited {sweep_n}"
        )
    return bad


def main() -> int:
    audit_trees = resolved(rule_audit.TREES)
    sweep_trees = resolved(r2_pathrefs.TREES)
    if not audit_trees or not sweep_trees:
        print("FAILED:r3_corpus_parity empty tree map -- nothing compared, fail closed")
        return 1

    audit_n = audit_corpus_size()
    if audit_n == 0:
        print("FAILED:r3_corpus_parity audit enumerated 0 rule files -- fail closed")
        return 1
    sweep_n = sweep_scanned()

    print(
        f"declared corpus (rule_audit.TREES) : {sorted(audit_trees)}  files={audit_n}"
    )
    print(
        f"swept corpus (r2_pathrefs.TREES)   : {sorted(sweep_trees)}  files={sweep_n}"
    )

    real = violations(audit_trees, sweep_trees, audit_n, sweep_n)

    # BOTH STATES: re-create the round-2 defect against the REAL sweep, not a stub.
    print("")
    print("both-states control (re-creating the round-2 two-tree sweep):")
    original = r2_pathrefs.TREES
    try:
        r2_pathrefs.TREES = {k: v for k, v in original.items() if k in ("live", "repo")}
        broken_trees = resolved(r2_pathrefs.TREES)
        broken_n = sweep_scanned()
        broken = violations(audit_trees, broken_trees, audit_n, broken_n)
    finally:
        r2_pathrefs.TREES = original

    missing_fired = any("NOT swept" in v for v in broken)
    count_fired = any("counts disagree" in v for v in broken)
    for line in broken:
        print(f"  MUTANT sees: {line}")
    print(f"  mutant swept {broken_n} files (real sweep: {sweep_n})")
    print(f"  path binding fires on the mutant : {'PASS' if missing_fired else 'FAIL'}")
    print(f"  count binding fires on the mutant: {'PASS' if count_fired else 'FAIL'}")
    if not (missing_fired and count_fired):
        print(
            "FAILED:r3_corpus_parity the mutation did not turn the gate red -- gate inert, "
            "its green means nothing"
        )
        return 1

    print("")
    if real:
        for line in real:
            print(f"  MISMATCH {line}")
        print(f"FAILED:r3_corpus_parity {len(real)} mismatch(es)")
        return 1
    print(
        f"SUCCESS:r3_corpus_parity {len(audit_trees)} trees / {audit_n} files declared == swept, "
        f"and the two-tree mutation fires on both bindings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
