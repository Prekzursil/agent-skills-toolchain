"""Verify the round-4 fix in the STORED BLOBS, not the working tree.

Rule: a working-tree green is not a committed green. Every assertion below reads
`git show <rev>:<path>` (the raw blob, 0 CRLF on this box -- `git archive` is the one that
applies EOL conversion and hands back CRLF).

Each check carries a control that must FAIL on a known-absent probe, so a green cannot come
from a reader that is looking at nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
# Rev is argv-driven so this checker can be run against the PRE-FIX commit as its own
# both-states control: it MUST go red at `<fix>^` and green at HEAD. A verifier that is
# green in both states measures nothing.
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def blob(path: str) -> str:
    p = subprocess.run(
        ["git", "-C", REPO, "show", f"{REV}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout if p.returncode == 0 else ""


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    # CONTROL for the reader itself: a real path yields content, a fabricated one yields "".
    real = blob("CLAUDE.md")
    fake = blob("docs/ssot/NO-SUCH-FILE-92f1a.md")
    reader_ok = len(real) > 500 and fake == ""
    print(
        f"CONTROL blob reader: real={len(real)}B fabricated={len(fake)}B -> {reader_ok}"
    )
    if not reader_ok:
        print("FAILED:r4-verify blob reader did not discriminate")
        return 3

    pop = json.loads(blob("command-center/ssot/population-classified.json"))
    rows = pop["rows"]
    live = [r for r in rows if r.get("exists")]
    kinds: dict[str, int] = {}
    for r in live:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"committed kind histogram: {kinds}")

    sev = [r for r in live if r["kind"] == "severed-worktree"]
    checks.append(("exactly one severed row", len(sev) == 1, str(len(sev))))
    if sev:
        row = sev[0]
        checks.append(
            (
                "severed row carries resolved_by",
                row.get("resolved_by")
                == "third-signal:dotgit-file-pointer-target-missing",
                str(row.get("resolved_by")),
            )
        )
        checks.append(
            (
                "severed row keeps signals_agree=false (record not deleted)",
                row.get("signals_agree") is False,
                str(row.get("signals_agree")),
            )
        )
        checks.append(
            (
                "severed row records the missing target",
                row.get("gitdir_target_exists") is False,
                str(row.get("gitdir_target_exists")),
            )
        )
    ka = pop.get("kind_arithmetic", {})
    checks.append(("kind_arithmetic closes", ka.get("closes") is True, json.dumps(ka)))
    checks.append(
        (
            "arithmetic sums to on_disk",
            ka.get("sum") == ka.get("on_disk") == len(live),
            f"sum={ka.get('sum')} on_disk={ka.get('on_disk')} live={len(live)}",
        )
    )
    checks.append(
        (
            "primary disagreement still recorded",
            len(pop.get("kind_signals_disagree", [])) == 1,
            str(pop.get("kind_signals_disagree")),
        )
    )
    checks.append(
        (
            "nothing left unresolved",
            pop.get("kind_signals_disagree_unresolved") == [],
            str(pop.get("kind_signals_disagree_unresolved")),
        )
    )

    claude = real
    checks.append(
        ("CLAUDE.md arithmetic closes at 178", "9 + 168 + 1 = 178" in claude, "")
    )
    checks.append(
        (
            "CLAUDE.md keeps the refuted wording",
            "REFUTED 2026-08-14 (round 4)" in claude,
            "",
        )
    )

    r3 = blob("command-center/ssot/BUILD-ROUND3-2026-08-14.md")
    checks.append(("round-3 DoD-1 marked REFUTED", "REFUTED as written" in r3, ""))
    checks.append(("round-3 original wording kept", "**PASS** — 178/178" in r3, ""))

    inv = blob("docs/ssot/SSOT-CLONE-INVENTORY.md")
    checks.append(("inventory carries the severed row", "severed worktrees" in inv, ""))
    checks.append(("inventory arithmetic row", "9 + 168 + 1 = **178**" in inv, ""))

    print()
    bad = 0
    for name, ok, detail in checks:
        mark = " ok " if ok else "FAIL"
        print(f"  [{mark}] {name}{('  <- ' + detail) if not ok and detail else ''}")
        bad += 0 if ok else 1
    if bad:
        print(f"FAILED:r4-verify-committed {bad} of {len(checks)} checks failed")
        return 1
    print(f"SUCCESS:r4-verify-committed checks={len(checks)} all pass (blob form)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
