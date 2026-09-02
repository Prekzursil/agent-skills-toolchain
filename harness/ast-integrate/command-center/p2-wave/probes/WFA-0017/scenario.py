#!/usr/bin/env python3
"""WFA-0017 skill-tree inventory, load semantics, and G-family 96 analysis."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    start = HERE
    for parent in [start, *start.parents]:
        if (parent / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return parent
    return HERE.parents[3]


REPO = _repo_root()
UNIT = "WFA-0017"
SENTINEL = "SUCCESS:WFA-0017"
OUT_REL = "command-center/wfa/WFA-0017-sweep-installed-skills.json"
OUT = REPO / OUT_REL
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json"
FIXTURE_TREES = HERE / "fixtures" / "trees"
FIXTURE_LOAD = HERE / "fixtures" / "load"
ALWAYS_ON = "ALWAYS-ON"
LAZY = "LAZY"
STAGE_HEADING = re.compile(
    r"^#{1,6}\s*((?:stage|step|phase|round)\s+\d+)\b",
    re.IGNORECASE | re.MULTILINE,
)
SKILL_NAMES = {"skill.md"}
WFA42_INSPECT = (
    REPO / "command-center/p2-wave/probes/WFA-0042/_inspect_source_out.json"
)
REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"
# Last measured Prompt-One 284-row body (WFA-0042 inspect). Absent here.
HOST_REGISTRY_SHA256 = (
    "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
)
HOST_REGISTRY_N = 284
HOST_REGISTRY_BYTES = 261589
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv"}

sys.path.insert(0, str(REPO / "tools" / "router"))
import inspect_load as INS  # noqa: E402
import load_semantics as LS  # noqa: E402


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def parse_frontmatter_mapping(text: str) -> dict[str, Any]:
    block, _body = LS.extract_frontmatter(text)
    if block is None:
        return {}
    try:
        mapping = LS._parse_yaml_mapping(block)
        if isinstance(mapping, dict):
            return mapping
    except Exception:
        pass
    out: dict[str, Any] = {}
    for line in block.splitlines():
        if not line or line[:1] in " \t#-":
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        if key:
            out[key] = val.strip().strip('"').strip("'")
    return out


def skill_name(path: Path, mapping: dict[str, Any]) -> str:
    name = mapping.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return path.parent.name


def is_multi_stage(text: str, mapping: dict[str, Any]) -> bool:
    for key in ("stages", "steps", "workflow"):
        val = mapping.get(key)
        if isinstance(val, list) and len(val) >= 2:
            return True
    found = {m.group(1).lower() for m in STAGE_HEADING.finditer(text)}
    return len(found) >= 2


def load_mode_predicted(text: str) -> str:
    return LS.resolve_load_mode(text)


def load_mode_measured(text: str) -> str:
    return INS.inspect_load_mode(text)


def record_skill(path: Path, tree_id: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    mapping = parse_frontmatter_mapping(text)
    sha, size = digest_file(path)
    predicted = load_mode_predicted(text)
    measured = load_mode_measured(text)
    return {
        "tree_id": tree_id,
        "name": skill_name(path, mapping),
        "path": str(path),
        "sha256": sha,
        "bytes": size,
        "load_mode_predicted": predicted,
        "load_mode_measured": measured,
        "load_mode": measured,
        "has_paths_key": "paths" in mapping,
        "has_frontmatter": LS.extract_frontmatter(text)[0] is not None,
        "multi_stage": is_multi_stage(text, mapping),
        "frontmatter_keys": sorted(str(k) for k in mapping.keys()),
    }


def iter_skill_md(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if name.lower() not in SKILL_NAMES:
                continue
            p = Path(dirpath) / name
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            found.append(p)
    return sorted(found)


def inventory_tree(root: Path, tree_id: str) -> dict[str, Any]:
    exists = root.is_dir()
    rows = [record_skill(p, tree_id) for p in iter_skill_md(root)] if exists else []
    names = sorted({r["name"] for r in rows})
    return {
        "tree_id": tree_id,
        "root": str(root),
        "exists": exists,
        "n_skill_md": len(rows),
        "n_names": len(names),
        "names": names,
        "n_multi_stage": sum(1 for r in rows if r["multi_stage"]),
        "rows": rows,
    }


def classify_name_presence(agents_names: set[str], claude_names: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in sorted(agents_names | claude_names):
        in_a = n in agents_names
        in_c = n in claude_names
        if in_a and in_c:
            out[n] = "both"
        elif in_a:
            out[n] = "agents_only"
        else:
            out[n] = "claude_only"
    return out


def hash_agreement(
    agents_rows: list[dict[str, Any]], claude_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Content-hash equality per shared name. Independent of name-set intersection."""
    by_a: dict[str, set[str]] = {}
    by_c: dict[str, set[str]] = {}
    for r in agents_rows:
        by_a.setdefault(r["name"], set()).add(r["sha256"])
    for r in claude_rows:
        by_c.setdefault(r["name"], set()).add(r["sha256"])
    shared = sorted(set(by_a) & set(by_c))
    identical: list[str] = []
    divergent: list[str] = []
    for name in shared:
        if by_a[name] == by_c[name] and len(by_a[name]) == 1:
            identical.append(name)
        else:
            divergent.append(name)
    return {
        "shared_names": shared,
        "n_shared": len(shared),
        "identical_content": identical,
        "divergent_content": divergent,
        "n_identical": len(identical),
        "n_divergent": len(divergent),
    }


