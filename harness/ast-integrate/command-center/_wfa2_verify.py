"""Read the WRITTEN slice back off disk and verify it independently.

Deliberately does NOT import the generator: this re-implements the checks
against the bytes actually on disk, so a generator bug cannot certify itself.
"""

from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path

P = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/catalog-slices/WFA-2.json"
)

CONTRACT = [
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
]

raw = P.read_bytes()
units = json.loads(raw.decode("utf-8"))

print("file            :", P)
print("bytes           :", len(raw))
print("parses          :", isinstance(units, list))
print("UNIT COUNT      :", len(units))
print("ids_first       :", units[0]["id"])
print("ids_last        :", units[-1]["id"])
print(
    "ids_sequential  :",
    [u["id"] for u in units] == [f"WFA-{n:04d}" for n in range(129, 129 + len(units))],
)
print("all_19_fields   :", all(all(f in u for f in CONTRACT) for u in units))
print(
    "no_empty_field  :",
    all(
        all(
            u[f] not in (None, "", [], {})
            for f in CONTRACT
            if f != "owner_approval_required"
        )
        for u in units
    ),
)
print(
    "phases          :",
    sorted({u["phase"] for u in units}),
    dict(
        sorted(
            {
                p: sum(1 for u in units if u["phase"] == p)
                for p in {x["phase"] for x in units}
            }.items()
        )
    ),
)
print(
    "substrates      :",
    {
        s: sum(1 for u in units if u["execution_substrate"] == s)
        for s in sorted({x["execution_substrate"] for x in units})
    },
)
print("owner_gated     :", [u["id"] for u in units if u["owner_approval_required"]])
print(
    "timeout range   :",
    min(u["timeout_seconds"] for u in units),
    "-",
    max(u["timeout_seconds"] for u in units),
)
print("output_paths_uq :", len({u["output_path"] for u in units}) == len(units))
print(
    "sentinels_ok    :",
    all(u["completion_sentinel"] == "SUCCESS:" + u["id"] for u in units),
)

# intra-slice dependency references must resolve
ids = {u["id"] for u in units}
ext = set()
unresolved = []
for u in units:
    for d in u["dependencies"]:
        if d.startswith("WFA-0"):
            if d not in ids:
                unresolved.append((u["id"], d))
        else:
            ext.add(d)
print("intra_dep_unresolved:", unresolved)
print("external_dep_codes  :", sorted(ext))

STOP = set(
    "a an the and or of to for that this with is are be as by on in it its from not "
    "must every each which what when does do not no any all one two".split()
)


def toks(s):
    return {
        w for w in re.findall(r"[a-z0-9_-]+", s.lower()) if w not in STOP and len(w) > 2
    }


pairs = []
for a, b in combinations(units, 2):
    ta = toks(a["title"] + " " + a["question_or_target"] + " " + a["mechanism"])
    tb = toks(b["title"] + " " + b["question_or_target"] + " " + b["mechanism"])
    pairs.append((len(ta & tb) / len(ta | tb), a["id"], b["id"]))
pairs.sort(reverse=True)
print(
    "closest 5 pairs (token-Jaccard; LEXICAL ONLY, a full-rewrite paraphrase would evade it):"
)
for j, x, y in pairs[:5]:
    print(f"   {j:.3f}  {x} <-> {y}")
print("max_jaccard     :", round(pairs[0][0], 3))
print("mean_jaccard    :", round(sum(p[0] for p in pairs) / len(pairs), 3))
print("nodup_sentences :", sum(1 for u in units if u.get("not_a_duplicate_because")))
