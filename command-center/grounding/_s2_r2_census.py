"""ROUND 2 / R5: the WHEN census under-reported a regression its own edit caused.

The round-1 census used
    WHEN = r"\\b(use when|when the user|triggers?|use this)\\b"
which matches "Do NOT use when you need ..." -- a NEGATIVE clause -- as if it
were a positive statement of when to use the skill.  `transcribe` lost its only
positive opener in round 1 and the census still counted it as stating WHEN.
The reported delta was 257 -> 256 (one skill); this probe measures the true one.

Two detectors, run side by side:
  OLD  the round-1 regex, verbatim.
  NEW  strip negative clauses FIRST, then require a positive WHEN marker.

DETECTOR CONTROL (rule 3c -- state the hypotheses before the control runs):
  H1 "OLD is inert on this case"  -> OLD says True for the CURRENT transcribe text
                                     and True for the PRE text: it cannot tell them apart.
  H2 "OLD is fine, NEW is noise"  -> both detectors agree on every case.
  These predict different tables, so the control can distinguish them.
  NEW must also be shown non-vacuous: it must return True on texts that really do
  state a positive WHEN, not merely False on everything.
"""

import io
import json
import os
import re
import subprocess
import sys

DAILY = "C:/Users/Prekzursil/.claude/skills.daily"
REPO = "C:/Users/Prekzursil/source/ast-integrate"
PRE_REV = "1e9cfe81~1"
# ROUND-3 FIX. This was `git_desc("HEAD", n)` below, described in round 2 as
# "the frozen R1 git blob".  HEAD IS NOT FROZEN.  It resolved to 1e9cfe81 only
# because round 2 had not committed yet; four commits later it resolves to the
# ROUND-2 (already-fixed) text, so the control compared the fixed state against
# itself and reported `NOT DISCRIMINATING -- do not cite the numbers below`.
# Measured at round-3 HEAD before this line existed.  The round-2 sentence
# "anchored to the frozen R1 git blob, not to disk" is therefore REFUTED: it was
# anchored to a MOVING reference and merely looked frozen at the moment it ran.
# Pinned to the immutable round-1 SHA.
R1_REV = "1e9cfe81"
EDITED = [
    "transcribe",
    "tdd-workflow",
    "security-review",
    "screenshot",
    "e2e-testing",
    "python-testing",
    "research-ops",
]

OLD_WHEN = re.compile(r"\b(use when|when the user|triggers?|use this)\b", re.I)
# A negative clause runs from its marker to the end of the sentence.
NEG_CLAUSE = re.compile(
    r"(do not use|don't use|do NOT use|never use|not for|NOT for|NOT the|NOT a )"
    r"[^.;]*[.;]?",
    re.I,
)
POS_WHEN = re.compile(
    r"\b(use when|use this when|when the user|when a user|"
    r"triggers?|use this|use for|use to|use at)\b",
    re.I,
)


def new_when(desc):
    """Positive WHEN: strip negative clauses, then look for a WHEN marker."""
    return bool(POS_WHEN.search(NEG_CLAUSE.sub(" ", desc)))


