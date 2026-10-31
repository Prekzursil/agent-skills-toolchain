"""ROUND 2 final verification -- one script, every postcondition, no prose.

Checks, each with the number that would falsify it:
  V1 fleet description chars                   115456 + 5 = 115461
  V2 the 3 round-2 skills byte-identical in all three trees
  V3 lexical-recall gate over ALL SEVEN skills this lane touched, vs the
     pre-round-1 baseline: every content-word loss must be DECLARED
  V4 cumulative char delta of the lane vs the pre-round-1 baseline must be <= 0
  V5 main-guard state across all four trees
  V6 no CRLF introduced into any file this lane wrote
"""

import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _s2_r2_apply import (  # noqa: E402
    ROWS,
    TREES,
    content_words,
    find_desc,
    norm,
    pre_desc,
    read,
    survives,
)

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
EXPECT_FLEET = 115461
ALL_SEVEN = [
    "transcribe",
    "tdd-workflow",
    "security-review",
    "screenshot",
    "e2e-testing",
    "python-testing",
    "research-ops",
]
# Losses declared across rounds 1 and 2 (round-1 rows had no gate; their losses are
# enumerated here so V3 is a real gate over the whole lane, not just round 2).
DECLARED = {
    "transcribe": ["files", "known-speaker", "hints", "extract", "label", "optional"],
    "screenshot": ["explicitly", "capabilities", "specific"],
    "research-ops": [
        "operator",
        "entry",
        "routes",
        "duplicating",
        "research",
        "rather",
    ],
    # Round-1 rows had no recall gate; their losses are enumerated here so V3 is a
    # gate over the WHOLE lane. Each is a meta/filler word whose subject survives:
    #   tdd-workflow    "this skill"->-, "refactoring code"->refactoring, "including"->-
    #   security-review "working with secrets"->secrets, "creating API endpoints"->API
    #                   endpoints, "Provides comprehensive"->gives
    #   e2e-testing     "CI/CD integration"->CI/CD, "artifact management"->artifacts,
    #                   "flaky test strategies"->flaky tests. NOTE the standalone term
    #                   "integration" is gone from THIS description; it is still carried
    #                   fleet-wide by tdd-workflow ("unit, integration, E2E").
    #   python-testing  "TDD methodology"->TDD, "coverage requirements"->coverage
    #                   ("python"/"testing" are recovered from the skill NAME, which V3
    #                    now checks mechanically rather than by assertion)
    "tdd-workflow": ["skill", "code", "including"],
    "security-review": [
        "skill",
        "working",
        "creating",
        "implementing",
        "provide",
        "comprehensive",
    ],
    "e2e-testing": ["integration", "management", "strategies"],
    "python-testing": ["methodology", "requirements"],
}
GUARD_TREES = {
    "repo/skills": REPO / "skills/ui-audit/dead_button_crawl.mjs",
    "repo/.agents": REPO / ".agents/skills/ui-audit/dead_button_crawl.mjs",
    "live/daily": Path(
        "C:/Users/Prekzursil/.claude/skills.daily/ui-audit/dead_button_crawl.mjs"
    ),
    "live/vault": Path(
        "C:/Users/Prekzursil/.agents/skills/ui-audit/dead_button_crawl.mjs"
    ),
}
WROTE = [
    "skills/ui-audit/dead_button_crawl.mjs",
    ".agents/skills/ui-audit/dead_button_crawl.mjs",
    "skills/ui-audit/_fix_main_guard.py",
    ".agents/skills/ui-audit/_fix_main_guard.py",
]


def desc_of(p):
    """Single-line description reader (round-2 skills are all plain scalars)."""
    d = find_desc(read(p))
    return d[1] if d else None


def desc_folded_aware(p):
    """Fleet totals MUST use this one.

    `find_desc` is a single-line regex and returns '' for the 12 folded/literal
    block scalars, silently dropping ~8,845 chars. Round 1 hit this exact trap:
    an inline re-measure returned 106,613 instead of 115,456 and the discrepancy
    was a parser blind spot, not a change on disk. V1 reproduced it again here
    (106,618 = 106,613 + this round's +5), which is why the fleet total is read
    with the folded-aware parser and the simple one is kept for the plain rows.
    """
    lines = [x.rstrip("\r") for x in read(p).split("\n")]
    if not lines or lines[0].strip() != "---":
        return ""
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return ""
    body, i = lines[1:end], 0
    while i < len(body):
        if body[i].startswith("description:"):
            rest = body[i].partition(":")[2].strip()
            if rest in (">", ">-", "|", "|-", ">+", "|+"):
                i += 1
                chunk = []
                while i < len(body) and (
                    body[i].strip() == "" or body[i][:1] in (" ", "\t")
                ):
                    chunk.append(body[i].strip())
                    i += 1
                return " ".join(x for x in chunk if x)
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest
        i += 1
    return ""


