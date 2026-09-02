"""Prior-art census: classify new implementation artifacts by MECHANISM."""
from __future__ import annotations

import json
from pathlib import Path

import mechanism as M
import surfaces as S

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"
REPO = HERE.parents[3]

SUBJECT_REBUILDS = [
    ESTATE / "tools" / "rebuilds" / "task-journal.mjs",
    ESTATE / "tools" / "rebuilds" / "geodesic-bounce-scheduler.mjs",
]
PRIOR_LIB = [
    ESTATE / "tools" / "lib" / "handled-ledger.mjs",
    ESTATE / "tools" / "lib" / "net-allowlist.mjs",
]


def _fps(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        if not p.is_file():
            continue
        if p.suffix.lower() not in M.MECH_SUFFIXES:
            continue
        fp = M.load_fp(p)
        if fp is not None:
            out.append(fp)
    return out


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def classify_subject(
    subject: dict,
    prior: list[dict],
    pack: dict,
    extra_candidates: list[dict] | None = None,
) -> dict:
    complete = S.surfaces_complete(pack)
    missing = S.incomplete_ids(pack)
    pool = list(prior)
    if extra_candidates:
        pool.extend(extra_candidates)
    match = M.best_match(subject, pool)
    score = match["score"] if match else 0.0
    token_hit = False
    if match:
        try:
            subj_src = Path(subject["path"]).read_text(encoding="utf-8")
            cand_src = Path(match["candidate_path"]).read_text(encoding="utf-8")
            token_hit = M.token_search_hit(subj_src, cand_src) or M.token_search_hit(
                cand_src, subj_src
            )
        except OSError:
            token_hit = False
    # Filename must not drive the verdict.
    filename_driven = bool(match and match["filename_same"] and score < M.DUPLICATE_THRESHOLD)
    if match and score >= M.DUPLICATE_THRESHOLD:
        verdict = "DUPLICATE-OF"
        prior_art = match["candidate_path"]
    elif complete:
        verdict = "GENUINELY-NEW"
        prior_art = None
    else:
        verdict = "NOT-CHECKED"
        prior_art = match["candidate_path"] if match else None
    return {
        "subject_path": subject["path"],
        "verdict": verdict,
        "prior_art": prior_art,
        "score": score,
        "shingle_jaccard": match["shingle_jaccard"] if match else 0.0,
        "ast_jaccard": match["ast_jaccard"] if match else None,
        "export_overlap": match["export_overlap"] if match else [],
        "filename_same": match["filename_same"] if match else False,
        "filename_driven": filename_driven,
        "token_search_hit": token_hit,
        "surfaces_complete": complete,
        "surfaces_named": list(S.REQUIRED_SURFACE_IDS),
        "surfaces_missing": missing,
        "queries": [
            "identifier-normalized w-shingles (w=5) Jaccard",
            "Python AST node-type Jaccard when parseable",
            "export-name token search (strike-1; not load-bearing)",
        ],
        "mechanism_note": (
            "Compare MECHANISM (normalized shingles), not filename. "
            "GENUINELY-NEW requires every required surface enumerated."
        ),
    }


def fixture_census(git_repo: Path) -> dict:
    pack = S.fixture_surfaces(ESTATE, git_repo)
    prior = _fps(PRIOR_LIB)
    # Prior art also includes live trees / inventory files as candidates.
    extra_paths = []
    for root in (
        ESTATE / "live-claude",
        ESTATE / "live-agents",
        ESTATE / "inventory",
    ):
        extra_paths.extend(S.walk_code(root))
    extra = _fps(extra_paths)
    entries = []
    for path in SUBJECT_REBUILDS:
        fp = M.load_fp(path)
        entries.append(classify_subject(fp, prior, pack, extra))
    hist = pack["git_history_deleted"]
    wfa = pack["wfa_0120_workflows"]
    workflow_rows = []
    for row in wfa.get("rows") or []:
        if not isinstance(row, dict):
            continue
        workflow_rows.append(
            {
                "subject_path": f"workflow:{row.get('blueprint_id')}",
                "verdict": row.get("verdict") or "NOT-CHECKED",
                "prior_art": row.get("existing_candidate"),
                "consumed_from": "WFA-0120",
                "mechanism": row.get("mechanism"),
                "surfaces_named": ["wfa_0120_workflows"],
            }
        )
    planted = next(
        e for e in entries if e["subject_path"].endswith("task-journal.mjs")
    )
    novel = next(
        e
        for e in entries
        if e["subject_path"].endswith("geodesic-bounce-scheduler.mjs")
    )
    # Token search from salvage exports into the planted file must miss.
    salvage_src = (ESTATE / "tools/lib/handled-ledger.mjs").read_text(encoding="utf-8")
    plant_src = (ESTATE / "tools/rebuilds/task-journal.mjs").read_text(encoding="utf-8")
    novel_src = (
        ESTATE / "tools/rebuilds/geodesic-bounce-scheduler.mjs"
    ).read_text(encoding="utf-8")
    token_miss_on_plant = not M.token_search_hit(salvage_src, plant_src)
    token_bait_on_novel = "ledger" in novel_src.lower() and "sha256" in novel_src.lower()
    controls = {
        "planted_duplicate": {
            "result": "PASS"
            if planted["verdict"] == "DUPLICATE-OF"
            and planted["prior_art"]
            and planted["prior_art"].endswith("handled-ledger.mjs")
            and not planted["filename_same"]
            and token_miss_on_plant
            else "FAIL",
            "verdict": planted["verdict"],
            "prior_art": planted["prior_art"],
            "score": planted["score"],
            "filename_same": planted["filename_same"],
            "token_search_missed_rename": token_miss_on_plant,
        },
        "novel_no_false_positive": {
            "result": "PASS"
            if novel["verdict"] == "GENUINELY-NEW"
            and novel["score"] < M.NOVEL_CEILING
            and token_bait_on_novel
            else "FAIL",
            "verdict": novel["verdict"],
            "score": novel["score"],
            "shared_vocabulary_present": token_bait_on_novel,
        },
        "git_history_deleted_symbol": {
            "result": "PASS"
            if hist.get("found_in_deleted")
            and not hist.get("found_in_head")
            and hist.get("status") == "enumerated"
            else "FAIL",
            "symbol": M.DELETED_SYMBOL,
            "found_in_deleted": hist.get("found_in_deleted"),
            "found_in_head": hist.get("found_in_head"),
            "deleted_path": hist.get("deleted_path"),
            "commit": hist.get("commit"),
        },
    }
    return {
        "kind": "fixture-estate",
        "surfaces": S.named_surface_list(pack),
        "surfaces_complete": S.surfaces_complete(pack),
        "entries": entries + workflow_rows,
        "controls": controls,
        "wfa_0120": {
            "status": wfa.get("status"),
            "path": wfa.get("path"),
            "count": wfa.get("count"),
        },
    }


def live_b07_subjects(repo: Path) -> list[Path]:
    lib = repo / "tools" / "lib"
    if not lib.is_dir():
        return []
    return [
        p
        for p in S.walk_code(lib)
        if p.suffix.lower() in {".mjs", ".js", ".cjs", ".py"} and "tests" not in p.parts
    ]


def live_program_built(repo: Path) -> list[Path]:
    root = repo / "tools" / "command-center"
    if not root.is_dir():
        return []
    return [
        p
        for p in S.walk_code(root)
        if p.suffix == ".py" and "tests" not in p.parts
    ]


def live_census(repo: Path) -> dict:
    pack = S.host_surfaces(repo)
    b07 = live_b07_subjects(repo)
    built = live_program_built(repo)
    # Mechanism candidates: code on live trees, skill/plugin scripts, tools/.
    # SKILL.md / plugin.json remain surface-enumerated, not shingle subjects.
    candidates_paths = []
    for key in ("live_claude", "live_agents"):
        p = Path((pack[key].get("path") or ""))
        candidates_paths.extend(S.walk_mech(p))
    for root in S.inventory_roots(repo):
        candidates_paths.extend(S.walk_mech(root))
    tools = repo / "tools"
    if tools.is_dir():
        candidates_paths.extend(
            p for p in S.walk_mech(tools) if "tests" not in p.parts
        )
    cand_fps = _fps(list({p.resolve(): p for p in candidates_paths if p.is_file()}.values()))
    entries = []
    for path in b07 + built:
        fp = M.load_fp(path)
        if fp is None:
            continue
        row = classify_subject(fp, cand_fps, pack)
        row["subject_rel"] = _rel(path, repo)
        row["b07_confirmed"] = path in b07
        entries.append(row)
    return {
        "kind": "live-estate",
        "b07_input": {
            "status": "enumerated" if b07 else "absent",
            "expected": "tools/lib salvage tree (6 modules) produced by B07",
            "found": [_rel(p, repo) for p in b07],
            "note": (
                "tools/lib is present on this worktree"
                if b07
                else "tools/lib salvage tree is ABSENT on this worktree; "
                "B07 is a bucket-style dependency, not a catalog unit id"
            ),
        },
        "program_built_unconfirmed_b07": [_rel(p, repo) for p in built],
        "surfaces": S.named_surface_list(pack),
        "surfaces_complete": S.surfaces_complete(pack),
        "surfaces_missing": S.incomplete_ids(pack),
        "entries": entries,
        "wfa_0120": {
            "status": pack["wfa_0120_workflows"].get("status"),
            "path": pack["wfa_0120_workflows"].get("path"),
            "count": pack["wfa_0120_workflows"].get("count"),
            "note": (
                "Workflow rebuild rows are consumed from WFA-0120, not re-detected here."
            ),
        },
    }


def dump(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2, default=_default) + "\n", encoding="utf-8")


def _default(obj):
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(type(obj))
