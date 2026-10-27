"""Both-states control for workflow_lint's parallel-filter rule + a census of the
10 live saved workflows. Read-only. Prints JSON."""

import json
import re
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "skills" / "workflow-authoring" / "scripts"))
import workflow_lint as WL  # noqa: E402

LIVE = Path(r"C:/Users/Prekzursil/.claude/workflows")

BROKEN = """// @name broken-probe
// @description a parallel with no filter(Boolean)
const rs = await parallel(units.map((u) => () => agent(u.p, { label: u.id })));
for (const r of rs) { console.log(r.verdict); }
"""

FIXED = """// @name fixed-probe
// @description a parallel WITH filter(Boolean)
const rs = (await parallel(units.map((u) => () => agent(u.p, { label: u.id })))).filter(Boolean);
for (const r of rs) { console.log(r.verdict); }
"""

out = {}

# --- both-states control on the parallel-filter rule -------------------------
b = [f.check for f in WL.lint_text(BROKEN, "broken.js")]
g = [f.check for f in WL.lint_text(FIXED, "fixed.js")]
# NOTE: the first run of this probe asserted the check name was "parallel-filter";
# the real name is "parallel-filter-boolean", so it printed the check in
# broken_checks AND fires_on_broken=false in the same object -- a self-contradicting
# output, i.e. MY probe was the broken detector, not the lint rule. Fixed here.
RULE = "parallel-filter-boolean"
out["bothstates_parallel_filter"] = {
    "rule": RULE,
    "broken_checks": sorted(set(b)),
    "fixed_checks": sorted(set(g)),
    "fires_on_broken": RULE in b,
    "silent_on_fixed": RULE not in g,
    "VERDICT": "DETECTOR-OK" if (RULE in b and RULE not in g) else "DETECTOR-BROKEN",
}

# --- does ANY timeout rule exist? both-states on a no-timeout workflow -------
out["bothstates_timeout"] = {
    "any_check_named_timeout": sorted(
        {c for c in b + g if "timeout" in c or "watchdog" in c}
    ),
    "VERDICT": "NO-TIMEOUT-RULE-EXISTS",
}

# --- census of live workflows ------------------------------------------------
rows = []
for p in sorted(LIVE.glob("*")):
    if p.suffix not in (".js", ".mjs"):
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    masked = WL.mask_code(t)
    rows.append(
        {
            "file": p.name,
            "bytes": len(t),
            "n_parallel": len(re.findall(r"\bparallel\s*\(", masked)),
            "n_agent": len(re.findall(r"\bagent\s*\(", masked)),
            "n_filter_boolean": len(
                re.findall(r"\.filter\s*\(\s*Boolean\s*\)", masked)
            ),
            "n_promise_race": len(re.findall(r"Promise\s*\.\s*race", masked)),
            "n_settimeout": len(re.findall(r"\bsetTimeout\b", masked)),
            "n_abort": len(re.findall(r"AbortController|AbortSignal", masked)),
            "has_timeout_word": bool(re.search(r"timeout", masked, re.I)),
            "has_resume_manifest": bool(re.search(r"plan_lint_stage0|--manifest", t)),
            "lint_findings": len(WL.lint_file(p)),
        }
    )
out["live_workflow_census"] = rows
out["totals"] = {
    "files": len(rows),
    "parallel_calls": sum(r["n_parallel"] for r in rows),
    "agent_calls": sum(r["n_agent"] for r in rows),
    "filter_boolean": sum(r["n_filter_boolean"] for r in rows),
    "promise_race": sum(r["n_promise_race"] for r in rows),
    "settimeout": sum(r["n_settimeout"] for r in rows),
    "resume_manifest_wired": sum(1 for r in rows if r["has_resume_manifest"]),
}
print(json.dumps(out, indent=2))