def read_raw(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def desc_from_text(text):
    lines = [x[:-1] if x.endswith("\r") else x for x in text.split("\n")]
    if not lines or lines[0].strip() != "---":
        return ""
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return ""
    body, i = lines[1:end], 0
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
                return " ".join(x for x in chunk if x)
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest
        i += 1
    return ""


def git_desc(rev, name):
    out = subprocess.run(
        ["git", "show", "%s:.agents/skills/%s/SKILL.md" % (rev, name)],
        cwd=REPO,
        capture_output=True,
    )
    if out.returncode != 0:
        return None
    return desc_from_text(out.stdout.decode("utf-8", "replace"))


def main():
    names = [
        d
        for d in sorted(os.listdir(DAILY))
        if os.path.isfile(os.path.join(DAILY, d, "SKILL.md"))
    ]
    post = {
        d: desc_from_text(read_raw(os.path.join(DAILY, d, "SKILL.md"))) for d in names
    }

    pre, r1 = dict(post), dict(post)
    missing = []
    for n in EDITED:
        d = git_desc(PRE_REV, n)
        if d is None:
            missing.append(n)
        else:
            pre[n] = d
        # R1 = the round-1 state, frozen at an IMMUTABLE SHA (see R1_REV above).
        # The both-states control below must keep working after round 2 repairs the
        # disk AND after any number of later commits, so it may never name HEAD.
        d1 = git_desc(R1_REV, n)
        if d1 is not None:
            r1[n] = d1

    print("=== DETECTOR CONTROL: both states, both detectors ===")
    print("  %-18s %-6s %-9s %-9s" % ("case", "state", "OLD", "NEW"))
    cases = [
        ("transcribe", "PRE", pre["transcribe"]),
        ("transcribe", "R1", r1["transcribe"]),
        ("transcribe", "R2", post["transcribe"]),
        ("research-ops", "PRE", pre["research-ops"]),
        ("research-ops", "R1", r1["research-ops"]),
        ("research-ops", "R2", post["research-ops"]),
        ("tdd-workflow", "R2", post["tdd-workflow"]),
    ]
    table = {}
    for nm, st, txt in cases:
        o, n = bool(OLD_WHEN.search(txt)), new_when(txt)
        table[(nm, st)] = (o, n)
        print("  %-18s %-6s %-9s %-9s" % (nm, st, o, n))
    # The control compares PRE with R1 (the frozen round-1 blob = the KNOWN-BROKEN
    # state). OLD must be blind to that regression (True/True) while NEW must see
    # it (True/False). Anchoring to R1 rather than to disk keeps the control alive
    # after round 2 repairs the file.
    inert = (
        table[("transcribe", "PRE")][0]
        and table[("transcribe", "R1")][0]
        and table[("transcribe", "PRE")][1]
        and not table[("transcribe", "R1")][1]
    )
    nonvacuous = table[("tdd-workflow", "R2")][1] and table[("transcribe", "PRE")][1]
    print(
        "  H1 OLD-is-inert-here (True/True) while NEW discriminates (True/False):",
        inert,
    )
    print("  NEW is non-vacuous (returns True on real positive-WHEN text):", nonvacuous)
    print(
        "  CONTROL:",
        "DISCRIMINATING"
        if inert and nonvacuous
        else "NOT DISCRIMINATING -- do not cite the numbers below",
    )
    if not (inert and nonvacuous):
        return 1
    print()

    print("=== CENSUS: fleet-wide, three states ===")
    print(
        "  PRE = pre-round-1 (%s) | R1 = round-1 as committed (HEAD) | R2 = now"
        % PRE_REV
    )
    states = {"PRE": pre, "R1": r1, "R2": post}
    print(
        "  fleet skills: %d   (PRE reconstructed for the %d edited, %d missing)"
        % (len(names), len(EDITED) - len(missing), len(missing))
    )
    counts = {}
    for lab, st in states.items():
        counts[lab] = (
            sum(1 for d in names if OLD_WHEN.search(st[d])),
            sum(1 for d in names if new_when(st[d])),
        )
    print("  %-5s %-12s %-12s" % ("state", "OLD detector", "NEW detector"))
    for lab in ("PRE", "R1", "R2"):
        print("  %-5s %-12d %-12d" % (lab, counts[lab][0], counts[lab][1]))
    print(
        "  round-1 delta   OLD %+d   NEW %+d"
        % (counts["R1"][0] - counts["PRE"][0], counts["R1"][1] - counts["PRE"][1])
    )
    print(
        "  round-2 delta   OLD %+d   NEW %+d"
        % (counts["R2"][0] - counts["R1"][0], counts["R2"][1] - counts["R1"][1])
    )
    print(
        "  net vs PRE      OLD %+d   NEW %+d"
        % (counts["R2"][0] - counts["PRE"][0], counts["R2"][1] - counts["PRE"][1])
    )
    print()

    def lost(det, a, b):
        return [d for d in names if det(a[d]) and not det(b[d])]

    o = lambda t: bool(OLD_WHEN.search(t))  # noqa: E731
    lost_old_r1 = lost(o, pre, r1)
    lost_new_r1 = lost(new_when, pre, r1)
    lost_old_r2 = lost(o, pre, post)
    lost_new_r2 = lost(new_when, pre, post)
    print("  ROUND 1 (the regression):")
    print("    lost a WHEN per OLD detector :", lost_old_r1)
    print("    lost a WHEN per NEW detector :", lost_new_r1)
    print(
        "    MASKED by OLD (real regression it could not see):",
        sorted(set(lost_new_r1) - set(lost_old_r1)),
    )
    print(
        "    MIS-ATTRIBUTED by OLD (flagged, but the NEW detector says fine):",
        sorted(set(lost_old_r1) - set(lost_new_r1)),
    )
    print("  ROUND 2 (after the repair):")
    print("    lost a WHEN per OLD detector :", lost_old_r2)
    print("    lost a WHEN per NEW detector :", lost_new_r2)
    print()
    print("=== the 7 edited skills, NEW detector, per state ===")
    print("  %-18s %-6s %-6s %-6s" % ("skill", "PRE", "R1", "R2"))
    for n in EDITED:
        print(
            "  %-18s %-6s %-6s %-6s"
            % (n, new_when(pre[n]), new_when(r1[n]), new_when(post[n]))
        )

    out = {
        "fleet": len(names),
        "counts": {k: {"old": v[0], "new": v[1]} for k, v in counts.items()},
        "round1": {
            "lost_old": lost_old_r1,
            "lost_new": lost_new_r1,
            "masked": sorted(set(lost_new_r1) - set(lost_old_r1)),
            "misattributed": sorted(set(lost_old_r1) - set(lost_new_r1)),
        },
        "round2": {"lost_old": lost_old_r2, "lost_new": lost_new_r2},
        "control_discriminating": bool(inert and nonvacuous),
    }
    with io.open(
        REPO + "/command-center/grounding/S2-R2-CENSUS.json",
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        f.write(json.dumps(out, indent=1))
    print()
    print(
        "SUCCESS:s2-r2-census r1_masked=%d r2_open=%d"
        % (len(set(lost_new_r1) - set(lost_old_r1)), len(lost_new_r2))
    )
    return 0


sys.exit(main())
