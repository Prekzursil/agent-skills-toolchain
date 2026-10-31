"""build/wfa-5 : enumerate the on-disk executed-workflow corpus and diff it against
the prior archaeology registry (08-WORKFLOW-CANDIDATE-REGISTRY.json).

Two populations must NOT be conflated (doc 08 finding 0):
  * run DEFINITION records : ~/.claude/projects/<proj>/<session>/workflows/wf_*.json
  * per-agent artifacts    : .../<session>/subagents/workflows/wf_*/agent-*.meta.json
This script counts BOTH so the discrepancy is visible rather than silent.
"""

import glob
import json
import os
import re
import sys

PROJ = os.path.expanduser("~/.claude/projects")
CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
OUT = "C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa5_corpus.json"

run_records = sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "wf_*.json")))
agent_meta = glob.glob(
    os.path.join(PROJ, "*", "*", "subagents", "workflows", "wf_*", "*.json")
)
print("SOURCE PROBE   run definition records :", len(run_records))
print("VERIFIER pop-2 per-agent meta artifacts:", len(agent_meta))

scripts = sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "scripts", "*")))
print("script files on disk                  :", len(scripts))

runs = []
for p in run_records:
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        runs.append({"record": p, "parse_error": str(exc)})
        continue
    runs.append(
        {
            "record": p,
            "id": d.get("id"),
            "name": d.get("name"),
            "status": d.get("status"),
            "agentCount": d.get("agentCount"),
            "durationMs": d.get("durationMs"),
            "phases": len(d.get("phases") or [])
            if isinstance(d.get("phases"), list)
            else d.get("phases"),
            "scriptPath": d.get("scriptPath") or d.get("script") or d.get("path"),
            "startedAt": d.get("startedAt") or d.get("createdAt"),
            "keys": sorted(d.keys()),
        }
    )

# what does a record actually look like
sample = [r for r in runs if not r.get("parse_error")][:1]
print("sample record keys:", sample[0]["keys"] if sample else "NONE")

# index scripts by basename stem, strip the trailing -wf_<id> suffix
stem_re = re.compile(r"^(?P<name>.+?)-wf_[0-9a-f]{3,}$")
by_name = {}
for s in scripts:
    base = os.path.basename(s)
    stem = os.path.splitext(base)[0]
    m = stem_re.match(stem)
    name = m.group("name") if m else stem
    by_name.setdefault(name, []).append(s)
print("distinct script names on disk:", len(by_name))

# prior registry
with open(
    os.path.join(CORPUS, "08-WORKFLOW-CANDIDATE-REGISTRY.json"), encoding="utf-8"
) as fh:
    prior = json.load(fh)
pri = prior["candidates"]
prior_names = set()
prior_paths = set()
for c in pri:
    prior_names.add(str(c.get("name", "")).strip().lower())
    pv = str(c.get("provenance", ""))
    prior_paths.add(pv.replace("\\", "/").lower())
    for tok in re.findall(r"[\w.\-]+\.(?:js|mjs)", pv):
        prior_names.add(tok.lower())
        prior_names.add(re.sub(r"-wf_[0-9a-f]{3,}\.m?js$", "", tok.lower()))

print("prior registry candidates:", len(pri), "prior name tokens:", len(prior_names))

new = {}
already = {}
for name, paths in by_name.items():
    key = name.lower()
    hit = key in prior_names or any(
        p.replace("\\", "/").lower() in prior_paths for p in paths
    )
    (already if hit else new)[name] = paths

print("script names ALREADY in prior registry:", len(already))
print("script names NOT in prior registry    :", len(new))

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(
        {
            "counts": {
                "run_definition_records": len(run_records),
                "per_agent_meta_artifacts": len(agent_meta),
                "script_files_on_disk": len(scripts),
                "distinct_script_names": len(by_name),
                "prior_registry_candidates": len(pri),
                "names_already_catalogued": len(already),
                "names_not_catalogued": len(new),
            },
            "runs": runs,
            "scripts_by_name": {k: v for k, v in sorted(by_name.items())},
            "new_names": sorted(new),
            "already_names": sorted(already),
        },
        fh,
        indent=1,
    )
print("wrote", OUT)
sys.exit(0)
