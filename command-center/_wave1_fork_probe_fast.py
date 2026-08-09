"""Fast renamed-copy sweep over the registry candidates (O(n) shingling, not O(n^2) difflib).

Three exact algorithms:
  1. sha256 of the resolved body      -> byte-identical duplicates
  2. same resolved body path          -> two candidates naming ONE artifact
  3. 5-gram word-shingle Jaccard via an inverted index -> near-copies >= 0.80
     (only pairs that share >= 1 rare shingle are ever scored, so it is linear
      in practice; Jaccard is computed exactly on the full shingle sets)

Plus the 3 same-name pairs compared body-to-body, and a detector control that
must (a) score a file against itself at Jaccard 1.0 and (b) surface an
artificially injected byte-identical duplicate.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
WINPATH = re.compile(r"[A-Za-z]:[\\/][^\"',;:|\s]*")
WORD = re.compile(r"[A-Za-z0-9_]+")
K = 5
THRESH = 0.80


def rows_from_registry() -> list[dict]:
    out = []
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
            out.append({"file": f.name, "id": cid, "name": e.get("name"), "raw": e})
    return out


def resolve_body(e: dict):
    for cand in WINPATH.findall(json.dumps(e, default=str)):
        p = Path(cand.replace("\\", "/"))
        try:
            if p.is_file():
                return str(p).replace("\\", "/"), p.read_bytes()
            if p.is_dir():
                for name in ("SKILL.md", "AGENT.md", "README.md", "plugin.json"):
                    q = p / name
                    if q.is_file():
                        return str(q).replace("\\", "/"), q.read_bytes()
        except OSError:
            continue
    return None, None


def shingles(text: str) -> frozenset[int]:
    w = WORD.findall(text.lower())
    if len(w) < K:
        return frozenset({hash(" ".join(w))})
    return frozenset(
        hash(" ".join(w[i:i + K])) for i in range(len(w) - K + 1)
    )


rows = rows_from_registry()
resolved, unresolved = [], []
for r in rows:
    path, body = resolve_body(r["raw"])
    if body is None:
        unresolved.append({"id": r["id"], "name": str(r["name"])[:70]})
        continue
    txt = body.decode("utf-8", "replace")
    resolved.append({
        "id": r["id"], "file": r["file"], "name": str(r["name"])[:70],
        "body_path": path, "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "sh": shingles(txt), "text": txt,
    })

# 1. byte-identical
bysha: dict = collections.defaultdict(list)
for r in resolved:
    bysha[r["sha256"]].append(r)
exact = {
    k[:16]: [{"id": x["id"], "file": x["file"], "body_path": x["body_path"]} for x in v]
    for k, v in bysha.items() if len(v) > 1
}

# 2. same resolved path
bypath: dict = collections.defaultdict(list)
for r in resolved:
    bypath[r["body_path"]].append(r)
samepath = {
    k: [{"id": x["id"], "file": x["file"], "name": x["name"]} for x in v]
    for k, v in bypath.items() if len(v) > 1
}

# 3. near-copies via inverted shingle index over DISTINCT paths
uniq = {}
for r in resolved:
    uniq.setdefault(r["body_path"], r)
items = list(uniq.values())
inv: dict = collections.defaultdict(list)
for i, r in enumerate(items):
    for s in r["sh"]:
        inv[s].append(i)
cand_pairs: collections.Counter = collections.Counter()
for s, idxs in inv.items():
    if len(idxs) < 2 or len(idxs) > 40:
        continue
    for a in range(len(idxs)):
        for b in range(a + 1, len(idxs)):
            cand_pairs[(idxs[a], idxs[b])] += 1
near = []
for (i, j), _shared in cand_pairs.items():
    A, B = items[i]["sh"], items[j]["sh"]
    inter = len(A & B)
    if not inter:
        continue
    jac = inter / len(A | B)
    if jac >= THRESH:
        near.append({
            "a_id": items[i]["id"], "b_id": items[j]["id"],
            "jaccard": round(jac, 4),
            "a_path": items[i]["body_path"], "b_path": items[j]["body_path"],
            "a_bytes": items[i]["bytes"], "b_bytes": items[j]["bytes"],
        })
near.sort(key=lambda r: -r["jaccard"])

# the 3 same-name pairs, body-to-body
byid = {r["id"]: r for r in resolved}
pair_rows = []
for x, y in (("agent-agent-as-judge", "WFA3-094"),
             ("agent-codex", "WFA3-072"),
             ("WFA3-067", "WFC-0105")):
    a, b = byid.get(x), byid.get(y)
    rec = {"a_id": x, "b_id": y, "a_resolved": bool(a), "b_resolved": bool(b)}
    if a and b:
        inter = len(a["sh"] & b["sh"])
        rec.update(
            a_path=a["body_path"], b_path=b["body_path"],
            a_bytes=a["bytes"], b_bytes=b["bytes"],
            byte_identical=a["sha256"] == b["sha256"],
            jaccard=round(inter / len(a["sh"] | b["sh"]), 4),
            verdict=("TRIVIAL-FORK" if a["sha256"] == b["sha256"]
                     else "NEAR-COPY" if inter / len(a["sh"] | b["sh"]) >= THRESH
                     else "MATERIALLY-DISTINCT"),
        )
    pair_rows.append(rec)

# detector control
ctl = {}
if items:
    s = items[0]["sh"]
    ctl["self_jaccard_must_be_1_0"] = round(len(s & s) / len(s | s), 4)
    fake = dict(items[0])
    fake["id"] = "SEEDED-DUPLICATE-CONTROL"
    probe = collections.defaultdict(list)
    for r in resolved + [fake]:
        probe[r["sha256"]].append(r["id"])
    grew = {k[:16]: v for k, v in probe.items() if len(v) > 1}
    ctl["seeded_byte_identical_duplicate_detected"] = any(
        "SEEDED-DUPLICATE-CONTROL" in v for v in grew.values()
    )
    ctl["groups_with_seed"] = {k: v for k, v in grew.items()
                               if "SEEDED-DUPLICATE-CONTROL" in v}

print(json.dumps({
    "candidates_total": len(rows),
    "bodies_resolved": len(resolved),
    "bodies_unresolved": len(unresolved),
    "unresolved_sample": unresolved[:20],
    "distinct_body_paths": len(uniq),
    "byte_identical_group_count": len(exact),
    "byte_identical_groups": exact,
    "candidates_sharing_one_body_path_count": len(samepath),
    "candidates_sharing_one_body_path": samepath,
    "near_copy_threshold_jaccard": THRESH,
    "shingle_k": K,
    "near_copy_pair_count": len(near),
    "near_copy_pairs": near[:40],
    "same_name_pairs_by_body": pair_rows,
    "detector_control": ctl,
}, indent=2, default=str))
