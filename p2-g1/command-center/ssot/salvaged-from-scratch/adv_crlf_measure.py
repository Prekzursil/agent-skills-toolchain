"""Independent measurement of the disputed CRLF claims.

Detectors already proven both-states by adv_crlf_control.py:
  D1 = git cat-file -p (binary subprocess, no text translation)
  D2 = git ls-files --eol i/ column

H1 (BUILD's claim)   : the numbers 278 / 840 / 248 / 355 / 328 / 112 are CRLF counts.
H2 (AUDIT's claim)   : they are LINE counts and the blobs are 0 CRLF.
"""

import subprocess
import sys

REPO = r"C:/Users/Prekzursil/source/ast-integrate"


def blob(rev, path):
    p = subprocess.run(["git", "cat-file", "-p", f"{rev}:{path}"],
                       cwd=REPO, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def stats(rev, path):
    b = blob(rev, path)
    if b is None:
        return None
    return {"bytes": len(b), "crlf": b.count(b"\r\n"),
            "lf": b.count(b"\n"), "cr": b.count(b"\r")}


ROUND2_TABLE = [
    ("docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md", 248),
    ("command-center/mcp-audit/ruff-census.json", 28),
    ("docs/mcp-audit/MCP-FLEET-AUDIT.md", 355),
    ("README.md", 328),
    ("AGENTS.md", 112),
]

ROUND3_CLAIMS = [
    ("docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md", 278),
    ("command-center/mcp-audit/disposition.json", 840),
]

# 630bb8af = auditor's chosen rev. 2caafe53 = the commit that AUTHORED the round-2 table
# (the correct rev for a self-referential row). 959f783f = its parent.
REVS_R2 = ["630bb8af", "959f783f", "2caafe53", "bfec0543", "673cd180"]
REVS_R3 = ["bfec0543", "0d3c9e93", "673cd180"]


def score(table, revs, label):
    print(f"\n===== {label} =====")
    h1_hits = {r: 0 for r in revs}
    h2_hits = {r: 0 for r in revs}
    for path, claimed in table:
        print(f"\n  {path}   claimed number = {claimed}")
        for rev in revs:
            s = stats(rev, path)
            if s is None:
                print(f"    {rev}  <file absent at this rev>")
                continue
            h1 = s["crlf"] == claimed
            h2 = (s["crlf"] == 0 and s["lf"] == claimed)
            h1_hits[rev] += h1
            h2_hits[rev] += h2
            print(f"    {rev}  bytes={s['bytes']:>7}  CRLF={s['crlf']:>4}  "
                  f"LF(lines)={s['lf']:>4}  bareCR={s['cr'] - s['crlf']:>3}   "
                  f"H1(crlf==n)={'HIT' if h1 else '.':<3} "
                  f"H2(0crlf & lines==n)={'HIT' if h2 else '.'}")
    n = len(table)
    print(f"\n  -- score over {n} rows --")
    for rev in revs:
        print(f"    {rev}   H1 {h1_hits[rev]}/{n}    H2 {h2_hits[rev]}/{n}")
    return h1_hits, h2_hits


def main():
    score(ROUND2_TABLE, REVS_R2, "ROUND-2 five-row CRLF table")
    score(ROUND3_CLAIMS, REVS_R3, "ROUND-3 two claims (the shipped sentence)")

    # Did ANY historical version of these files ever have CRLF in the blob?
    print("\n===== every historical version, any CRLF at all? =====")
    for path in ["README.md", "AGENTS.md", "docs/mcp-audit/MCP-FLEET-AUDIT.md",
                 "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md",
                 "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md",
                 "command-center/mcp-audit/disposition.json",
                 "command-center/mcp-audit/ruff-census.json"]:
        p = subprocess.run(["git", "log", "--all", "--format=%H", "--", path],
                           cwd=REPO, capture_output=True, text=True)
        revs = [r for r in p.stdout.split() if r]
        worst = 0
        checked = 0
        for r in revs:
            s = stats(r, path)
            if s:
                checked += 1
                worst = max(worst, s["crlf"])
        print(f"  {path:52s} versions={checked:>3}  max CRLF over ALL history = {worst}")

    print("\nSUCCESS:crlf-measure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
