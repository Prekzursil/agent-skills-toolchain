"""BUILD-R1 RED-PROOF: does ci_gate's measurement path really go red on a real defect?

ci_gate --self-test exercises the PURE PREDICATES with hand-made sets.  That proves the
comparison logic, and nothing about whether the classifier, reading real bytes off real
files, actually notices a rule whose frontmatter changed.  A gate whose predicates are
tested but whose measurement is not is the "control that cannot distinguish the two
hypotheses" shape: it passes, and you record it as diligence.

So: copy BOTH in-repo rule trees to a temp dir, mutate the copies, repoint
``rule_audit.TREES`` at them, and require ci_gate's own ``measure_trees()`` +
``always_on_problems()`` + ``divergence_problems()`` to FIRE on each mutation and stay
SILENT on the untouched copy.

THE REPO IS NEVER MODIFIED.  Everything happens under tempfile.TemporaryDirectory(); the
real TREES mapping is restored in a finally block.

Run::

    python docs/rule-audit/_b8_redproof.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ci_gate  # noqa: E402
import rule_audit  # noqa: E402

# A rule that is always-on in rules/ (no frontmatter) and a rule that is lazy (paths-scoped).
ALWAYS_ON_VICTIM = "common/agents.md"
LAZY_VICTIM = "common/testing.md"
PATHS_FRONTMATTER = '---\npaths: ["**/*"]\n---\n'


def strip_frontmatter(text: str) -> str:
    match = rule_audit.FRONTMATTER_RE.match(text)
    return text[match.end() :] if match else text


def evaluate(repo_root: Path, self_root: Path) -> list[str]:
    """Run ci_gate's real measurement against the two given trees."""
    original = dict(rule_audit.TREES)
    try:
        rule_audit.TREES["repo"] = repo_root
        rule_audit.TREES["agent-self"] = self_root
        always_on, divergence = ci_gate.measure_trees()
    finally:
        rule_audit.TREES.clear()
        rule_audit.TREES.update(original)
    return ci_gate.always_on_problems(
        always_on, ci_gate.ALWAYS_ON
    ) + ci_gate.divergence_problems(divergence, set(ci_gate.ALLOWED_LOAD_DIVERGENCE))


def main() -> int:
    cases: list[tuple[str, bool, bool]] = []

    with tempfile.TemporaryDirectory(prefix="rule-audit-redproof-") as tmp:
        base = Path(tmp)
        pristine_repo = base / "clean" / "rules"
        pristine_self = base / "clean" / "agent-self"
        shutil.copytree(rule_audit.TREES["repo"], pristine_repo)
        shutil.copytree(rule_audit.TREES["agent-self"], pristine_self)

        # ---- CONTROL: an untouched copy must be silent -----------------------------
        clean = evaluate(pristine_repo, pristine_self)
        cases.append(("CONTROL untouched copies -> silent", bool(clean), False))
        if clean:
            print("  control detail:", clean[:2])

        # ---- MUTATION 1: DEMOTE an always-on rule by adding paths: ------------------
        m1_repo = base / "m1" / "rules"
        m1_self = base / "m1" / "agent-self"
        shutil.copytree(pristine_repo, m1_repo)
        shutil.copytree(pristine_self, m1_self)
        victim = m1_repo / ALWAYS_ON_VICTIM
        victim.write_text(
            PATHS_FRONTMATTER + victim.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        fired = evaluate(m1_repo, m1_self)
        cases.append(
            (f"DEMOTE {ALWAYS_ON_VICTIM} via paths: -> fires", bool(fired), True)
        )
        if fired:
            print(f"  m1 says: {fired[0][:150]}")

        # ---- MUTATION 2: PROMOTE a lazy rule by stripping its frontmatter -----------
        m2_repo = base / "m2" / "rules"
        m2_self = base / "m2" / "agent-self"
        shutil.copytree(pristine_repo, m2_repo)
        shutil.copytree(pristine_self, m2_self)
        victim = m2_repo / LAZY_VICTIM
        victim.write_text(
            strip_frontmatter(victim.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        fired = evaluate(m2_repo, m2_self)
        cases.append(
            (f"PROMOTE {LAZY_VICTIM} by stripping paths: -> fires", bool(fired), True)
        )
        if fired:
            print(f"  m2 says: {fired[0][:150]}")

        # ---- MUTATION 3: a FOURTH deploy-source divergence --------------------------
        # Strip the frontmatter from the agent-self copy of a rule that is lazy in BOTH
        # trees, so the two deploy sources start disagreeing about a file they agreed on.
        m3_repo = base / "m3" / "rules"
        m3_self = base / "m3" / "agent-self"
        shutil.copytree(pristine_repo, m3_repo)
        shutil.copytree(pristine_self, m3_self)
        victim = m3_self / LAZY_VICTIM
        if not victim.is_file():
            print(
                f"FAILED:b8_redproof {LAZY_VICTIM} absent from agent-self -- pick another"
            )
            return 1
        victim.write_text(
            strip_frontmatter(victim.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        fired = evaluate(m3_repo, m3_self)
        cases.append((f"NEW divergence on {LAZY_VICTIM} -> fires", bool(fired), True))
        if fired:
            print(f"  m3 says: {fired[0][:150]}")

        # ---- MUTATION 4: REPAIR an allowlisted divergence ---------------------------
        # Make agent-self agree with rules/ on one allowlisted file. The gate must still
        # fire, so the repair is recorded rather than silently absorbed.
        m4_repo = base / "m4" / "rules"
        m4_self = base / "m4" / "agent-self"
        shutil.copytree(pristine_repo, m4_repo)
        shutil.copytree(pristine_self, m4_self)
        allow = sorted(ci_gate.ALLOWED_LOAD_DIVERGENCE)[0]
        shutil.copy2(m4_repo / allow, m4_self / allow)
        fired = evaluate(m4_repo, m4_self)
        cases.append((f"REPAIR divergence on {allow} -> fires", bool(fired), True))
        if fired:
            print(f"  m4 says: {fired[0][:150]}")

        # ---- MUTATION 5: detector-broken tree --------------------------------------
        empty = base / "empty"
        empty.mkdir()
        try:
            evaluate(empty, pristine_self)
            cases.append(("EMPTY repo tree -> RuntimeError", False, True))
        except RuntimeError:
            cases.append(("EMPTY repo tree -> RuntimeError", True, True))

    print()
    bad = [name for name, got, want in cases if got != want]
    for name, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {name:56} fired={got} want={want}")
    if bad:
        print(f"FAILED:b8_redproof {len(bad)} case(s) misbehaved: {bad}")
        return 1
    print(
        f"SUCCESS:b8_redproof {len(cases)}/{len(cases)} states behaved on REAL file bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