def candidate_tree_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".agents" / "skills",
        home / ".claude" / "skills",
        Path("/home/ubuntu/.agents/skills"),
        Path("/home/ubuntu/.claude/skills"),
        Path("/root/.agents/skills"),
        Path("/root/.claude/skills"),
        Path("/mnt/c/Users/Prekzursil/.agents/skills"),
        Path("/mnt/c/Users/Prekzursil/.claude/skills"),
        Path("C:/Users/Prekzursil/.agents/skills"),
        Path("C:/Users/Prekzursil/.claude/skills"),
        REPO / "skills",
        REPO / ".agents" / "skills",
        REPO / ".claude" / "skills",
        Path("/mnt/c/Users/Prekzursil/source/ast-integrate/skills"),
        Path("C:/Users/Prekzursil/source/ast-integrate/skills"),
    ]


def _resolved_or_none(path: Path) -> Path | None:
    try:
        if path.is_dir():
            return path.resolve()
    except OSError:
        return None
    return None


def live_trees() -> dict[str, Path]:
    """Live deployed trees stay named as home paths even when absent.

    Repo `.agents/skills` is the canonical published root, not a substitute
    for `~/.agents/skills`. Catalog `skills/` is the compat copy.
    """
    home = Path.home()
    repo_canonical = REPO / ".agents" / "skills"
    repo_compat = REPO / "skills"
    agents = home / ".agents" / "skills"
    claude = home / ".claude" / "skills"
    repo_canon_res = _resolved_or_none(repo_canonical)
    repo_compat_res = _resolved_or_none(repo_compat)
    for p in candidate_tree_roots():
        resolved = _resolved_or_none(p)
        if resolved is None:
            continue
        if repo_canon_res and resolved == repo_canon_res:
            continue
        if repo_compat_res and resolved == repo_compat_res:
            continue
        s = str(p).replace("\\", "/")
        if s.endswith(".agents/skills") and not agents.is_dir():
            agents = p
        if s.endswith(".claude/skills") and not claude.is_dir():
            claude = p
    return {
        "agents": agents,
        "claude": claude,
        "repo": repo_compat,
        "repo_canonical": repo_canonical,
    }


