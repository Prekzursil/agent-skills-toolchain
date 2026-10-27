"""SYNTHESIS-REVIEW: extract residual ids from each lane's terminal dossier and diff
against what E2E-WAVE-STATUS.md carries. Answers "did the synthesis drop a residual?"."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOSSIERS = {
    "CS": ["docs/claude-science/CS-INTEGRATE.md", "docs/claude-science/LANE-CS-INTEGRATE.md"],
    "SKILLS": ["command-center/integrate/SKILLS-FLEET-INTEGRATE.md"],
    "MON": ["docs/monitor/MON-INTEGRATE.md"],
    "P2": ["command-center/p2-wave/P2-INTEGRATE.md"],
    "CASUALTY": ["command-center/casualty/LANE-CASUALTY-INTEGRATE.md"],
    "WFSOTA": ["docs/workflow-sota/INTEGRATE-LOG.md"],
}
DOC = os.path.join(ROOT, "command-center", "E2E-WAVE-STATUS.md")
doc = open(DOC, encoding="utf-8", errors="replace").read()

# discover CS dossier if the guesses miss
cs_found = []
for dp, dn, fn in os.walk(os.path.join(ROOT, "docs")):
    for f in fn:
        if f.endswith(".md") and ("INTEGRATE" in f.upper() or "LANE" in f.upper()):
            cs_found.append(os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/"))
out = {"docs_dossiers_found": sorted(cs_found)}

RID = re.compile(r"\bR-?(?:[A-Z]{1,3})?-?\d{1,3}\b")
RESID = re.compile(r"\bR-[A-Z]\d+\b|\bR-I\d+\b|\bR-M\d+\b|\bR\d+\b")

for lane, cands in DOSSIERS.items():
    rec = {"path": None, "exists": False}
    for c in cands:
        p = os.path.join(ROOT, c.replace("/", os.sep))
        if os.path.exists(p):
            rec["path"] = c
            rec["exists"] = True
            break
    if rec["exists"]:
        body = open(os.path.join(ROOT, rec["path"].replace("/", os.sep)), encoding="utf-8",
                    errors="replace").read()
        rec["bytes"] = len(body)
        ids = sorted(set(RESID.findall(body)))
        rec["residual_ids"] = ids
        rec["in_doc"] = {i: (i in doc) for i in ids}
        # residual section headings
        rec["residual_headings"] = [h.strip()[:110] for h in
                                    re.findall(r"^#{1,4}\s*.*(?:RESIDUAL|Residual|residual).*$", body, re.M)]
        # every line that starts a residual bullet
        rec["residual_lines"] = [ln.strip()[:170] for ln in body.splitlines()
                                 if re.match(r"^\s*[-*|]?\s*\*{0,2}(R-?[A-Z]?\d+|R\d+)\b", ln)][:40]
    out[lane] = rec

print(json.dumps(out, indent=1))
