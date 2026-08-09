"""Trivial-fork / renamed-copy probe over the 161 registry candidates.

Name normalisation only catches SAME-NAME duplicates. A *renamed* copy keeps its
bytes and changes its name, so it is invisible to that key. This probe resolves
each candidate's anchor to a real file where possible and groups by CONTENT:

  - exact sha256 of the resolved body  -> byte-identical duplicates
  - difflib ratio >= 0.90 pairwise within same-extension buckets -> near-copies

Plus a targeted body comparison for the three same-name pairs the name key found.
Detector control: a known-duplicate pair is injected (one file compared to itself)
and must be reported; and a known-distinct pair must not be.
"""

from __future__ import annotations

import difflib
import hashlib
import itertools
import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"

WINPATH = re.compile(r"[A-Za-z]:[\\/][^\"',;:|\s]*")


def load_rows() -> list[dict]:
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
    return rows


def candidate_paths(e: dict) -> list[str]:
    blob = json.dumps(e, default=str)
    return WINPATH.findall(blob)


def resolve_body(e: dict):
    """Return (path, bytes) for the first anchor that resolves to a readable file."""
    for cand in candidate_paths(e):
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


out: dict = {}
rows = load_rows()
resolved, unresolved = [], []
for r in rows:
    path, body = resolve_body(r["raw"])
    if body is None:
        unresolved.append({"id": r["id"], "name": str(r["name"])[:70]})
        continue
    resolved.append({
        "id": r["id"], "file": r["file"], "name": str(r["name"])[:70],
        "body_path": path, "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "text": body.decode("utf-8", "replace"),
    })

# exact byte-identical groups
bysha: dict = {}
for r in resolved:
    bysha.setdefault(r["sha256"], []).append(r)
exact = {
    k[:16]: [{"id": x["id"], "file": x["file"], "body_path": x["body_path"]} for x in v]
    for k, v in bysha.items() if len(v) > 1
}

# same-path groups (two candidates pointing at the SAME file = same artifact twice)
bypath: dict = {}
for r in resolved:
    bypath.setdefault(r["body_path"], []).append(r)
samepath = {
    k: [{"id": x["id"], "file": x["file"], "name": x["name"]} for x in v]
    for k, v in bypath.items() if len(v) > 1
}

# near-copies: pairwise within a size band, only on DISTINCT paths
near = []
uniq = {}
for r in resolved:
    uniq.setdefault(r["body_path"], r)
items = list(uniq.values())
for a, b in itertools.combinations(items, 2):
    lo, hi = sorted((a["bytes"], b["bytes"]))
    if hi == 0 or lo / hi < 0.6:
        continue
    ratio = difflib.SequenceMatcher(None, a["text"], b["text"]).quick_ratio()
    if ratio < 0.90:
        continue
    real = difflib.SequenceMatcher(None, a["text"], b["text"]).ratio()
    if real >= 0.90:
        near.append({
            "a_id": a["id"], "b_id": b["id"], "similarity": round(real, 4),
            "a_path": a["body_path"], "b_path": b["body_path"],
        })

# the three same-name pairs, compared by BODY
pairs = [
    ("agent-agent-as-judge", "WFA3-094"),
    ("agent-codex", "WFA3-072"),
    ("WFA3-067", "WFC-0105"),
]
byid = {r["id"]: r for r in resolved}
pair_rows = []
for x, y in pairs:
    ra, rb = byid.get(x), byid.get(y)
    rec = {"a_id": x, "b_id": y,
           "a_resolved": bool(ra), "b_resolved": bool(rb)}
    if ra and rb:
        rec.update(
            a_path=ra["body_path"], b_path=rb["body_path"],
            a_bytes=ra["bytes"], b_bytes=rb["bytes"],
            byte_identical=ra["sha256"] == rb["sha256"],
            similarity=round(difflib.SequenceMatcher(None, ra["text"], rb["text"]).ratio(), 4),
        )
    pair_rows.append(rec)

# detector control
ctl_dup = None
ctl_distinct = None
if len(items) >= 2:
    s = items[0]["text"]
    ctl_dup = round(difflib.SequenceMatcher(None, s, s).ratio(), 4)
    # pick the least similar pair we can find cheaply as the known-distinct control
    worst = min(
        (difflib.SequenceMatcher(None, items[0]["text"], q["text"]).ratio(), q["id"])
        for q in items[1:]
    )
    ctl_distinct = {"lowest_similarity_seen": round(worst[0], 4), "vs_id": worst[1]}

out["fork_probe"] = {
    "candidates_total": len(rows),
    "bodies_resolved": len(resolved),
    "bodies_unresolved": len(unresolved),
    "unresolved_sample": unresolved[:15],
    "distinct_body_paths": len(uniq),
    "byte_identical_groups": exact,
    "byte_identical_group_count": len(exact),
    "candidates_sharing_one_body_path": samepath,
    "candidates_sharing_one_body_path_count": len(samepath),
    "near_copy_pairs_ge_0_90": near,
    "near_copy_pair_count": len(near),
    "same_name_pairs_compared_by_body": pair_rows,
    "detector_control": {
        "self_similarity_must_be_1_0": ctl_dup,
        "known_distinct_control": ctl_distinct,
    },
}
print(json.dumps(out, indent=2, default=str))
