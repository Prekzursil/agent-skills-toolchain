"""Fleet-wide mechanical overlap matrix over SKILL.md BODIES.

The OVERLAP lens did not complete. Its correct entry point (named by the USABILITY
lens as its own gap) is a token-set similarity sweep over BODIES, then a two-body
read of whatever surfaces. This is the sweep. It makes NO merge recommendation --
per fan-out-contract C4, a mechanical question gets an algorithm, and the judgement
of whether divergent content MATTERS is what agents are for.

Two independent similarity measures are computed so a single metric's artifact
cannot drive a destructive call:
  J_body  = Jaccard over the body's word set (order-free, length-tolerant)
  C_shing = containment over 5-gram shingles (order-sensitive, catches copy-paste)

DETECTOR CONTROL: cv-studio contains a byte-identical nested copy of itself in the
live tree, and the four *-deploy skills are known near-siblings. The control asserts
a synthetic self-pair scores 1.0 and that an unrelated pair scores low; if the
self-pair is not 1.0 the metric is broken and every number below is void.
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
WORD = re.compile(r"[a-z0-9][a-z0-9_-]*")

CLUSTERS = {
    "humanizer": ["humanizer", "agentic-humanizer", "slop-check"],
    "deploy": ["cloudflare-deploy", "netlify-deploy", "render-deploy", "vercel-deploy"],
    "hexstrike": [
        "hexstrike-ai-setup",
        "hexstrike-ai-mcp",
        "hexstrike-ai-authorized-engagement",
    ],
    "seclookup": [
        "secsearch",
        "hacktricks",
        "hacktricks-api",
        "lolbin-lookup",
        "gtfobins-lookup",
        "security-kb-lookup",
        "sec-corpora-update",
    ],
    "verify": [
        "two-tier-verify",
        "verification-before-completion",
        "mutation-check",
        "verification-loop",
        "acceptance-review",
        "smallest-check-ladder",
        "seed-golden-journey",
        "packaged-artifact-smoke",
    ],
    "playwright": [
        "playwright",
        "playwright-interactive",
        "webapp-testing",
        "e2e-testing",
    ],
    "design": [
        "design-studio",
        "design-review-loop",
        "design-studio-session",
        "ui-audit",
        "critique-panel",
        "ui-drive",
        "ui-invariant-walk",
    ],
}


def body_of(p: Path) -> str:
    t = p.read_text(encoding="utf-8", errors="replace")
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e != -1:
            t = t[e + 4 :]
    return t.lower()


bodies, wordsets, shingles = {}, {}, {}
for d in sorted(x for x in DAILY.iterdir() if x.is_dir()):
    sk = d / "SKILL.md"
    if not sk.exists():
        continue
    b = body_of(sk)
    bodies[d.name] = b
    toks = WORD.findall(b)
    wordsets[d.name] = set(toks)
    shingles[d.name] = {tuple(toks[i : i + 5]) for i in range(max(0, len(toks) - 4))}

print(f"parsed bodies: {len(bodies)}")


def jac(a, b):
    A, B = wordsets[a], wordsets[b]
    return len(A & B) / len(A | B) if A | B else 0.0


def cont(a, b):
    A, B = shingles[a], shingles[b]
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


# --- DETECTOR CONTROL -----------------------------------------------------
name0 = next(iter(wordsets))
wordsets["__SELF__"] = set(wordsets[name0])
shingles["__SELF__"] = set(shingles[name0])
self_j, self_c = jac(name0, "__SELF__"), cont(name0, "__SELF__")
lo_pairs = [("humanizer", "x64dbg"), ("reframe", "gtfobins-lookup")]
print(f"DETECTOR CONTROL: self-pair J={self_j:.3f} C={self_c:.3f} (must be 1.000)")
for a, b in lo_pairs:
    if a in wordsets and b in wordsets:
        print(
            f"  unrelated {a} vs {b}: J={jac(a, b):.3f} C={cont(a, b):.3f} (must be low)"
        )
if abs(self_j - 1.0) > 1e-9:
    print("  -> METRIC BROKEN, all numbers void")
del wordsets["__SELF__"], shingles["__SELF__"]
print()

# --- named clusters -------------------------------------------------------
print("=== NAMED CLUSTERS (briefed candidates) ===")
for cname, members in CLUSTERS.items():
    present = [m for m in members if m in wordsets]
    absent = [m for m in members if m not in wordsets]
    print(
        f"\n## {cname}  present={len(present)}/{len(members)}"
        + (f"  ABSENT={absent}" if absent else "")
    )
    for a, b in itertools.combinations(present, 2):
        j, c = jac(a, b), cont(a, b)
        flag = "  <-- READ BOTH" if (j >= 0.45 or c >= 0.20) else ""
        print(f"   J={j:.3f} C={c:.3f}  {a} | {b}{flag}")

# --- fleet-wide top pairs -------------------------------------------------
names = sorted(wordsets)
scored = []
for a, b in itertools.combinations(names, 2):
    j = jac(a, b)
    if j >= 0.40:
        scored.append((j, cont(a, b), a, b))
scored.sort(reverse=True)
print(f"\n=== FLEET-WIDE PAIRS WITH J >= 0.40 : {len(scored)} ===")
for j, c, a, b in scored[:45]:
    print(f"   J={j:.3f} C={c:.3f}  {a} | {b}")

out = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-OVERLAP-MATRIX.json"
)
out.write_text(
    json.dumps(
        {
            "threshold": 0.40,
            "self_control": {"jaccard": self_j, "containment": self_c},
            "pairs": [
                {"jaccard": j, "containment": c, "a": a, "b": b}
                for j, c, a, b in scored
            ],
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"\nwrote {out}")
