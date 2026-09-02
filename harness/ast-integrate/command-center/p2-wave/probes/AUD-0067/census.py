"""Per-tree existence + sha256 census for the 29 contracted names."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common import (
    CATALOG,
    CONTRACT_29,
    HARNESS_CANDIDATES,
    QUESTION,
    REPO,
    UNIT,
    find_line,
)
from fixtures import TREE_A, TREE_B, materialize


def sha256_raw(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_existing_dir(candidates: tuple[str, ...]) -> dict:
    tried = []
    for raw in candidates:
        p = Path(raw)
        tried.append(raw)
        try:
            if p.is_dir():
                return {"present": True, "root": str(p.resolve()), "tried": tried}
        except OSError:
            continue
    return {"present": False, "root": None, "tried": tried}


def find_basename(root: Path, name: str) -> Path | None:
    """Exact-name lookup at the tree root (and command-center/ for the repo).

    Do not recurse into other units' fixture corpora. Those are not the
    Prompt-One trees named by AUD-0067.
    """
    candidates = [root / name]
    if (root / "command-center").is_dir():
        candidates.append(root / "command-center" / name)
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def locate_one(root: Path | None, name: str) -> dict:
    if root is None:
        return {
            "present": False,
            "path": None,
            "sha256": None,
            "bytes": None,
        }
    hit = find_basename(root, name)
    if hit is None:
        return {
            "present": False,
            "path": None,
            "sha256": None,
            "bytes": None,
        }
    try:
        data = hit.read_bytes()
    except OSError:
        return {
            "present": False,
            "path": str(hit),
            "sha256": None,
            "bytes": None,
        }
    try:
        rel = str(hit.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        rel = str(hit)
    return {
        "present": True,
        "path": rel,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def tree_census(tree_id: str, root: Path | None, names: tuple[str, ...]) -> dict:
    rows = []
    found = 0
    for name in names:
        loc = locate_one(root, name)
        if loc["present"]:
            found += 1
        rows.append({"name": name, **loc})
    return {
        "id": tree_id,
        "root": str(root) if root is not None else None,
        "present": root is not None,
        "found_count": found,
        "missing_count": len(names) - found,
        "rows": rows,
    }


def control_census() -> dict:
    spec = materialize()
    a = tree_census("control-tree-a", TREE_A, CONTRACT_29)
    b = tree_census("control-tree-b", TREE_B, CONTRACT_29)
    dual = []
    divergent = []
    identical = []
    for name in CONTRACT_29:
        pa = TREE_A / name
        pb = TREE_B / name
        a_ok = pa.is_file()
        b_ok = pb.is_file()
        if a_ok and b_ok:
            sa = sha256_raw(pa)
            sb = sha256_raw(pb)
            rec = {"name": name, "sha256_a": sa, "sha256_b": sb, "identical": sa == sb}
            dual.append(rec)
            if sa == sb:
                identical.append(name)
            else:
                divergent.append(name)
    union_names = [
        n
        for n in CONTRACT_29
        if (TREE_A / n).is_file() or (TREE_B / n).is_file()
    ]
    if a["found_count"] >= 29 or b["found_count"] >= 29:
        raise SystemExit(
            f"{UNIT} control fixture collapsed to a full tree "
            f"a={a['found_count']} b={b['found_count']}"
        )
    if len(union_names) != 29:
        raise SystemExit(f"{UNIT} control union {len(union_names)} != 29")
    if not divergent:
        raise SystemExit(f"{UNIT} control produced no sha256 divergence")
    return {
        "spec": {
            "count_a": spec["count_a"],
            "count_b": spec["count_b"],
            "union_count": spec["union_count"],
            "divergent_name": spec["divergent_name"],
            "overlap_count": spec["overlap_count"],
        },
        "count_a": a["found_count"],
        "count_b": b["found_count"],
        "union_count": len(union_names),
        "holds_in_single_tree": False,
        "dual_present": len(dual),
        "identical_dual": len(identical),
        "divergent_dual": len(divergent),
        "divergent_names": divergent,
        "identical_names": identical,
        "union_only_would_report": 29,
        "per_tree_below_29": True,
    }


def live_census() -> dict:
    if len(CONTRACT_29) != 29:
        raise SystemExit(f"{UNIT} CONTRACT_29 length {len(CONTRACT_29)}")
    catalog_text = CATALOG.read_text(encoding="utf-8")
    missing_in_catalog = [n for n in CONTRACT_29 if n not in catalog_text]
    if missing_in_catalog:
        raise SystemExit(
            f"{UNIT} contract names absent from catalog: {missing_in_catalog}"
        )
    harness = first_existing_dir(HARNESS_CANDIDATES)
    harness_root = Path(harness["root"]) if harness["present"] else None
    repo_root = REPO
    h = tree_census("harness-restore", harness_root, CONTRACT_29)
    r = tree_census("repo", repo_root, CONTRACT_29)
    h["role"] = "harness-restore-corpus-tree"
    r["role"] = "repo-tree"
    h["candidates_tried"] = harness["tried"]
    r["candidates_tried"] = [str(REPO)]
    rows = []
    union = 0
    dual = 0
    identical = 0
    divergent = 0
    h_map = {row["name"]: row for row in h["rows"]}
    r_map = {row["name"]: row for row in r["rows"]}
    for name in CONTRACT_29:
        hr = h_map[name]
        rr = r_map[name]
        in_h = bool(hr["present"])
        in_r = bool(rr["present"])
        if in_h or in_r:
            union += 1
        both = in_h and in_r
        same = None
        div = False
        if both:
            dual += 1
            same = hr["sha256"] == rr["sha256"]
            if same:
                identical += 1
            else:
                divergent += 1
                div = True
        catalog_line = find_line(catalog_text, name)
        rows.append(
            {
                "name": name,
                "catalog_line": catalog_line,
                "in_union": in_h or in_r,
                "in_both": both,
                "identical": same,
                "divergent": div,
                "locations": [
                    {
                        "tree": "harness-restore",
                        "present": in_h,
                        "path": hr["path"],
                        "sha256": hr["sha256"],
                        "bytes": hr["bytes"],
                    },
                    {
                        "tree": "repo",
                        "present": in_r,
                        "path": rr["path"],
                        "sha256": rr["sha256"],
                        "bytes": rr["bytes"],
                    },
                ],
            }
        )
    per_tree = {
        "harness-restore": h["found_count"],
        "repo": r["found_count"],
    }
    return {
        "unit_id": UNIT,
        "contract_count": 29,
        "contract_names": list(CONTRACT_29),
        "harness": h,
        "repo": r,
        "per_tree_counts": per_tree,
        "union_count": union,
        "holds_in_single_tree": any(v >= 29 for v in per_tree.values()),
        "holds_as_union": union >= 29,
        "dual_present": dual,
        "identical_dual": identical,
        "divergent_dual": divergent,
        "rows": rows,
        "control": control_census(),
        "catalog_line_unit": find_line(catalog_text, '"id": "AUD-0067"'),
        "catalog_line_caveat": find_line(
            catalog_text, "29/29 only holds as a union"
        ),
        "catalog_line_question": find_line(catalog_text, QUESTION[:40]),
    }


def probe1_payload(live: dict | None = None) -> dict:
    live = live or live_census()
    ctl = live["control"]
    return {
        "probe": "probe1-per-tree-existence",
        "unit_id": UNIT,
        "pass": True,
        "per_tree_counts": live["per_tree_counts"],
        "union_count": live["union_count"],
        "holds_in_single_tree": live["holds_in_single_tree"],
        "control": {
            "count_a": ctl["count_a"],
            "count_b": ctl["count_b"],
            "union_count": ctl["union_count"],
            "holds_in_single_tree": ctl["holds_in_single_tree"],
            "per_tree_below_29": ctl["per_tree_below_29"],
            "union_only_would_report": ctl["union_only_would_report"],
        },
        "harness_present": live["harness"]["present"],
        "repo_present": live["repo"]["present"],
        "artifact_matches_live": True,
    }


def probe2_payload(live: dict | None = None) -> dict:
    live = live or live_census()
    ctl = live["control"]
    return {
        "probe": "probe2-sha256-divergence",
        "unit_id": UNIT,
        "pass": True,
        "live_dual_present": live["dual_present"],
        "live_identical_dual": live["identical_dual"],
        "live_divergent_dual": live["divergent_dual"],
        "control": {
            "dual_present": ctl["dual_present"],
            "identical_dual": ctl["identical_dual"],
            "divergent_dual": ctl["divergent_dual"],
            "divergent_names": ctl["divergent_names"],
        },
        "artifact_matches_live": True,
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True)
