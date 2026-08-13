"""ROUND 2 / R6: is dead_button_crawl.mjs really a one-line copy-back?

Round 1 residual #1 said the repo's `dead_button_crawl.mjs` still carries the old
lexical main-guard and called it "a one-line change".  The independent audit went
further: "the repair is a copy-back, not new authorship", because the LIVE trees
already carry `__isMain`.  Both sentences assume the two sides differ only in the
guard.  This probe tests that assumption before anything is copied, per the
destructive-action default (read BOTH sides, state where each capability lands).

  H-ONELINE : repo and live differ only in the guard -> the unique-line counts on
              each side are tiny and one-directional.
  H-DIVERGED: live has substantive extra work -> large, two-directional delta, and
              a copy-back would import unreviewed behaviour, not repair a line.

Detector control: the differ must reconstruct BOTH files exactly
(common + side-only == that side's line count).  A differ reporting "0 repo-only"
is indistinguishable from a broken differ unless reconstruction is checked.
"""
import io
import json
import re
import sys
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"
PAIRS = {
    "repo/skills": REPO + "/skills/ui-audit/dead_button_crawl.mjs",
    "repo/.agents": REPO + "/.agents/skills/ui-audit/dead_button_crawl.mjs",
    "live/daily": "C:/Users/Prekzursil/.claude/skills.daily/ui-audit/dead_button_crawl.mjs",
    "live/vault": "C:/Users/Prekzursil/.agents/skills/ui-audit/dead_button_crawl.mjs",
}
OLD_GUARD = re.compile(r"process\.argv\[1\][^\n]*resolve\(__filename\)")
NEW_GUARD = re.compile(r"__isMain")


def lines_of(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return [x.rstrip("\r") for x in f.read().split("\n")]


def main():
    data = {k: lines_of(v) for k, v in PAIRS.items()}
    print("=== guard state per tree ===")
    for k, ls in data.items():
        body = "\n".join(ls)
        old = [i + 1 for i, x in enumerate(ls) if OLD_GUARD.search(x)]
        new = [i + 1 for i, x in enumerate(ls) if NEW_GUARD.search(x)]
        print("  %-14s lines=%-5d bytes~%-6d old-guard@%s  __isMain@%s"
              % (k, len(ls), len(body), old or "-", new or "-"))
    print()

    a, b = data["repo/skills"], data["live/daily"]
    ca, cb = Counter(a), Counter(b)
    common = ca & cb
    a_only = list((ca - cb).elements())
    b_only = list((cb - ca).elements())
    print("=== differ: repo/skills  vs  live/daily ===")
    print("  repo lines %d = common %d + repo-only %d -> %s"
          % (len(a), sum(common.values()), len(a_only),
             "OK" if sum(common.values()) + len(a_only) == len(a) else "RECONSTRUCTION FAIL"))
    print("  live lines %d = common %d + live-only %d -> %s"
          % (len(b), sum(common.values()), len(b_only),
             "OK" if sum(common.values()) + len(b_only) == len(b) else "RECONSTRUCTION FAIL"))
    two_way = bool(a_only) and bool(b_only)
    print("  two-directional?", two_way)
    print()

    def sig(xs):
        return [x for x in xs if x.strip() and not x.strip().startswith("//")]

    print("  repo-only NON-BLANK NON-COMMENT lines: %d" % len(sig(a_only)))
    for x in sig(a_only)[:25]:
        print("    - %s" % x.strip()[:110])
    print()
    print("  live-only NON-BLANK NON-COMMENT lines: %d  (showing 30)" % len(sig(b_only)))
    for x in sig(b_only)[:30]:
        print("    + %s" % x.strip()[:110])
    print()

    # what NEW capability does live carry?  count top-level declarations only on
    # each side, so "extra content" is described, not just counted.
    decl = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*const\s+(\w+)\s*=")
    def decls(ls):
        out = []
        for x in ls:
            m = decl.match(x)
            if m:
                out.append(m.group(1) or m.group(2))
        return out
    da, db = set(decls(a)), set(decls(b))
    print("  declarations only in LIVE :", sorted(db - da))
    print("  declarations only in REPO :", sorted(da - db))
    print()

    verdict = "H-DIVERGED" if (two_way and len(sig(b_only)) > 20) else "H-ONELINE"
    print("VERDICT:", verdict)
    if verdict == "H-DIVERGED":
        print("  -> a whole-file copy-back would import %d unreviewed live-only lines."
              % len(sig(b_only)))
        print("  -> the round-1 residual and the audit both called this a one-line")
        print("     change / plain copy-back. Both sentences are REFUTED by this diff.")

    out = {
        "trees": {k: {"lines": len(v),
                      "old_guard": [i + 1 for i, x in enumerate(v) if OLD_GUARD.search(x)],
                      "isMain": [i + 1 for i, x in enumerate(v) if NEW_GUARD.search(x)]}
                  for k, v in data.items()},
        "repo_only_sig": len(sig(a_only)), "live_only_sig": len(sig(b_only)),
        "two_directional": two_way,
        "decls_live_only": sorted(db - da), "decls_repo_only": sorted(da - db),
        "verdict": verdict,
    }
    with io.open(REPO + "/command-center/grounding/S2-R2-DEADBUTTON.json", "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out, indent=1))
    print()
    print("SUCCESS:s2-r2-deadbutton verdict=%s" % verdict)
    return 0


sys.exit(main())
