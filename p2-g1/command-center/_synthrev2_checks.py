"""Synthesis-review pass 2: mechanical checks over command-center/GRIND-STATUS.md.

Everything here is a MEASUREMENT, not a read of a claim. Writes JSON to stdout.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "command-center" / "GRIND-STATUS.md"


def run(args, cwd=REPO):
    p = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, shell=False)
    return p.returncode, p.stdout, p.stderr


text = DOC.read_text(encoding="utf-8", newline="")
lines = text.split("\n")

out = {}

# ---- 1. every cited sha resolves -------------------------------------------------
shas = sorted(set(re.findall(r"`([0-9a-f]{7,40})`", text)))
sha_res = {}
for s in shas:
    rc, so, se = run(["git", "rev-parse", "--verify", "--quiet", s + "^{commit}"])
    sha_res[s] = {"rc": rc, "resolved": so.strip()}
out["cited_shas"] = sha_res

# ---- 2. every cited path exists --------------------------------------------------
# backtick-quoted tokens that look like paths
cands = set()
for m in re.findall(r"`([^`\n]+)`", text):
    tok = m.strip()
    # strip a trailing :NNN line anchor
    tok = re.sub(r":\d+$", "", tok)
    if "/" in tok and not tok.startswith(
        ("http", "git ", "python ", "pytest ", "-", "$")
    ):
        # drop obvious command strings
        if " " in tok:
            continue
        cands.add(tok)
paths = {}
for c in sorted(cands):
    p = REPO / c
    alt = None
    if not p.exists():
        # try under .github/workflows for bare workflow names
        for pref in (".github/workflows", "command-center", "docs"):
            q = REPO / pref / c
            if q.exists():
                alt = str(q.relative_to(REPO)).replace("\\", "/")
                break
    paths[c] = {"exists": p.exists(), "found_under": alt}
out["cited_paths"] = paths

# bare workflow filenames mentioned
wfs = sorted(set(re.findall(r"`?([a-z0-9\-]+\.yml)", text)))
out["cited_workflows"] = {w: (REPO / ".github/workflows" / w).exists() for w in wfs}

# ---- 3. B3 / D2: the §9 credential state at HEAD vs worktree ---------------------
NEG = "NEVER remove, rotate, revoke, regenerate"
INV = "rotate, don't just delete"
res = {}
for label, getter in (
    ("HEAD_blob", lambda: run(["git", "show", "HEAD:agent-self/config/AGENTS.md"])[1]),
    (
        "worktree",
        lambda: (REPO / "agent-self/config/AGENTS.md").read_text(
            encoding="utf-8", newline=""
        ),
    ),
):
    try:
        body = getter()
    except Exception as e:  # noqa: BLE001
        res[label] = {"error": str(e)}
        continue
    body_lf = body.replace("\r\n", "\n")
    res[label] = {
        "lines": len(body_lf.rstrip("\n").split("\n")),
        "non_negotiable": body_lf.count(NEG),
        "inversion": body_lf.lower().count(INV.lower()),
    }
out["credential_sec9"] = res
rc, so, se = run(
    [
        "git",
        "status",
        "--porcelain",
        "--",
        "agent-self/config/AGENTS.md",
        "docs/rule-audit/ci_gate.py",
        "docs/rule-audit/r4_credential_rule_gate.py",
    ]
)
out["credential_dirty"] = {"rc": rc, "porcelain": so.strip()}

# ---- 4. B2: skill-dual-write.yml trigger, HEAD blob vs worktree ------------------
sd = {}
rc, so, se = run(["git", "show", "HEAD:.github/workflows/skill-dual-write.yml"])
sd["HEAD_rc"] = rc
head_yml = so.replace("\r\n", "\n")
sd["HEAD_has_push"] = "\n  push:" in head_yml
sd["HEAD_has_pull_request"] = "\n  pull_request:" in head_yml
wt = (
    (REPO / ".github/workflows/skill-dual-write.yml")
    .read_text(encoding="utf-8", newline="")
    .replace("\r\n", "\n")
)
sd["worktree_has_push"] = "\n  push:" in wt
rc, so, se = run(
    ["git", "status", "--porcelain", "--", ".github/workflows/skill-dual-write.yml"]
)
sd["dirty"] = so.strip()
# control: quality.yml must read push True
q = (
    (REPO / ".github/workflows/quality.yml")
    .read_text(encoding="utf-8", newline="")
    .replace("\r\n", "\n")
)
sd["control_quality_has_push"] = "\n  push:" in q
out["skill_dual_write"] = sd

# ---- 5. commit volume: 247 in 36h ------------------------------------------------
rc, so, se = run(["git", "log", "--since=36 hours ago", "--oneline"])
out["commits_36h"] = len([x for x in so.strip().split("\n") if x.strip()])

# ---- 6. overclaim ledger arithmetic ----------------------------------------------
o_rows = re.findall(r"^\| (O\d+) \|", text, flags=re.M)
mine = re.findall(r"^\| (O\d+) \| \*mine\*", text, flags=re.M)
out["overclaims"] = {
    "row_ids": o_rows,
    "row_count": len(o_rows),
    "mine_ids": mine,
    "mine_count": len(mine),
    "stated_counts": re.findall(
        r"(\d+) overclaims? (?:against|:) (\d+) (?:real )?defects", text
    ),
    "stated_mine": re.findall(r"(\w+|\d+) of the (\d+) are mine", text),
}
# the second table has no header row -> broken markdown
idx = [i for i, ln in enumerate(lines) if ln.startswith("| O")]
gaps = []
for a, b in zip(idx, idx[1:]):
    if b - a > 1:
        gaps.append(
            {"after_line": a + 1, "next_line": b + 1, "between": lines[a + 1 : b]}
        )
out["overclaims"]["table_gaps"] = gaps

# ---- 7. CL / B / D ordering ------------------------------------------------------
out["section_order"] = {
    "B": re.findall(r"^\*\*(B\d+)", text, flags=re.M),
    "CL": re.findall(r"^\*\*(CL\d+)", text, flags=re.M),
    "D": re.findall(r"^\| \*\*(D\d+)\*\*", text, flags=re.M),
}

# ---- 8. GRIND-GATE-RESULTS.json shape -------------------------------------------
try:
    g = json.loads(
        (REPO / "command-center/GRIND-GATE-RESULTS.json").read_text(encoding="utf-8")
    )
    if isinstance(g, dict):
        keys = list(g.keys())
        gates = g.get("gates") or g.get("results") or []
        out["gate_results"] = {
            "top_keys": keys,
            "n_entries": len(gates) if isinstance(gates, list) else None,
        }
        if isinstance(gates, list):
            verdicts = {}
            for e in gates:
                v = e.get("verdict") or e.get("result") or e.get("status")
                verdicts[v] = verdicts.get(v, 0) + 1
            out["gate_results"]["verdicts"] = verdicts
    else:
        out["gate_results"] = {"type": type(g).__name__, "n": len(g)}
except Exception as e:  # noqa: BLE001
    out["gate_results"] = {"error": str(e)}

print(json.dumps(out, indent=2, ensure_ascii=False))
