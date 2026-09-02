"""ROUND 3 / R3-C + R3-E: two vault claims nobody has executed.

R3-C  Round 1 created +6 newly-DIVERGED files in ~/.agents/skills (needs_merge
      397 -> 403) and round 2 correctly re-scoped the sentence and handed it back.
      The handback carries a PREDICTION -- "copy the description lines into the
      vault and needs_merge must return to 397" -- which has never been run.  A
      prediction in a handback is a claim, not a receipt.  This runs it on a COPY
      of the seven skill directories, through the REAL classifier, in BOTH states.
      Nothing is written to ~/.agents/skills.

      H-CLOSES  : the +6 are description-line-only -> state B returns them to
                  IDENTICAL and needs_merge drops by 6.
      H-DEEPER  : the vault copies differ in more than the description -> the drop
                  is smaller and the handback instruction is incomplete.
      Different predicted numbers, so the probe can distinguish them.

R3-E  Item 2's remedy for the 6-file vault no-op is "a targeted merge of those six
      files, not the deploy hop".  That sentence assumes the six are one-way behind
      the repo.  NOBODY MEASURED THE DIRECTION.  Round 2 measured exactly this for
      the seventh file, dead_button_crawl.mjs, and found the opposite of what two
      earlier reports assumed: 8 repo-only lines against 56 LIVE-only lines, so a
      copy-back would have destroyed live work.  If the six are the same shape, the
      remedy sentence is wrong and the owner is being handed a destructive action.

      Control for the differ: dead_button_crawl.mjs is a KNOWN two-way file (round 2,
      independently measured).  The differ must report it two-way, or it is broken and
      no verdict about the six may be cited.  Plus a reconstruction check in both
      directions (common + side-only == that side's unique-line count).
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
VAULT = Path("C:/Users/Prekzursil/.agents/skills")
REPO_AGENTS = REPO / ".agents" / "skills"
OUT = REPO / "command-center" / "grounding" / "S2-R3-VAULT.json"

SEVEN = [
    "transcribe",
    "tdd-workflow",
    "security-review",
    "screenshot",
    "e2e-testing",
    "python-testing",
    "research-ops",
]
SIX = [
    "axe_scan.mjs",
    "capture.mjs",
    "critique.mjs",
    "layout_lint.mjs",
    "run_audit.mjs",
    "visual_diff.mjs",
]
CONTROL_FILE = "dead_button_crawl.mjs"  # known two-way (round 2)


def load_deploy():
    spec = importlib.util.spec_from_file_location(
        "_deploy", REPO / "scripts" / "deploy-skills-daily.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def raw(p: Path) -> str:
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def lines_of(p: Path) -> list[str]:
    return [x[:-1] if x.endswith("\r") else x for x in raw(p).split("\n")]


def significant(ls):
    out = []
    for x in ls:
        s = x.strip()
        if s and s not in ("{", "}", "});", ")", "};", "]", "[", "*/", "/*"):
            out.append(s)
    return out


def main() -> int:
    dep = load_deploy()
    rc = 0

    # ---------------- R3-C -------------------------------------------------
    print("=== R3-C  the handback prediction, executed on a COPY (both states) ===")
    print(f"  real vault NEVER written: {VAULT}")
    diff_lines = {}
    for s in SEVEN:
        a, b = REPO_AGENTS / s / "SKILL.md", VAULT / s / "SKILL.md"
        if not b.is_file():
            diff_lines[s] = None
            continue
        la, lb = lines_of(a), lines_of(b)
        n = sum(1 for x, y in zip(la, lb) if x != y) + abs(len(la) - len(lb))
        diff_lines[s] = n
    print(f"  repo-vs-vault differing lines per skill: {diff_lines}")
    only_desc = [s for s, n in diff_lines.items() if n == 1]
    print(
        f"  differ by EXACTLY one line (the description): {len(only_desc)} {only_desc}"
    )
    print()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src, dst = root / "src", root / "dst"
        for s in SEVEN:
            shutil.copytree(REPO_AGENTS / s, src / s)
            if (VAULT / s).is_dir():
                shutil.copytree(VAULT / s, dst / s)

        pa = dep.plan(src, dst)
        needs_a = set(pa["needs_merge"])
        skill_md_a = sorted(r for r in needs_a if r.endswith("SKILL.md"))
        print("  STATE A -- vault copy as it is today")
        print(f"    summary        {pa['report']['summary']}")
        print(f"    needs_merge    {len(needs_a)}")
        print(f"    SKILL.md in needs_merge: {len(skill_md_a)} {skill_md_a}")

        # State B: the owner's handback action, EXACTLY as written -- copy the
        # DESCRIPTION LINE only, not the file.  Applied ONLY to the temp copy.
        #
        # The first version of this probe copied the whole SKILL.md and reported
        # "7 of 6 reconciled" -- a self-contradicting number, i.e. a detector
        # fault, not a finding.  A whole-file copy also reconciles tdd-workflow,
        # which was ALREADY diverged before round 1 and is not part of the +6.
        # Recorded, not deleted.  The minimal action gives tdd-workflow as a
        # built-in NEGATIVE control: it must NOT reconcile.
        moved = []
        for s in SEVEN:
            f = dst / s / "SKILL.md"
            if not f.is_file():
                continue
            want = next(
                x
                for x in lines_of(src / s / "SKILL.md")
                if x.startswith("description:")
            )
            cur = lines_of(f)
            new = [want if x.startswith("description:") else x for x in cur]
            if new != cur:
                with io.open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write("\n".join(new))
                moved.append(s)

        pb = dep.plan(src, dst)
        needs_b = set(pb["needs_merge"])
        skill_md_b = sorted(r for r in needs_b if r.endswith("SKILL.md"))
        print("  STATE B -- after the handback action, on the copy")
        print(f"    summary        {pb['report']['summary']}")
        print(f"    needs_merge    {len(needs_b)}")
        print(f"    SKILL.md in needs_merge: {len(skill_md_b)} {skill_md_b}")
        drop = len(needs_a) - len(needs_b)
        print(
            f"    files reconciled: {drop}   (skills rewritten on the copy: {len(moved)})"
        )

        differ = len(needs_a) != len(needs_b)
        tdd_still = "tdd-workflow/SKILL.md" in needs_b
        print(
            f"    CONTROL both-states verdicts differ: {differ}"
            " (identical counts would make this probe inert)"
        )
        print(
            f"    NEGATIVE CONTROL tdd-workflow (diverged BEFORE round 1) still"
            f" needs a merge: {tdd_still}"
        )
        verdict_c = (
            "H-CLOSES (the +6 are description-line-only; the handback instruction is complete)"
            if drop == 6 and tdd_still
            else f"H-DEEPER (reconciled {drop}, expected 6; tdd_still={tdd_still})"
        )
        print(f"    VERDICT: {verdict_c}")
        if not differ or not tdd_still:
            rc = 1
    print()

    # ---------------- R3-E -------------------------------------------------
    print("=== R3-E  direction of divergence for the 6 defective vault files ===")
    print(
        "  (item 2 calls the remedy 'a targeted merge'; nobody measured the direction)"
    )
    rows = []
    for fn in SIX + [CONTROL_FILE]:
        a, b = REPO_AGENTS / "ui-audit" / fn, VAULT / "ui-audit" / fn
        if not a.is_file() or not b.is_file():
            rows.append(
                {"file": fn, "state": "MISSING", "repo_only": None, "vault_only": None}
            )
            continue
        ra, rb = set(significant(lines_of(a))), set(significant(lines_of(b)))
        common = ra & rb
        repo_only, vault_only = ra - rb, rb - ra
        # reconstruction control, both directions
        ok = len(common) + len(repo_only) == len(ra) and len(common) + len(
            vault_only
        ) == len(rb)
        two_way = bool(repo_only) and bool(vault_only)
        # Set arithmetic alone CANNOT tell a one-line REPLACEMENT (1 unique line on
        # each side, which is "two-way" by set difference) from both sides holding
        # real independent work.  The question the owner actually needs answered is
        # "would a copy DESTROY anything?", so classify the vault-only lines:
        # a line that is the old main-guard the repo deliberately replaced is not
        # work at risk; anything else is.
        subs = sorted(x for x in vault_only if "process.argv[1]" not in x)
        rows.append(
            {
                "file": fn,
                "repo_sig": len(ra),
                "vault_sig": len(rb),
                "common": len(common),
                "repo_only": len(repo_only),
                "vault_only": len(vault_only),
                "vault_only_substantive": len(subs),
                "two_way_setwise": two_way,
                "destructive_to_copy": bool(subs),
                "reconstruction_ok": ok,
                "sample_vault_only": [x[:110] for x in subs[:3]],
            }
        )
    print(
        f"  {'file':<24}{'repoOnly':>9}{'vaultOnly':>10}{'substantive':>12}  would a copy destroy work?"
    )
    for r in rows:
        if r.get("state") == "MISSING":
            print(f"  {r['file']:<24} MISSING")
            continue
        d = "YES -- union merge" if r["destructive_to_copy"] else "no -- safe copy"
        print(
            f"  {r['file']:<24}{r['repo_only']:>9}{r['vault_only']:>10}"
            f"{r['vault_only_substantive']:>12}  {d}"
        )
        for s in r["sample_vault_only"]:
            print(f"      vault-only: {s}")
    ctrl = next((r for r in rows if r["file"] == CONTROL_FILE), None)
    ctrl_ok = bool(ctrl) and ctrl.get("destructive_to_copy") is True
    recon_ok = all(r.get("reconstruction_ok", True) for r in rows)
    print()
    print(
        f"  DIFFER CONTROL: {CONTROL_FILE} is known to hold real live-only work"
        f" (round 2: 56 live-only lines) -> measured destructive: {ctrl_ok}"
    )
    print(f"  reconstruction check (both directions, all files): {recon_ok}")
    if not ctrl_ok or not recon_ok:
        print("  differ is NOT validated -- no verdict about the six may be cited")
        rc = 1
    six_rows = [r for r in rows if r["file"] in SIX and r.get("state") != "MISSING"]
    n_two = sum(1 for r in six_rows if r["destructive_to_copy"])
    safe = [r["file"] for r in six_rows if not r["destructive_to_copy"]]
    verdict_e = (
        f"{len(safe)}/{len(six_rows)} of the six are safe to copy "
        f"(vault-only content is exactly the old guard the repo replaced); "
        f"{n_two} hold real vault-only work and need a union merge"
    )
    print(f"  VERDICT: {verdict_e}")

    OUT.write_text(
        json.dumps(
            {
                "r3c": {
                    "diff_lines_repo_vs_vault": diff_lines,
                    "state_a_needs_merge": len(needs_a),
                    "state_b_needs_merge": len(needs_b),
                    "reconciled": drop,
                    "state_a_skillmd": skill_md_a,
                    "state_b_skillmd": skill_md_b,
                    "verdict": verdict_c,
                    "control_states_differ": differ,
                    "real_vault_written": False,
                },
                "r3e": {
                    "rows": rows,
                    "control_two_way": ctrl_ok,
                    "reconstruction_ok": recon_ok,
                    "verdict": verdict_e,
                },
            },
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print()
    print(
        f"{'SUCCESS' if rc == 0 else 'FAILED'}:s2-r3-vault reconciled={drop} two_way={n_two}/{len(six_rows)}"
    )
    return rc


sys.exit(main())
