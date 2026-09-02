"""ROUND 3 diagnostic: why do the hand-rolled and PyYAML parsers differ by 7,253 chars?

Only 3 descriptions differ non-trivially, so a 7,253-char gap is SELF-CONTRADICTING
and therefore a detector question, not a finding.  Hypotheses, stated first:

  H-YAMLFAIL : some SKILL.md frontmatters are NOT valid YAML, PyYAML returns None,
               and those descriptions are counted as 0.  -> the missing chars are
               concentrated in a small set of REJECTED files.
  H-TRUNC    : PyYAML parses everything but returns shorter strings (folding /
               whitespace normalisation).  -> the gap is spread thinly over MANY files.

They predict different distributions, so this can distinguish them.

If H-YAMLFAIL holds it matters far beyond bookkeeping: "the frontmatter does not
parse" is exactly the H-PARSE hypothesis rounds 1-2 refuted.  The decisive follow-up
is the INTERSECTION of the YAML-rejected set with the observed BARE set:
  - disjoint  -> the loader is lenient; H-PARSE stays refuted, on new evidence.
  - overlapping -> the earlier refutation is in trouble and must be revisited.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import yaml

DAILY = Path("C:/Users/Prekzursil/.claude/skills.daily")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-R3-YAMLDIAG.json"
)

BARE = {
    "ui-drive",
    "ui-invariant-walk",
    "use-image-clipboard",
    "using-git-worktrees",
    "vercel-deploy",
    "verification-before-completion",
    "verification-loop",
    "video-convert",
    "video-join-concat",
    "video-resize-aspect",
    "video-stabilize",
    "voice-analyze",
    "voice-apply",
    "voice-blend",
    "voice-create",
    "volatility-3",
    "webapp-testing",
    "windbg-command-cookbook",
    "windbg-preview",
    "windows-virtualization-conflict-triage",
    "winui-app",
    "workflow-foundry",
    "workflow-monitor",
    "writing-plans",
    "writing-skills",
    "wsl-vmware-cutover",
    "x-api",
    "x64dbg",
    "yeet",
    "zero-issue-coding",
}


def raw(p: Path) -> str:
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def front(text: str) -> list[str] | None:
    lines = [x[:-1] if x.endswith("\r") else x for x in text.split("\n")]
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def handrolled(body: list[str]) -> tuple[str, bool]:
    i = 0
    while i < len(body):
        ln = body[i]
        if ln.startswith("description:"):
            rest = ln.partition(":")[2].strip()
            if rest in (">", ">-", "|", "|-", ">+", "|+"):
                i += 1
                chunk = []
                while i < len(body) and (
                    body[i].strip() == "" or body[i][:1] in (" ", "\t")
                ):
                    chunk.append(body[i].strip())
                    i += 1
                join = " " if rest.startswith(">") else "\n"
                return join.join(x for x in chunk if x or join == "\n"), True
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest, False
        i += 1
    return "", False


def main() -> int:
    names = sorted(d.name for d in DAILY.iterdir() if (d / "SKILL.md").is_file())
    rejected, short, ok = [], [], 0
    gap_rejected = gap_short = 0
    for d in names:
        body = front(raw(DAILY / d / "SKILL.md"))
        if body is None:
            rejected.append((d, len(handrolled([])[0]), "no frontmatter"))
            continue
        h, _ = handrolled(body)
        try:
            doc = yaml.safe_load("\n".join(body))
            err = None
        except yaml.YAMLError as e:
            doc, err = None, type(e).__name__
        if (
            err
            or not isinstance(doc, dict)
            or not isinstance(doc.get("description"), str)
        ):
            rejected.append((d, len(h), err or "no str description"))
            gap_rejected += len(h)
            continue
        y = doc["description"]
        if len(y) != len(h):
            short.append((d, len(h), len(y)))
            gap_short += len(h) - len(y)
        else:
            ok += 1

    print("=== WHERE THE 7,253 CHARS WENT ===")
    print(f"  skills                          : {len(names)}")
    print(
        f"  PyYAML REJECTED the frontmatter : {len(rejected)}  ({gap_rejected} chars)"
    )
    print(f"  PyYAML parsed but LENGTH differs: {len(short)}  ({gap_short} chars)")
    print(f"  byte-for-byte identical         : {ok}")
    print(f"  accounted for                   : {gap_rejected + gap_short}")
    print()
    print("=== THE REJECTED FILES (PyYAML error class) ===")
    for d, n, why in rejected:
        print(f"  {d:<38} desc={n:<6} {why}   {'** BARE **' if d in BARE else ''}")
    print()
    print("=== LENGTH-ONLY DIFFERENCES (folding / whitespace) ===")
    for d, a, b in short[:15]:
        print(f"  {d:<38} handrolled={a:<6} pyyaml={b:<6} delta={b - a}")
    if len(short) > 15:
        print(f"  ... and {len(short) - 15} more")
    print()

    rej = {d for d, _, _ in rejected}
    inter = sorted(rej & BARE)
    print("=== THE DECISIVE QUESTION: do YAML-rejected files go BARE? ===")
    print(f"  YAML-rejected  : {len(rej)}")
    print(f"  observed BARE  : {len(BARE)}")
    print(f"  INTERSECTION   : {len(inter)} {inter}")
    print(f"  rejected-and-RENDERED: {len(rej - BARE)} {sorted(rej - BARE)[:8]}")
    if not inter:
        verdict = "DISJOINT -> loader is lenient; H-PARSE stays REFUTED (new evidence)"
    elif len(inter) == len(rej):
        verdict = "TOTAL OVERLAP -> H-PARSE must be revisited"
    else:
        verdict = "PARTIAL -> inconclusive, investigate"
    print(f"  VERDICT: {verdict}")

    dom = "H-YAMLFAIL" if gap_rejected > gap_short else "H-TRUNC"
    print()
    print(
        f"  gap attribution: {dom}  (rejected {gap_rejected} vs length-only {gap_short})"
    )

    OUT.write_text(
        json.dumps(
            {
                "n_skills": len(names),
                "rejected": [
                    {"skill": d, "chars": n, "why": w} for d, n, w in rejected
                ],
                "length_only": [
                    {"skill": d, "handrolled": a, "pyyaml": b} for d, a, b in short
                ],
                "gap_rejected": gap_rejected,
                "gap_length_only": gap_short,
                "intersection_with_bare": inter,
                "rejected_and_rendered": sorted(rej - BARE),
                "verdict": verdict,
                "dominant": dom,
            },
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print()
    print(f"SUCCESS:s2-r3-yamldiag rejected={len(rej)} intersect_bare={len(inter)}")
    return 0


sys.exit(main())
