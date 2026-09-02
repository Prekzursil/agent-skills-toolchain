"""P11 - registry re-count, pass 2. Pass 1's `upstream_repo` matcher was BROKEN (it read the
top level; the field lives under `provenance`) and returned 0 duplicate groups. That 0 was a
detector failure, not a refutation of F-W1-07. Detector control below: the matcher must FIND the
known-present pair WFA3-078/WFA3-073 before any count is reported.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
W1_END = "edcf9f5b"


def rows(rev: str | None) -> list[dict]:
    out: list[dict] = []
    for n in range(1, 6):
        rel = f"platform/registry/workflow-candidates-{n}.json"
        if rev:
            r = subprocess.run(
                ["git", "cat-file", "-p", f"{rev}:{rel}"],
                cwd=str(REPO),
                capture_output=True,
                check=True,
            )
            d = json.loads(r.stdout.decode("utf-8"))
        else:
            d = json.loads((REPO / rel).read_text(encoding="utf-8"))
        arr = d if isinstance(d, list) else (d.get("candidates") or d.get("rows") or [])
        if isinstance(arr, dict):
            arr = list(arr.values())
        out.extend(x for x in arr if isinstance(x, dict))
    return out


def upstream_of(rec: dict) -> str:
    prov = rec.get("provenance")
    if isinstance(prov, dict):
        u = prov.get("upstream_repo") or prov.get("upstream") or ""
        if isinstance(u, str):
            return u.strip().rstrip("/").lower()
    u = rec.get("upstream_repo") or ""
    return u.strip().rstrip("/").lower() if isinstance(u, str) else ""


def measure(rev: str | None) -> dict[str, object]:
    rs = rows(rev)
    keep = [
        r
        for r in rs
        if "MANIFEST" not in str(r.get("id", "")).upper()
        and "REJECT" not in str(r.get("id", "")).upper()
    ]
    by_up: dict[str, list[str]] = defaultdict(list)
    no_up = []
    for r in keep:
        u = upstream_of(r)
        if u:
            by_up[u].append(str(r.get("id")))
        else:
            no_up.append(str(r.get("id")))
    dup_groups = {u: sorted(v) for u, v in by_up.items() if len(v) > 1}
    # counts_toward_range: the registry's OWN declared counting rule = a third signal
    ctr = Counter(str(r.get("counts_toward_range")) for r in rs)
    ctr_keep = Counter(str(r.get("counts_toward_range")) for r in keep)
    kinds = Counter(str(r.get("candidate_kind")) for r in keep)
    # marketplace-shell detection by declared kind / name, independent of upstream URL
    shellish = sorted(
        str(r.get("id"))
        for r in keep
        if "shell" in json.dumps(r).lower() and "marketplace" in json.dumps(r).lower()
    )
    excess = sum(len(v) - 1 for v in dup_groups.values())
    return {
        "raw_rows": len(rs),
        "kept": len(keep),
        "rows_with_no_upstream_repo": len(no_up),
        "duplicate_upstream_groups": len(dup_groups),
        "rows_in_a_duplicate_group": sum(len(v) for v in dup_groups.values()),
        "excess_rows_if_one_per_upstream": excess,
        "kept_minus_excess": len(keep) - excess,
        "duplicate_groups": dup_groups,
        "counts_toward_range_all_rows": dict(ctr),
        "counts_toward_range_kept_rows": dict(ctr_keep),
        "candidate_kind_histogram": dict(kinds.most_common()),
        "marketplace_shell_mentioning_rows": shellish,
    }


DETECTOR_CONTROL_PAIR = ("WFA3-078", "WFA3-073")
res = {"anchor": W1_END, "detector_control": {}}
m_now = measure(None)
groups = m_now["duplicate_groups"]
assert isinstance(groups, dict)
found = [
    u for u, ids in groups.items() if set(DETECTOR_CONTROL_PAIR).issubset(set(ids))
]
res["detector_control"] = {
    "requirement": "matcher must FIND the known-present pair WFA3-078/WFA3-073",
    "found_group": found,
    "verdict": "PASS - detector finds a known-present item"
    if found
    else "FAIL - detector blind",
}
res["at_W1_END"] = measure(W1_END)
res["now"] = m_now

# F-W1-07's four named shells, checked one by one against its four named already-counted rows.
claimed = {
    "WFA3-078": ["WFA3-073"],
    "WFA3-079": ["WFA3-072"],
    "WFA3-080": ["WFA3-068"],
    "WFA3-076": ["WFA3-067", "WFA3-069", "WFA3-071", "WFA3-NEW-01", "WFA3-NEW-02"],
}
rs = {str(r.get("id")): r for r in rows(W1_END)}
per_pair = {}
for shell, others in claimed.items():
    su = upstream_of(rs.get(shell, {}))
    per_pair[shell] = {
        "shell_upstream": su,
        "shell_present": shell in rs,
        "matches": {o: (upstream_of(rs.get(o, {})) == su and su != "") for o in others},
        "other_upstreams": {o: upstream_of(rs.get(o, {})) for o in others},
    }
res["F_W1_07_named_pairs_at_W1_END"] = per_pair

dest = REPO / "command-center" / "P11-REGISTRY.json"
dest.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2)[:6000])
print(f"SUCCESS:p11-registry2 {dest}")
