#!/usr/bin/env python
"""Eval harness: LEXICAL vs PURE-SEMANTIC vs HYBRID router recall on the same prompts.

Extends the lexical skill-router eval. Three variants are run per prompt:
  LEXICAL  = the old hooks/skill-router/route.py (IDF token overlap + capabilities regex)
  SEMANTIC = this router with SEMROUTER_PURE=1 (embeddings only — no intents, no lexical lanes)
  HYBRID   = this router as shipped (semantic recall + intent table + capabilities)

Cases are split into KEYWORD-MATCH (regression guard: the semantic/hybrid must not lose what
lexical already got) and KEYWORD-MISMATCH (the payoff: the prompt shares no words with the
target skill, where embeddings should beat lexical). Acceptable answers are domain clusters,
since the router surfaces a top-k cluster, not a single unit. Recall = "did ANY acceptable
unit appear in the suggestions". Runs with SEMROUTER_NO_RECORD=1 so success.json is untouched.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Unique per-invocation run id: both routers dedup suggestions per session_id, so REUSING ids
# across eval runs makes the second run look empty (the bug that briefly showed lexical 0/14).
RUNID = f"{os.getpid()}-{int(time.time())}"

SR = Path(__file__).resolve().parent
NEW = str(SR / "route.py")
OLD = str(Path.home() / ".claude" / "hooks" / "skill-router" / "route.py")

# (prompt, acceptable_skills, acceptable_mcp_servers, is_keyword_mismatch)
CASES = [
    # ---- keyword-match (regression guard) ----
    ("write the tests first for this new payment feature, proper TDD with 80 percent coverage",
     ["tdd-workflow", "test-driven-development"], [], False),
    ("review this authentication code for security vulnerabilities and hardcoded secrets before I commit",
     ["security-review", "security-bounty-hunter", "code-security", "security-best-practices"], [], False),
    ("compute the TPSA, logP and number of rotatable bonds for this SMILES string",
     ["cheminformatics-rdkit"], ["rdkit"], False),
    ("convert this horizontal landscape video into a vertical 9 by 16 clip for reels",
     ["reframe"], [], False),
    ("talk in caveman mode from now on to save me tokens",
     ["caveman"], [], False),
    ("convene a council to weigh the tradeoffs of these three architecture options",
     ["council"], [], False),
    ("generate an AOB signature for this function in binary ninja so my trainer survives an update",
     ["binja-sigmaker", "binary-ninja-diff-signatures", "binary-ninja"], ["binary-ninja"], False),
    ("dock a phenibut analog into the GABA-B receptor and run an FEP binding free energy calc",
     ["phenibut-compchem", "structure-based-screening", "schrodinger-maestro-driver"], ["schrodinger"], False),
    # ---- keyword-mismatch (semantic payoff) ----
    ("the app crashes when I click the delete button",
     ["systematic-debugging", "agent-introspection-debugging"], [], True),
    ("my screen is a confusing cluttered mess of buttons and nobody can find anything",
     ["make-interfaces-feel-better", "ui-ux-pro-max", "design-system", "frontend-design-direction"], [], True),
    ("the dashboard feels really slow and laggy when it loads a big list",
     ["benchmark-optimization-loop", "parallel-execution-optimizer"], [], True),
    ("figure out how this program checks the license key so I can bypass it",
     ["reverse-engineering-toolkit", "cheat-engine-workflow", "game-find-anticheat", "security-review",
      "x64dbg", "radare2", "cheat-engine-x64dbg-ida-handoff"], [], True),
    ("I want to know if this candidate compound is safe and how strongly it sticks to the protein",
     ["structure-based-screening", "ddi-admet-research", "drug-discovery-literature-bridge",
      "schrodinger-maestro-driver", "phenibut-compchem"], ["schrodinger", "rdkit", "tooluniverse"], True),
    ("what did we figure out last week about the save file format",
     ["bcsfe-save-roundtrip", "knowledge-ops"], ["basic-memory"], True),
    # ---- negatives (should stay silent) ----
    ("thanks that works great, really appreciate the help", [], [], False),
    ("ok sounds good let us proceed", [], [], False),
]


def parse(out):
    """(set(skills), set(mcp_servers)) from a router JSON emission; both line formats."""
    if not (out or "").strip():
        return set(), set()
    try:
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return set(), set()
    if "router]" not in ctx:
        return set(), set()
    mcps = set(re.findall(r"mcp__([a-z0-9_-]+)__", ctx))
    # isolate the "skills:" segment so command/deliberation slashes aren't counted as skills
    m = re.search(r"skills:\s*(.*?)(?:\s\|\s|$)", ctx)
    seg = m.group(1) if m else ""
    skills = set(re.findall(r"/([a-z0-9][a-z0-9-]+)", seg))
    return skills, mcps


def run(route, tag, env_extra):
    env = os.environ.copy()
    env.update(env_extra)
    env["SEMROUTER_NO_RECORD"] = "1"
    res = []
    for i, (p, *_rest) in enumerate(CASES):
        payload = {"prompt": p, "session_id": f"eval-{tag}-{RUNID}-{i}"}
        try:
            r = subprocess.run([sys.executable, route], input=json.dumps(payload),
                               capture_output=True, text=True, timeout=30, env=env)
            res.append(parse(r.stdout))
        except Exception:
            res.append((set(), set()))
    return res


def score(res, only=None):
    sr = st = mr = mt = nf = nt = 0
    for (p, es, em, mis), (sk, mc) in zip(CASES, res):
        if only is True and not mis:
            continue
        if only is False and (mis or (not es and not em)):
            continue
        es, em = set(es), set(em)
        if es:
            st += 1; sr += 1 if (es & sk) else 0
        if em:
            mt += 1; mr += 1 if (em & mc) else 0
        if not es and not em:
            nt += 1; nf += 1 if (sk or mc) else 0
    return dict(skill=f"{sr}/{st}", mcp=f"{mr}/{mt}", neg_fire=f"{nf}/{nt}")


def main():
    lex = run(OLD, "lex", {})
    sem = run(NEW, "sem", {"SEMROUTER_PURE": "1"})
    hyb = run(NEW, "hyb", {})
    print("=== per-case skill recall (L=lexical S=pure-semantic H=hybrid; * = keyword-mismatch) ===")
    for (p, es, em, mis), L, S, H in zip(CASES, lex, sem, hyb):
        def hit(r):
            sk, mc = r
            ok_s = bool(set(es) & sk) if es else None
            ok_m = bool(set(em) & mc) if em else None
            if es and em:
                return "Y" if (ok_s and ok_m) else ("y" if (ok_s or ok_m) else ".")
            if es:
                return "Y" if ok_s else "."
            if em:
                return "Y" if ok_m else "."
            return "-" if (sk or mc) else "."  # negative: '.' good, '-' fired
        print(f"  {'*' if mis else ' '} L:{hit(L)} S:{hit(S)} H:{hit(H)}  {p[:60]}")
    print("\n=== AGGREGATE ===")
    print(f"  {'variant':10s} {'ALL':22s} {'keyword-MATCH':22s} keyword-MISMATCH")
    for name, r in (("LEXICAL", lex), ("SEMANTIC", sem), ("HYBRID", hyb)):
        a, mm, ms = score(r), score(r, only=False), score(r, only=True)
        print(f"  {name:10s} skill={a['skill']:>6} mcp={a['mcp']:>5} neg={a['neg_fire']:>5}   "
              f"skill={mm['skill']:>6} mcp={mm['mcp']:>5}    skill={ms['skill']:>6} mcp={ms['mcp']:>5}")


if __name__ == "__main__":
    main()