def registry_candidate_paths() -> list[Path]:
    named = [
        Path.home() / ".claude" / "harness-restore-20260806" / REGISTRY_NAME,
        Path("/home/ubuntu/.claude/harness-restore-20260806") / REGISTRY_NAME,
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
        Path("/root/.claude/harness-restore-20260806") / REGISTRY_NAME,
        REPO / REGISTRY_NAME,
        REPO / "command-center" / REGISTRY_NAME,
        REPO / "command-center" / "p2-wave" / REGISTRY_NAME,
        HERE / "fixtures" / REGISTRY_NAME,
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for p in named:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _is_host_registry(path: Path, sha: str, n_candidates: int, nbytes: int) -> bool:
    """Accept only the Prompt-One 284-row body, never another unit's fixture."""
    posix = str(path).replace("\\", "/")
    if "/fixtures/" in posix or "\\fixtures\\" in posix:
        return False
    if sha == HOST_REGISTRY_SHA256:
        return True
    if (
        path.name == REGISTRY_NAME
        and n_candidates == HOST_REGISTRY_N
        and nbytes == HOST_REGISTRY_BYTES
    ):
        return True
    return False


def load_registry() -> dict[str, Any]:
    probed = []
    for path in registry_candidate_paths():
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        row = {"path": str(path), "exists": exists, "bytes": size}
        probed.append(row)
        if not exists or size <= 0:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            row["rejected"] = "unparseable"
            continue
        if not isinstance(doc, dict):
            row["rejected"] = "not-object"
            continue
        cands = doc.get("candidates")
        if not isinstance(cands, list):
            row["rejected"] = "no-candidates-list"
            continue
        sha, nbytes = digest_file(path)
        row["sha256"] = sha
        row["n_candidates"] = len(cands)
        if not _is_host_registry(path, sha, len(cands), nbytes):
            row["rejected"] = "not-host-284-row-registry"
            continue
        return {
            "present": True,
            "path": str(path),
            "sha256": sha,
            "bytes": nbytes,
            "n_candidates": len(cands),
            "doc": doc,
            "probed": probed,
        }
    return {"present": False, "path": None, "doc": None, "probed": probed}


def _family_of(row: dict[str, Any]) -> str:
    fam = row.get("family")
    if isinstance(fam, str) and fam:
        return fam
    cls = row.get("classification")
    if isinstance(cls, dict):
        f2 = cls.get("family")
        if isinstance(f2, str):
            return f2
    return ""


def _provenance_blob(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("provenance", "origin", "path", "src", "source"):
        val = row.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, (dict, list)):
            parts.append(json.dumps(val, sort_keys=True))
    return "\n".join(parts).replace("\\", "/").lower()


def analyze_g_family(reg: dict[str, Any]) -> dict[str, Any]:
    inspect: dict[str, Any] = {}
    if WFA42_INSPECT.is_file():
        try:
            inspect = json.loads(WFA42_INSPECT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inspect = {}
    inspect_counts = inspect.get("json_family_counts") or {}
    inspect_n = inspect.get("json_n")
    inspect_sha = inspect.get("source_sha256")

    if not reg.get("present"):
        g_count = inspect_counts.get("G-skill")
        summed = inspect_counts.values() if isinstance(inspect_counts, dict) else []
        families_sum = sum(int(v) for v in summed if isinstance(v, int))
        return {
            "registry_body_present": False,
            "registry_path": None,
            "g_skill_row_count": g_count,
            "registry_n": inspect_n,
            "family_histogram_sum": families_sum,
            "family_histogram": inspect_counts,
            "inspect_source": str(WFA42_INSPECT.relative_to(REPO))
            if WFA42_INSPECT.is_file()
            else None,
            "inspect_source_sha256": inspect_sha,
            "unique_g_ids": None,
            "unique_g_names": None,
            "n_g_provenance_agents": None,
            "n_g_provenance_claude": None,
            "counting_rule": "family-field-histogram-over-candidate-rows",
            "registry_96_is_summed_across_trees": None,
            "registry_96_is_name_deduplicated": None,
            "settled": False,
            "kind": "FAMILY-BUCKET-ROW-COUNT-UNSETTLED-PAIR-DUPLICATES",
            "statement": (
                "The catalog's 96 is the G-skill family-bucket size on the "
                "284-row candidate registry (WFA-0042 inspect: G-skill=96, "
                f"json_n={inspect_n}, histogram_sum={families_sum}, "
                f"source_sha256={inspect_sha}). That number is a per-row family "
                "label count, not a live walk of ~/.agents/skills plus "
                "~/.claude/skills. Whether those 96 rows themselves pair-duplicate "
                "the two deployed trees (summed) or list each skill once "
                "(deduplicated) cannot be settled without the registry body, "
                "which is absent on this Linux worktree. Live tree intersection "
                "and content-hash equality are measured separately and do not "
                "impersonate the missing registry body."
            ),
        }

    doc = reg["doc"]
    cands = list(doc.get("candidates") or [])
    g_rows = [c for c in cands if _family_of(c) == "G-skill"]
    ids = [str(c.get("id") or "") for c in g_rows]
    names = [str(c.get("name") or "") for c in g_rows]
    n_rows = len(g_rows)
    n_ids = len({i for i in ids if i})
    n_names = len({n for n in names if n})
    n_agents = sum(1 for c in g_rows if ".agents/skills" in _provenance_blob(c))
    n_claude = sum(1 for c in g_rows if ".claude/skills" in _provenance_blob(c))
    pair_dup = n_names > 0 and n_rows == 2 * n_names
    name_dedup = n_rows == n_names == n_ids
    if pair_dup:
        kind = "SUMMED"
        summed_flag = True
        dedup = False
    elif name_dedup:
        kind = "DEDUPLICATED"
        summed_flag = False
        dedup = True
    else:
        kind = "MIXED-OR-COLLIDING"
        summed_flag = False
        dedup = n_rows == n_ids
    if summed_flag:
        clause = "a summed double-count (row count is 2× unique names)."
    elif dedup and n_rows == n_names:
        clause = "a deduplicated per-id/per-name count, not a sum of the two trees."
    else:
        clause = (
            "a per-candidate-id family-bucket count "
            f"(rows={n_rows}, unique names={n_names}); not a raw tree-walk sum."
        )
    return {
        "registry_body_present": True,
        "registry_path": reg.get("path"),
        "registry_sha256": reg.get("sha256"),
        "g_skill_row_count": n_rows,
        "registry_n": len(cands),
        "unique_g_ids": n_ids,
        "unique_g_names": n_names,
        "n_g_provenance_agents": n_agents,
        "n_g_provenance_claude": n_claude,
        "counting_rule": "family-field-on-candidate-rows",
        "registry_96_is_summed_across_trees": summed_flag,
        "registry_96_is_name_deduplicated": bool(dedup and n_rows == n_names),
        "settled": True,
        "kind": kind,
        "statement": (
            f"G-skill rows={n_rows} unique_ids={n_ids} unique_names={n_names} "
            f"provenance_agents={n_agents} provenance_claude={n_claude}. "
            f"kind={kind}. The catalog 96 is {clause}"
        ),
        "g_ids_sample": ids[:12],
        "g_names_sample": names[:12],
    }


def load_controls() -> dict[str, Any]:
    files = {
        "no_frontmatter": FIXTURE_LOAD / "always-on-no-frontmatter.md",
        "other_keys": FIXTURE_LOAD / "always-on-other-keys.md",
        "with_paths": FIXTURE_LOAD / "lazy-with-paths.md",
    }
    rows = {}
    for key, path in files.items():
        text = path.read_text(encoding="utf-8")
        pred = load_mode_predicted(text)
        meas = load_mode_measured(text)
        rows[key] = {
            "path": str(path.relative_to(REPO)),
            "predicted": pred,
            "measured": meas,
            "agree": pred == meas,
        }
    inversion = (
        rows["no_frontmatter"]["measured"] == ALWAYS_ON
        and rows["other_keys"]["measured"] == ALWAYS_ON
        and rows["with_paths"]["measured"] == LAZY
        and rows["no_frontmatter"]["measured"] != rows["with_paths"]["measured"]
    )
    return {
        "rows": rows,
        "inversion_holds": inversion,
        "absence_means_always_on": rows["no_frontmatter"]["measured"] == ALWAYS_ON
        and rows["other_keys"]["measured"] == ALWAYS_ON,
        "paths_key_means_lazy": rows["with_paths"]["measured"] == LAZY,
        "never_loaded_rejected": all(
            r["measured"] in {ALWAYS_ON, LAZY} for r in rows.values()
        ),
        "instrument_agrees": all(r["agree"] for r in rows.values()),
    }


def detector_control() -> dict[str, Any]:
    agents = inventory_tree(FIXTURE_TREES / "agents", "fixture-agents")
    claude = inventory_tree(FIXTURE_TREES / "claude", "fixture-claude")
    a_names = set(agents["names"])
    c_names = set(claude["names"])
    presence = classify_name_presence(a_names, c_names)
    hashes = hash_agreement(agents["rows"], claude["rows"])
    expected = {
        "wfa0017-only-agents": "agents_only",
        "wfa0017-only-claude": "claude_only",
        "wfa0017-shared-identical": "both",
        "wfa0017-shared-divergent": "both",
    }
    mismatches = {
        k: presence.get(k) for k, v in expected.items() if presence.get(k) != v
    }
    ident_ok = "wfa0017-shared-identical" in hashes["identical_content"]
    div_ok = "wfa0017-shared-divergent" in hashes["divergent_content"]
    only_ok = (
        "wfa0017-only-agents" not in hashes["shared_names"]
        and "wfa0017-only-claude" not in hashes["shared_names"]
    )
    passed = not mismatches and ident_ok and div_ok and only_ok
    return {
        "agents": {"n": agents["n_skill_md"], "names": agents["names"]},
        "claude": {"n": claude["n_skill_md"], "names": claude["names"]},
        "presence": presence,
        "expected": expected,
        "mismatches": mismatches,
        "hash_agreement": hashes,
        "identical_ok": ident_ok,
        "divergent_ok": div_ok,
        "one_tree_not_in_intersection": only_ok,
        "passed": passed,
    }


def distinct_multi_stage(invs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for tree_id, inv in invs.items():
        for row in inv["rows"]:
            by_name.setdefault(row["name"], []).append({**row, "tree_id": tree_id})
    multi = []
    for name, rows in sorted(by_name.items()):
        if any(r["multi_stage"] for r in rows):
            trees = sorted({r["tree_id"] for r in rows})
            hashes = sorted({r["sha256"] for r in rows})
            multi.append(
                {
                    "name": name,
                    "trees": trees,
                    "n_trees": len(trees),
                    "n_distinct_hashes": len(hashes),
                    "true_duplicate_deploy": len(trees) > 1 and len(hashes) == 1,
                    "name_collision_different_bytes": len(hashes) > 1,
                }
            )
    return {
        "n_distinct_names": len(by_name),
        "n_distinct_multi_stage": len(multi),
        "multi_stage": multi,
    }


def sweep() -> dict[str, Any]:
    trees = live_trees()
    probed_roots = [
        {"path": str(p), "exists": p.is_dir()} for p in candidate_tree_roots()
    ]
    invs = {
        "agents": inventory_tree(trees["agents"], "agents"),
        "claude": inventory_tree(trees["claude"], "claude"),
        "repo": inventory_tree(trees["repo"], "repo"),
        "repo_canonical": inventory_tree(trees["repo_canonical"], "repo_canonical"),
    }
    a_names = set(invs["agents"]["names"])
    c_names = set(invs["claude"]["names"])
    r_names = set(invs["repo"]["names"])
    canon_names = set(invs["repo_canonical"]["names"])
    presence_ac = classify_name_presence(a_names, c_names)
    hashes_ac = hash_agreement(invs["agents"]["rows"], invs["claude"]["rows"])
    hashes_repo = hash_agreement(
        invs["repo_canonical"]["rows"], invs["repo"]["rows"]
    )
    control = detector_control()
    load = load_controls()
    reg = load_registry()
    gfam = analyze_g_family(reg)
    distinct = distinct_multi_stage(invs)
    compact_invs = {}
    for k, inv in invs.items():
        compact_invs[k] = {kk: vv for kk, vv in inv.items()}
    return {
        "trees": {k: str(v) for k, v in trees.items()},
        "probed_roots": probed_roots,
        "inventories": compact_invs,
        "cross_tree": {
            "agents_names": sorted(a_names),
            "claude_names": sorted(c_names),
            "repo_names": sorted(r_names),
            "repo_canonical_names": sorted(canon_names),
            "intersection_agents_claude": sorted(a_names & c_names),
            "agents_only": sorted(a_names - c_names),
            "claude_only": sorted(c_names - a_names),
            "presence": presence_ac,
            "union_deployed": sorted(a_names | c_names),
            "union_all_three": sorted(a_names | c_names | r_names),
            "union_measured": sorted(a_names | c_names | r_names | canon_names),
            "intersection_canonical_compat": sorted(canon_names & r_names),
            "canonical_only": sorted(canon_names - r_names),
            "compat_only": sorted(r_names - canon_names),
        },
        "content_hash_equality": hashes_ac,
        "canonical_vs_compat": hashes_repo,
        "distinct_multi_stage": distinct,
        "detector_control": control,
        "load_semantics": load,
        "registry": {
            "present": reg.get("present"),
            "path": reg.get("path"),
            "sha256": reg.get("sha256"),
            "bytes": reg.get("bytes"),
            "n_candidates": reg.get("n_candidates"),
            "probed": reg.get("probed"),
        },
        "g_family": gfam,
    }
