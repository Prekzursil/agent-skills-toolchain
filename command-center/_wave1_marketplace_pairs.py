"""Two corrections + one measurement the fast sweep exposed.

CORRECTION 1 - my anchor resolver is NOT a body resolver.
  It takes the first Windows path in the candidate record, which for many rows is
  the ARCHAEOLOGY DOC or the PRIOR REGISTRY JSON, not the candidate's own body.
  Self-contradiction tell: 32 distinct candidates "resolved" to ONE file. So the
  five byte-identical groups the fast sweep printed are resolver artifacts, not
  duplicate candidates. This script quantifies the artifact so the number is not
  mistaken for a finding.

CORRECTION 2 - the near-copy arm was uncontrolled.
  A seeded near-copy (5% of words perturbed) must land above the 0.80 Jaccard
  threshold, or a "0 near-copies" reading measures nothing.

MEASUREMENT - plugin-vs-marketplace double counting.
  workflow-candidates-3.json appears to count a PLUGIN and the MARKETPLACE that
  ships it as two candidates. Group wc3 rows by upstream_repo and report.
"""

from __future__ import annotations

import collections
import json
import random
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
WINPATH = re.compile(r"[A-Za-z]:[\\/][^\"',;:|\s]*")
WORD = re.compile(r"[A-Za-z0-9_]+")
K = 5

out: dict = {}

# ---------------------------------------------------------------- CORRECTION 1
rows = []
for f in sorted(
    p for p in (PLATFORM / "registry").glob("workflow-candidates-*.json")
    if ".COVERAGE." not in p.name and ".METHOD." not in p.name
):
    raw = json.loads(f.read_text(encoding="utf-8"))
    arr = raw["candidates"] if isinstance(raw, dict) else raw
    for e in arr:
        if not isinstance(e, dict) or "_manifest" in e:
            continue
        cid = str(e.get("id") or "")
        if "REJECT" in cid.upper():
            continue
        rows.append({"file": f.name, "id": cid, "name": e.get("name"), "raw": e})

SHARED_DOC_MARKERS = ("harness-restore-20260806", "08-WORKFLOW-", "07-OPTION-", "09-WORKFLOW-", "13-ARCHITECTURE")
first_path, first_is_shared_doc = {}, {}
for r in rows:
    paths = WINPATH.findall(json.dumps(r["raw"], default=str))
    fp = paths[0].replace("\\", "/") if paths else None
    first_path[r["id"]] = fp
    first_is_shared_doc[r["id"]] = bool(fp and any(m in fp for m in SHARED_DOC_MARKERS))

byfp: dict = collections.defaultdict(list)
for cid, fp in first_path.items():
    if fp:
        byfp[fp].append(cid)
collisions = {k: v for k, v in byfp.items() if len(v) > 1}
out["correction_1_resolver_artifact"] = {
    "claim": "the 5 byte-identical groups reported by _wave1_fork_probe_fast.py are resolver artifacts, not duplicate candidates",
    "candidates": len(rows),
    "candidates_whose_first_path_is_a_SHARED_PROGRAM_DOC": sum(first_is_shared_doc.values()),
    "colliding_first_path_groups": len(collisions),
    "largest_collision_size": max((len(v) for v in collisions.values()), default=0),
    "self_contradiction_tell": "32 distinct candidate ids cannot all BE one file (08-WORKFLOW-CANDIDATE-REGISTRY.json); a probe that says so is broken, so its duplicate verdicts are void",
    "verdict": "the body-level duplicate sweep is REFUTED as a detector; only the groups whose shared path is a genuine artifact body survive",
    "collision_groups": {
        k: {"ids": v, "is_shared_program_doc": any(m in k for m in SHARED_DOC_MARKERS)}
        for k, v in sorted(collisions.items(), key=lambda kv: -len(kv[1]))
    },
}

# ---------------------------------------------------------------- CORRECTION 2
def shingles(text: str) -> frozenset[int]:
    w = WORD.findall(text.lower())
    if len(w) < K:
        return frozenset({hash(" ".join(w))})
    return frozenset(hash(" ".join(w[i:i + K])) for i in range(len(w) - K + 1))


donor = Path("C:/Users/Prekzursil/.agents/skills/ralph-loop/SKILL.md")
dt = donor.read_text(encoding="utf-8", errors="replace")
ds = shingles(dt)
rng = random.Random(20260810)
words = WORD.findall(dt)
ctl_rows = []
for pct in (0.01, 0.05, 0.15, 0.50):
    w2 = list(words)
    n = max(1, int(len(w2) * pct))
    for _ in range(n):
        w2[rng.randrange(len(w2))] = "ZZAUDITPERTURBZZ"
    s2 = shingles(" ".join(w2))
    jac = len(ds & s2) / len(ds | s2)
    ctl_rows.append({
        "words_perturbed_pct": pct,
        "jaccard_vs_original": round(jac, 4),
        "would_be_flagged_at_0_80": jac >= 0.80,
    })
out["correction_2_near_copy_control"] = {
    "claim": "the near-copy arm must FIRE on a seeded near-copy before its 0 counts as evidence",
    "donor": str(donor),
    "donor_words": len(words),
    "donor_shingles": len(ds),
    "self_jaccard": round(len(ds & ds) / len(ds | ds), 4),
    "rows": ctl_rows,
    "arm_is_controlled": any(r["would_be_flagged_at_0_80"] for r in ctl_rows),
    "note": "a 5-gram shingle set decays fast under scattered substitution; the band where the detector fires is what this table establishes",
}

# ---------------------------------------------------------------- MEASUREMENT
def upstream(e: dict):
    p = e.get("provenance")
    if isinstance(p, dict):
        for k in ("upstream_repo", "repo", "verified_body", "verified_path"):
            if p.get(k):
                return k, str(p[k])
    return None, None


byup: dict = collections.defaultdict(list)
for r in rows:
    k, v = upstream(r["raw"])
    if v:
        byup[v.lower().rstrip("/")].append({"id": r["id"], "name": str(r["name"])[:80], "file": r["file"], "field": k})
shared_up = {k: v for k, v in byup.items() if len(v) > 1}
out["measurement_shared_upstream_groups"] = {
    "question": "do any candidates share ONE upstream repo / verified body, i.e. is a plugin and the marketplace that ships it counted twice?",
    "groups": len(shared_up),
    "candidates_involved": sum(len(v) for v in shared_up.values()),
    "collapse_if_each_group_counted_once": sum(len(v) - 1 for v in shared_up.values()),
    "registry_total": len(rows),
    "registry_total_after_that_collapse": len(rows) - sum(len(v) - 1 for v in shared_up.values()),
    "detail": {k: v for k, v in sorted(shared_up.items(), key=lambda kv: -len(kv[1]))},
}

print(json.dumps(out, indent=2, default=str))