def main():
    ok = True
    daily = TREES["daily"]
    names = [d.name for d in sorted(daily.iterdir()) if (d / "SKILL.md").is_file()]

    print("=== V1 fleet description chars ===")
    fleet = sum(len(desc_folded_aware(daily / n / "SKILL.md")) for n in names)
    blind = sum(len(desc_of(daily / n / "SKILL.md") or "") for n in names)
    print(
        "  %d skills, %d chars (expect %d) -> %s"
        % (
            len(names),
            fleet,
            EXPECT_FLEET,
            "OK" if fleet == EXPECT_FLEET else "MISMATCH",
        )
    )
    print(
        "  folded-blind parser would report %d (%+d) -- the round-1 trap, reproduced"
        % (blind, blind - fleet)
    )
    ok &= fleet == EXPECT_FLEET

    print()
    print("=== V2 three-tree byte identity, round-2 skills ===")
    for n in [k for k in ROWS if "host" not in ROWS[k]]:
        seen = {t: desc_of(root / n / "SKILL.md") for t, root in TREES.items()}
        same = len(set(seen.values())) == 1
        print("  %-16s identical3=%-5s len=%d" % (n, same, len(seen["daily"] or "")))
        ok &= same

    print()
    print("=== V3 lexical-recall gate, ALL SEVEN skills vs pre-round-1 baseline ===")
    print("  a word SURVIVES if it is still in the description OR in the skill NAME;")
    print("  every remaining loss must appear in that skill's DECLARED list")
    total_lost = 0
    for n in ALL_SEVEN:
        base = pre_desc(n)
        now = desc_of(daily / n / "SKILL.md")
        # The skill name is part of the lexical surface -- it is the listing's
        # primary key -- so "python"/"testing" for python-testing are recoverable.
        surface = set(content_words(now)) | {norm(x) for x in n.split("-")}
        lost = [w for w in content_words(base) if not survives(w, surface)]
        undeclared = [
            w for w in lost if not survives(w, {norm(x) for x in DECLARED[n]})
        ]
        gained = [
            w for w in content_words(now) if not survives(w, set(content_words(base)))
        ]
        total_lost += len(lost)
        flag = "OK" if not undeclared else "UNDECLARED LOSS"
        print(
            "  %-16s lost=%-2d declared-ok=%-5s gained=%-2d %s"
            % (n, len(lost), not undeclared, len(gained), flag)
        )
        if undeclared:
            print("      undeclared: %s" % undeclared)
        ok &= not undeclared

    print()
    print("=== V4 cumulative char delta vs the pre-round-1 baseline ===")
    delta = 0
    for n in ALL_SEVEN:
        b, c = len(pre_desc(n)), len(desc_of(daily / n / "SKILL.md"))
        delta += c - b
        print("  %-16s baseline=%-4d now=%-4d %+d" % (n, b, c, c - b))
    print("  LANE TOTAL: %+d chars (must be <= 0)" % delta)
    ok &= delta <= 0

    print()
    print("=== V5 main-guard state, all four trees ===")
    for t, p in GUARD_TREES.items():
        txt = io.open(p, "r", encoding="utf-8", newline="").read()
        old = "resolve(process.argv[1]) === resolve(__filename)" in txt
        new = "__isMain(process.argv[1], __filename)" in txt
        imp = "import { realpathSync }" in txt
        good = (not old) and new and imp
        print(
            "  %-14s old-guard=%-5s __isMain=%-5s imports=%-5s %s"
            % (t, old, new, imp, "OK" if good else "STILL BROKEN")
        )
        ok &= good

    print()
    print("=== V6 no CRLF introduced by this lane ===")
    for rel in WROTE:
        b = (REPO / rel).read_bytes()
        n = b.count(b"\r\n")
        print("  %-52s crlf=%d %s" % (rel, n, "OK" if n == 0 else "CRLF INTRODUCED"))
        ok &= n == 0

    print()
    print("=== V7 dual-write gate ===")
    r = subprocess.run(
        [sys.executable, "ci/check_skill_dual_write.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    print(
        "  exit=%d  %s"
        % (r.returncode, (r.stdout or r.stderr).strip().splitlines()[-1:])
    )
    ok &= r.returncode == 0

    (REPO / "command-center/grounding/S2-R2-FINALVERIFY.json").write_text(
        json.dumps(
            {
                "fleet": fleet,
                "lane_delta": delta,
                "total_lost_words": total_lost,
                "all_ok": bool(ok),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print()
    print("%s:s2-r2-finalverify" % ("SUCCESS" if ok else "FAILED"))
    return 0 if ok else 1


sys.exit(main())
