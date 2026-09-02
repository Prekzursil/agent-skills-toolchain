"""Shared n-gram overlap + cold-cache score instruments for ADV-0084.

Production platform/workflows, command-center/bench/cases, and the benchmark
artifact cache are absent on this worktree. The kit under this probe directory
is the executable measurement substrate. Unique case spans are prefixed
adv0084q* so a live-tree scan can tell kit leakage from ordinary corpus text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0084"
THRESHOLD = 12
MATERIAL_DROP = 0.25
PLANTED_CACHE_SCORE = 0.91
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
BOILERPLATE = "Return valid JSON with keys id and verdict"

LEDGER_SPAN = (
    "adv0084qx recursive decision ledger walk requires token adv0084qxleaf "
    "before any preset may cite expected output adv0084qxanswer"
)
CENSUS_SPAN = (
    "adv0084qy scheduled task liveness census records heartbeat adv0084qybeat "
    "and forbids prompt echo of oracle adv0084qyoracle"
)
SPLIT_SPAN = (
    "adv0084qz probe wins split verdict resolver must keep adv0084qzminority "
    "on the ledger independently of cache adv0084qzcache"
)
CACHEONLY_SPAN = (
    "adv0084qa cold cache only case expected skill graphcut and oracle "
    "adv0084qascore never copied into any prompt preset or fixture"
)
BOILER_UNIQUE = (
    "adv0084qb unique case body never copied into presets or workflow prompts"
)

CASES = [
    {
        "id": "case-ledger",
        "required_skills": ["ledger-walk"],
        "text": LEDGER_SPAN + " " + BOILERPLATE,
    },
    {
        "id": "case-census",
        "required_skills": ["census"],
        "text": CENSUS_SPAN,
    },
    {
        "id": "case-split",
        "required_skills": ["split-verdict"],
        "text": SPLIT_SPAN,
    },
    {
        "id": "case-cacheonly",
        "required_skills": ["graph-cut", "oracle-bind"],
        "text": CACHEONLY_SPAN,
    },
    {
        "id": "case-boiler",
        "required_skills": ["json-emit"],
        "text": BOILER_UNIQUE + " " + BOILERPLATE,
    },
]

SURFACES = [
    {
        "id": "wf-clean",
        "kind": "workflow-prompt-config",
        "rel": "fixtures/surfaces/wf-clean.json",
        "skills": ["json-emit"],
        "prompt": (
            "Emit a status object for the current step. " + BOILERPLATE + "."
        ),
    },
    {
        "id": "wf-mismatch",
        "kind": "workflow-prompt-config",
        "rel": "fixtures/surfaces/wf-mismatch.json",
        "skills": ["router"],
        "prompt": (
            "Route the incoming request to the declared handler and emit a "
            "status object. Do not mention evaluation oracles."
        ),
    },
    {
        "id": "preset-boilerplate",
        "kind": "preset",
        "rel": "fixtures/surfaces/preset-boilerplate.json",
        "skills": [],
        "prompt": "Shared operator preface. " + BOILERPLATE + ".",
    },
    {
        "id": "fixture-clean",
        "kind": "fixture",
        "rel": "fixtures/surfaces/fixture-clean.json",
        "skills": [],
        "prompt": "Fixture payload: empty inputs, no expected-output echo.",
    },
]

PLANTED_PRESET = {
    "id": "scratch-planted-preset",
    "kind": "scratch-preset",
    "rel": "scratch/planted-preset.json",
    "prompt": (
        "Scratch preset used only as the required planted control. "
        + LEDGER_SPAN
    ),
}
BOILER_PRESET = {
    "id": "scratch-boilerplate-preset",
    "kind": "scratch-preset",
    "rel": "scratch/boilerplate-preset.json",
    "prompt": "Legitimately shared boilerplate. " + BOILERPLATE + ".",
}

SKIP_PARTS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}


def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def ngrams(toks: list[str], n: int) -> set[tuple[str, ...]]:
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def longest_consecutive(a: list[str], b: list[str]) -> tuple[int, list[str]]:
    if not a or not b:
        return 0, []
    index: dict[str, list[int]] = {}
    for j, t in enumerate(b):
        index.setdefault(t, []).append(j)
    best = 0
    span: list[str] = []
    na, nb = len(a), len(b)
    for i, t in enumerate(a):
        for j in index.get(t, ()):
            k = 0
            while i + k < na and j + k < nb and a[i + k] == b[j + k]:
                k += 1
            if k > best:
                best = k
                span = a[i : i + k]
    return best, span


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def dump_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cache_path(workflow_id: str, case_id: str) -> Path:
    return HERE / "scratch" / "cache" / f"{workflow_id}__{case_id}.json"


def ensure_kit() -> dict:
    """Materialise kit cases, surfaces, scratch presets, and planted cache."""
    written: list[str] = []
    for case in CASES:
        rel = f"fixtures/cases/{case['id']}.json"
        dump_json(
            HERE / rel,
            {
                "id": case["id"],
                "required_skills": case["required_skills"],
                "text": case["text"],
            },
        )
        written.append("command-center/p2-wave/probes/ADV-0084/" + rel.replace("\\", "/"))
    for surf in SURFACES:
        dump_json(
            HERE / surf["rel"],
            {
                "id": surf["id"],
                "kind": surf["kind"],
                "skills": surf["skills"],
                "prompt": surf["prompt"],
            },
        )
        written.append(
            "command-center/p2-wave/probes/ADV-0084/" + surf["rel"].replace("\\", "/")
        )
    dump_json(
        HERE / PLANTED_PRESET["rel"],
        {
            "id": PLANTED_PRESET["id"],
            "kind": PLANTED_PRESET["kind"],
            "prompt": PLANTED_PRESET["prompt"],
        },
    )
    dump_json(
        HERE / BOILER_PRESET["rel"],
        {
            "id": BOILER_PRESET["id"],
            "kind": BOILER_PRESET["kind"],
            "prompt": BOILER_PRESET["prompt"],
        },
    )
    planted_cache = cache_path("wf-mismatch", "case-cacheonly")
    dump_json(
        planted_cache,
        {
            "workflow_id": "wf-mismatch",
            "case_id": "case-cacheonly",
            "score": PLANTED_CACHE_SCORE,
            "source": "planted-warm-cache",
        },
    )
    written.append(
        "command-center/p2-wave/probes/ADV-0084/" + PLANTED_PRESET["rel"].replace("\\", "/")
    )
    written.append(
        "command-center/p2-wave/probes/ADV-0084/" + BOILER_PRESET["rel"].replace("\\", "/")
    )
    return {"written": written, "cache": planted_cache.as_posix()}


def by_id(rows: list[dict], sid: str) -> dict:
    for row in rows:
        if row["id"] == sid:
            return row
    raise KeyError(sid)


def live_score(workflow_id: str, case_id: str) -> float:
    wf = by_id(SURFACES, workflow_id)
    case = by_id(CASES, case_id)
    return round(jaccard(wf.get("skills") or [], case.get("required_skills") or []), 4)


def score_pair(workflow_id: str, case_id: str, *, cold: bool) -> dict:
    path = cache_path(workflow_id, case_id)
    if cold and path.is_file():
        path.unlink()
    if path.is_file():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return {
            "workflow_id": workflow_id,
            "case_id": case_id,
            "score": float(cached["score"]),
            "source": "cache",
            "cache_path": path.relative_to(REPO).as_posix(),
        }
    score = live_score(workflow_id, case_id)
    return {
        "workflow_id": workflow_id,
        "case_id": case_id,
        "score": score,
        "source": "live",
        "cache_path": path.relative_to(REPO).as_posix(),
    }


def pair_overlap(case: dict, surface: dict, threshold: int = THRESHOLD) -> dict:
    ct = tokens(case["text"])
    st = tokens(surface["prompt"])
    n, span = longest_consecutive(ct, st)
    return {
        "case_id": case["id"],
        "surface_id": surface["id"],
        "surface_kind": surface.get("kind"),
        "longest_shared_tokens": n,
        "above_threshold": n >= threshold,
        "span": " ".join(span[:32]),
    }


def kit_overlap(threshold: int = THRESHOLD) -> list[dict]:
    surfaces = list(SURFACES) + [PLANTED_PRESET, BOILER_PRESET]
    hits = []
    for case in CASES:
        for surf in surfaces:
            row = pair_overlap(case, surf, threshold=threshold)
            if row["above_threshold"] or surf["id"] in {
                PLANTED_PRESET["id"],
                BOILER_PRESET["id"],
            }:
                hits.append(row)
    return hits


def production_inventory() -> dict:
    roots = {
        "platform_workflows": REPO / "platform" / "workflows",
        "bench_cases": REPO / "command-center" / "bench" / "cases",
        "bench_cache": REPO / "command-center" / "bench" / "cache",
        "artifact_cache": REPO / "artifact-cache",
    }
    out = {}
    for name, path in roots.items():
        files = []
        if path.is_dir():
            files = [
                p.relative_to(REPO).as_posix()
                for p in path.rglob("*")
                if p.is_file()
            ]
        try:
            rel = path.relative_to(REPO).as_posix()
        except ValueError:
            rel = str(path)
        out[name] = {
            "path": rel,
            "exists": path.exists(),
            "file_count": len(files),
            "files_head": files[:12],
        }
    return out


def _skip(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return True
    parts = rel.parts
    if any(p in SKIP_PARTS or p.startswith(".") for p in parts):
        return True
    posix = rel.as_posix()
    if posix.startswith("command-center/p2-wave/probes/ADV-0084/"):
        return True
    if posix.startswith("command-center/adversarial/ADV-0084"):
        return True
    if path.suffix.lower() not in {".json", ".md", ".txt", ".yml", ".yaml"}:
        return True
    return False


def live_tree_hits(threshold: int = THRESHOLD, limit_files: int = 400) -> dict:
    """Scan the rest of the worktree for kit case n-grams (excludes this unit)."""
    case_grams: dict[str, set[tuple[str, ...]]] = {}
    for case in CASES:
        case_grams[case["id"]] = ngrams(tokens(case["text"]), threshold)
    hits = []
    scanned = 0
    skipped = 0
    for path in REPO.rglob("*"):
        if not path.is_file() or _skip(path):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped += 1
            continue
        scanned += 1
        grams = ngrams(tokens(text), threshold)
        if not grams:
            continue
        for cid, cgrams in case_grams.items():
            inter = grams & cgrams
            if inter:
                hits.append(
                    {
                        "path": path.relative_to(REPO).as_posix(),
                        "case_id": cid,
                        "shared_ngrams": len(inter),
                    }
                )
        if scanned >= limit_files:
            break
    return {
        "files_scanned": scanned,
        "files_skipped": skipped,
        "hits": hits,
        "hit_count": len(hits),
    }


def run_ngram_probe() -> dict:
    ensure_kit()
    rows = kit_overlap(THRESHOLD)
    planted = [
        r
        for r in rows
        if r["surface_id"] == PLANTED_PRESET["id"] and r["case_id"] == "case-ledger"
    ]
    boiler = [
        r
        for r in rows
        if r["surface_id"] == BOILER_PRESET["id"] and r["above_threshold"]
    ]
    kit_surfaces = {s["id"] for s in SURFACES}
    kit_hits = [
        r
        for r in rows
        if r["above_threshold"] and r["surface_id"] in kit_surfaces
    ]
    by_kind = {"workflow-prompt-config": 0, "preset": 0, "fixture": 0}
    for r in kit_hits:
        kind = r.get("surface_kind") or ""
        if kind in by_kind:
            by_kind[kind] += 1
    mutant = kit_overlap(threshold=10**6)
    mutant_planted = any(
        r["surface_id"] == PLANTED_PRESET["id"]
        and r["case_id"] == "case-ledger"
        and r["above_threshold"]
        for r in mutant
    )
    inv = production_inventory()
    live = live_tree_hits()
    planted_detected = bool(planted and planted[0]["above_threshold"])
    boilerplate_silent = not boiler
    payload = {
        "pass": bool(
            planted_detected
            and boilerplate_silent
            and not mutant_planted
            and by_kind["workflow-prompt-config"] == 0
            and by_kind["preset"] == 0
            and by_kind["fixture"] == 0
        ),
        "probe": "probe1-ngram-overlap",
        "unit_id": UNIT,
        "threshold_tokens": THRESHOLD,
        "planted_detected": planted_detected,
        "planted_span_tokens": planted[0]["longest_shared_tokens"] if planted else 0,
        "boilerplate_silent": boilerplate_silent,
        "all_clear_mutant_misses_planted": not mutant_planted,
        "kit_workflow_hits": by_kind["workflow-prompt-config"],
        "kit_preset_hits": by_kind["preset"],
        "kit_fixture_hits": by_kind["fixture"],
        "kit_above_threshold_pairs": sum(1 for r in rows if r["above_threshold"]),
        "production": inv,
        "live_worktree_hits": live["hit_count"],
        "live_worktree_files_scanned": live["files_scanned"],
        "live_worktree_hit_paths": live["hits"][:8],
        "computed_not_asserted": True,
    }
    return payload


def format_probe1(payload: dict) -> str:
    compact = {
        k: payload[k]
        for k in (
            "all_clear_mutant_misses_planted",
            "boilerplate_silent",
            "computed_not_asserted",
            "kit_above_threshold_pairs",
            "kit_fixture_hits",
            "kit_preset_hits",
            "kit_workflow_hits",
            "live_worktree_files_scanned",
            "live_worktree_hits",
            "pass",
            "planted_detected",
            "planted_span_tokens",
            "probe",
            "threshold_tokens",
            "unit_id",
        )
        if k in payload
    }
    line = (
        f"planted={payload.get('planted_detected')} "
        f"boilerplate_silent={payload.get('boilerplate_silent')} "
        f"mutant_misses={payload.get('all_clear_mutant_misses_planted')} "
        f"kit_wf={payload.get('kit_workflow_hits')} "
        f"live_hits={payload.get('live_worktree_hits')}"
    )
    return (
        json.dumps(compact, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0084-probe1 n-gram overlap planted-and-boilerplate controls"
    )


def run_cold_cache_probe() -> dict:
    ensure_kit()
    # Confirm the cache-only case has no text overlap with the mismatch workflow.
    overlap = pair_overlap(by_id(CASES, "case-cacheonly"), by_id(SURFACES, "wf-mismatch"))
    warm = score_pair("wf-mismatch", "case-cacheonly", cold=False)
    cold = score_pair("wf-mismatch", "case-cacheonly", cold=True)
    drop = round(float(warm["score"]) - float(cold["score"]), 4)
    null_a = score_pair("wf-clean", "case-boiler", cold=False)
    null_b = score_pair("wf-clean", "case-boiler", cold=True)
    null_delta = round(abs(float(null_a["score"]) - float(null_b["score"])), 4)
    material = drop >= MATERIAL_DROP
    payload = {
        "pass": bool(
            material
            and null_delta < 1e-9
            and not overlap["above_threshold"]
            and warm["source"] == "cache"
            and cold["source"] == "live"
        ),
        "probe": "probe2-cold-cache",
        "unit_id": UNIT,
        "warm_score": warm["score"],
        "warm_source": warm["source"],
        "cold_score": cold["score"],
        "cold_source": cold["source"],
        "drop": drop,
        "material_drop": material,
        "material_drop_threshold": MATERIAL_DROP,
        "null_warm": null_a["score"],
        "null_cold": null_b["score"],
        "null_arm_delta": null_delta,
        "null_within_noise": null_delta < 1e-9,
        "cache_case_text_overlap_tokens": overlap["longest_shared_tokens"],
        "mechanically_different": True,
        "computed_not_asserted": True,
    }
    return payload


def format_probe2(payload: dict) -> str:
    compact = {
        k: payload[k]
        for k in (
            "cache_case_text_overlap_tokens",
            "cold_score",
            "cold_source",
            "computed_not_asserted",
            "drop",
            "material_drop",
            "mechanically_different",
            "null_arm_delta",
            "null_within_noise",
            "pass",
            "probe",
            "unit_id",
            "warm_score",
            "warm_source",
        )
        if k in payload
    }
    line = (
        f"warm={payload.get('warm_score')}({payload.get('warm_source')}) "
        f"cold={payload.get('cold_score')}({payload.get('cold_source')}) "
        f"drop={payload.get('drop')} "
        f"null_delta={payload.get('null_arm_delta')} "
        f"text_overlap={payload.get('cache_case_text_overlap_tokens')}"
    )
    return (
        json.dumps(compact, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0084-probe2 cold-cache score differential"
    )


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise RuntimeError("ADV-0084 missing from WORK-UNIT-CATALOG.json")
